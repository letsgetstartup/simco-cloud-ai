import json
import hashlib
import logging
from pythonjsonlogger import jsonlogger
from fastapi import APIRouter, HTTPException, Body, Request
from google.cloud import bigquery
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import os
import datetime

# Structured Logging Setup
logger = logging.getLogger()
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s')
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

router = APIRouter()

# Configuration
PROJECT_ID = os.environ.get("GCP_PROJECT", os.environ.get("GOOGLE_CLOUD_PROJECT"))
DATASET_ID = "simco_ai"
TABLE_ID = "events_fact"
REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "registry", "metrics.json")

# Models
class TimeRange(BaseModel):
    start: str # RFC3339
    end: str   # RFC3339

class ExecuteRequest(BaseModel):
    query_type: str
    tenant_id: str
    site_id: str
    time_range: TimeRange
    machine_id: Optional[str] = None

# Registry Loader
class MetricRegistry:
    def __init__(self):
        self.metrics = {}
        self.load()

    def load(self):
        try:
            with open(REGISTRY_PATH, 'r') as f:
                data = json.load(f)
                self.metrics = data.get("metrics", {})
        except Exception as e:
            logger.error("Error loading registry", extra={"error": str(e)})
            self.metrics = {}

    def get_metric(self, query_type: str) -> Optional[Dict[str, Any]]:
        return self.metrics.get(query_type)

    def get_sql(self, template_path: str) -> str:
        full_path = os.path.join(os.path.dirname(__file__), "registry", template_path)
        with open(full_path, 'r') as f:
            return f.read()

registry = MetricRegistry()

# BigQuery Client
def get_bq_client():
    return bigquery.Client(project=PROJECT_ID)

def check_data_quality(client, tenant_id, site_id):
    """Query the dq_metrics table for recent batch health."""
    template = registry.get_sql("sql/dq_metrics.sql")
    query = template.format(project_id=PROJECT_ID, dataset_id=DATASET_ID)
    
    params = [
        bigquery.ScalarQueryParameter("tenant_id", "STRING", tenant_id),
        bigquery.ScalarQueryParameter("site_id", "STRING", site_id),
    ]
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    
    try:
        results = list(client.query(query, job_config=job_config).result())[0]
        if not results.total_batch_size:
             return "UNKNOWN", ["No record of recent ETL runs for this scope."]
        
        warnings = []
        confidence = "HIGH"
        
        # Policy: If > 5% machine_id missing, low confidence
        if results.total_missing_machine / results.total_batch_size > 0.05:
             confidence = "LOW"
             warnings.append(f"Significant data gaps: {results.total_missing_machine} events missing machine IDs.")
        
        if results.total_negative_duration > 0:
             warnings.append(f"Data anomaly: {results.total_negative_duration} events had negative durations and were clamped.")
             
        return confidence, warnings
    except Exception as e:
        logger.warning("DQ Check failed", extra={"error": str(e)})
        return "UNKNOWN", [f"Data quality status unavailable: {str(e)}"]

