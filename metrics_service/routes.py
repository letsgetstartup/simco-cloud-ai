from fastapi import APIRouter, HTTPException, Body
from google.cloud import bigquery
from typing import List, Optional
from pydantic import BaseModel
import os
import datetime
from bq_queries import TOP_DOWNTIME_REASONS, DOWNTIME_BY_MACHINE, EVENTS_PER_HOUR

router = APIRouter()

# Configuration
PROJECT_ID = os.environ.get("GCP_PROJECT", os.environ.get("GOOGLE_CLOUD_PROJECT"))
DATASET_ID = "simco_ai"
TABLE_ID = "events_fact"

# Models
class TimeRange(BaseModel):
    start: str
    end: str

class MetricsRequest(BaseModel):
    tenant_id: str
    site_id: str
    machine_id: Optional[str] = None
    time_range: TimeRange

class AskRequest(BaseModel):
    question: str
    tenant_id: str
    site_id: str
    machine_id: Optional[str] = None

# BigQuery Client (lazy init in dependency or global)
# Use a dependency or simple global client
def get_bq_client():
    return bigquery.Client(project=PROJECT_ID)

def execute_query(query_template, params, bq_client):
    job_config = bigquery.QueryJobConfig(
        query_parameters=params
    )
    
    # Format Query with Table ID
    query = query_template.format(
        project_id=PROJECT_ID,
        dataset_id=DATASET_ID,
        table_id=TABLE_ID,
        machine_filter="AND machine_id = @machine_id" if any(p.name == "machine_id" for p in params) else ""
    )
    
    query_job = bq_client.query(query, job_config=job_config)
    results = query_job.result()
    
    rows = [dict(row) for row in results]
    return rows, query_job.job_id

@router.post("/metrics/top-downtime-reasons")
def get_top_downtime_reasons(req: MetricsRequest):
    client = get_bq_client()
    
    params = [
        bigquery.ScalarQueryParameter("tenant_id", "STRING", req.tenant_id),
        bigquery.ScalarQueryParameter("site_id", "STRING", req.site_id),
        bigquery.ScalarQueryParameter("start_ts", "TIMESTAMP", req.time_range.start),
        bigquery.ScalarQueryParameter("end_ts", "TIMESTAMP", req.time_range.end),
        bigquery.ArrayQueryParameter("event_types", "STRING", ["STOP", "DOWNTIME", "IDLE_START", "ALARM_ON", "ALARM", "SETUP_START"]),
    ]
    
    if req.machine_id:
         params.append(bigquery.ScalarQueryParameter("machine_id", "STRING", req.machine_id))

    try:
        rows, job_id = execute_query(TOP_DOWNTIME_REASONS, params, client)
        return {
            "metric_name": "top_downtime_reasons",
            "time_range": req.time_range.dict(),
            "rows": rows,
            "source": {"type": "bigquery", "job_id": job_id, "table": f"{DATASET_ID}.{TABLE_ID}"},
            "citations": [{"type": "bigquery_job", "ref": job_id}]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/metrics/downtime-by-machine")
def get_downtime_by_machine(req: MetricsRequest):
    client = get_bq_client()
    
    params = [
        bigquery.ScalarQueryParameter("tenant_id", "STRING", req.tenant_id),
        bigquery.ScalarQueryParameter("site_id", "STRING", req.site_id),
        bigquery.ScalarQueryParameter("start_ts", "TIMESTAMP", req.time_range.start),
        bigquery.ScalarQueryParameter("end_ts", "TIMESTAMP", req.time_range.end),
        bigquery.ArrayQueryParameter("event_types", "STRING", ["STOP", "DOWNTIME", "IDLE_START", "ALARM_ON", "ALARM", "SETUP_START"]),
    ]

    try:
        rows, job_id = execute_query(DOWNTIME_BY_MACHINE, params, client)
        return {
            "metric_name": "downtime_by_machine",
            "time_range": req.time_range.dict(),
            "rows": rows,
            "source": {"type": "bigquery", "job_id": job_id, "table": f"{DATASET_ID}.{TABLE_ID}"},
            "citations": [{"type": "bigquery_job", "ref": job_id}]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/metrics/events-per-hour")
def get_events_per_hour(req: MetricsRequest):
    client = get_bq_client()
    
    params = [
        bigquery.ScalarQueryParameter("tenant_id", "STRING", req.tenant_id),
        bigquery.ScalarQueryParameter("site_id", "STRING", req.site_id),
        bigquery.ScalarQueryParameter("start_ts", "TIMESTAMP", req.time_range.start),
        bigquery.ScalarQueryParameter("end_ts", "TIMESTAMP", req.time_range.end),
        bigquery.ArrayQueryParameter("event_types", "STRING", ["STOP", "DOWNTIME", "IDLE_START", "ALARM_ON", "ALARM", "SETUP_START"]),
    ]
    
    if req.machine_id:
         params.append(bigquery.ScalarQueryParameter("machine_id", "STRING", req.machine_id))

    try:
        rows, job_id = execute_query(EVENTS_PER_HOUR, params, client)
        # Convert timestamp to string for JSON serialization
        for r in rows:
            if "hour_bucket" in r:
                r["hour_bucket"] = r["hour_bucket"].isoformat()
                
        return {
            "metric_name": "events_per_hour",
            "time_range": req.time_range.dict(),
            "rows": rows,
            "source": {"type": "bigquery", "job_id": job_id, "table": f"{DATASET_ID}.{TABLE_ID}"},
            "citations": [{"type": "bigquery_job", "ref": job_id}]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ask")
def ask(req: AskRequest):
    # Simple Intent Detection
    q = req.question.lower()
    
    # Defaults
    end_date = datetime.datetime.now(datetime.timezone.utc)
    
    # Smarter default for demo data: if "30 days" or "last month" is in query, or just default to 45 days to see all demo data
    days = 1
    if "30 days" in q or "month" in q or "all" in q or "demo" in q:
        days = 30
    elif "reasons" in q or "why" in q:
        # Default top reasons to 30 days so demo data is visible
        days = 30
        
    start_date = end_date - datetime.timedelta(days=days)
    
    time_range = TimeRange(
        start=start_date.isoformat(),
        end=end_date.isoformat()
    )
    
    metrics_req = MetricsRequest(
        tenant_id=req.tenant_id,
        site_id=req.site_id,
        machine_id=req.machine_id,
        time_range=time_range
    )
    
    if "reasons" in q or "why" in q:
        return get_top_downtime_reasons(metrics_req)
    elif "machine" in q:
        # Default to 30 days for demo machine comparison
        start_date_30d = end_date - datetime.timedelta(days=30)
        metrics_req.time_range.start = start_date_30d.isoformat()
        return get_downtime_by_machine(metrics_req)
    elif "trend" in q or "hour" in q:
        return get_events_per_hour(metrics_req)
    else:
        # Default fallback to 30 days for demo visibility
        return get_top_downtime_reasons(metrics_req)