def execute_metric_query(req: ExecuteRequest):
    metric_def = registry.get_metric(req.query_type)
    if not metric_def:
        raise HTTPException(status_code=400, detail=f"INVALID_QUERY_TYPE: {req.query_type}")

    client = get_bq_client()
    
    # 1. Data Quality Gate
    confidence, dq_warnings = check_data_quality(client, req.tenant_id, req.site_id)
    
    # Policy Enforcement: If registry specifies required DQ checks and confidence is LOW/UNKNOWN, block execution.
    dq_required = metric_def.get("dq_required", [])
    if dq_required and confidence in ["LOW", "UNKNOWN"]:
        logger.error("DQ Gating Failure: Metric required high-quality data but DQ confidence is insufficient.", extra={
            "query_type": req.query_type,
            "confidence": confidence,
            "dq_required": dq_required
        })
        raise HTTPException(
            status_code=409, 
            detail={
                "error": "DATA_QUALITY_FAILED",
                "confidence": confidence,
                "warnings": dq_warnings,
                "required_dq": dq_required
            }
        )
    
    # 2. Validation: Strict time window
    try:
        start_dt = datetime.datetime.fromisoformat(req.time_range.start.replace('Z', '+00:00'))
        end_dt = datetime.datetime.fromisoformat(req.time_range.end.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time format. Use RFC3339 (ISO8601).")

    if end_dt <= start_dt:
        raise HTTPException(status_code=400, detail="End time must be after start time.")
    
    delta = end_dt - start_dt
    if delta.days > 90:
        raise HTTPException(status_code=400, detail="Time range exceeds 90 day limit.")

    # 3. Intelligent Routing (Rollup decision)
    use_rollup = False
    active_table = TABLE_ID
    template_path = metric_def["sql_template_path"]

    # Policy: If range > 7 days, use rollup for faster scanning
    if delta.days > 7 and req.query_type in ["TOP_DOWNTIME_REASONS", "DOWNTIME_BY_MACHINE"]:
        use_rollup = True
        active_table = "events_daily_rollup"
        template_path = "sql/events_rollup.sql" # Use generic rollup template
        logger.info("Intelligent routing: Switching to ROLLUP table for long-range query.", extra={"days": delta.days})

    # 4. Execution
    template = registry.get_sql(template_path)
    params = [
        bigquery.ScalarQueryParameter("tenant_id", "STRING", req.tenant_id),
        bigquery.ScalarQueryParameter("site_id", "STRING", req.site_id),
        bigquery.ScalarQueryParameter("start_ts", "TIMESTAMP", req.time_range.start),
        bigquery.ScalarQueryParameter("end_ts", "TIMESTAMP", req.time_range.end),
        bigquery.ArrayQueryParameter("event_types", "STRING", ["STOP", "DOWNTIME", "IDLE_START", "ALARM_ON", "ALARM", "SETUP_START"]),
    ]
    if req.machine_id:
         params.append(bigquery.ScalarQueryParameter("machine_id", "STRING", req.machine_id))

    job_config = bigquery.QueryJobConfig(query_parameters=params)
    query = template.format(
        project_id=PROJECT_ID, dataset_id=DATASET_ID, table_id=active_table,
        machine_filter="AND machine_id = @machine_id" if req.machine_id else ""
    )
    
    query_hash = hashlib.sha256(query.encode()).hexdigest()
    query_job = client.query(query, job_config=job_config)
    results = query_job.result()
    rows = [dict(row) for row in results]
    
    # Post-processing
    if req.query_type == "EVENTS_PER_HOUR" and not use_rollup:
        for r in rows:
            if "hour_bucket" in r: r["hour_bucket"] = r["hour_bucket"].isoformat()
    if use_rollup:
        for r in rows:
            if "date" in r: r["date"] = r["date"].isoformat()

    response = {
        "metric_name": req.query_type.lower(),
        "query_type": req.query_type,
        "metric_version": metric_def.get("metric_version", "1.0.0"),
        "confidence": confidence,
        "warnings": dq_warnings,
        "effective_time_range": {
            "start": req.time_range.start,
            "end": req.time_range.end,
            "duration_days": round(delta.total_seconds() / 86400, 2),
            "source": "rollup" if use_rollup else "raw"
        },
        "rows": rows,
        "visualization": metric_def.get("visualization"),
        "audit": {
            "type": "bigquery", 
            "job_id": query_job.job_id, 
            "query_hash": query_hash,
            "table": f"{DATASET_ID}.{active_table}"
        },
        "citations": [{"type": "bigquery_job", "ref": query_job.job_id}]
    }
    
    logger.info("Metric execution completed", extra={
        "query_type": req.query_type, 
        "rows_returned": len(rows),
        "confidence": confidence,
        "source": "rollup" if use_rollup else "raw",
        "job_id": query_job.job_id
    })
    return response

@router.post("/execute")
def execute(req: ExecuteRequest, request: Request):
    # Security: Reinforce tenant isolation
    # In production, this would be extracted from a verified OIDC token
    provided_tenant = request.headers.get("X-Tenant-ID")
    if provided_tenant and provided_tenant != req.tenant_id:
        logger.warning("Security alert: Tenant mismatch detected", extra={
            "header_tenant": provided_tenant,
            "body_tenant": req.tenant_id
        })
        raise HTTPException(status_code=403, detail="FORBIDDEN: Tenant context mismatch.")

    try:
        return execute_metric_query(req)
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error("Internal Execution Error", extra={"error": str(e), "query_type": req.query_type})
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ask")
def ask(req: ExecuteRequest):
    return execute(req)
