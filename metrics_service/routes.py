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

from enum import Enum

class QueryType(str, Enum):
    TOP_DOWNTIME_REASONS = "TOP_DOWNTIME_REASONS"
    DOWNTIME_BY_MACHINE = "DOWNTIME_BY_MACHINE"
    EVENTS_PER_HOUR = "EVENTS_PER_HOUR"

# Models
class TimeRange(BaseModel):
    start: str # RFC3339
    end: str   # RFC3339

class ExecuteRequest(BaseModel):
    query_type: QueryType
    tenant_id: str
    site_id: str
    time_range: TimeRange
    machine_id: Optional[str] = None

# BigQuery Client
def get_bq_client():
    return bigquery.Client(project=PROJECT_ID)

def execute_metric_query(req: ExecuteRequest):
    client = get_bq_client()
    
    # Validation: Strict time window
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

    # Select Query Template
    if req.query_type == QueryType.TOP_DOWNTIME_REASONS:
        template = TOP_DOWNTIME_REASONS
    elif req.query_type == QueryType.DOWNTIME_BY_MACHINE:
        template = DOWNTIME_BY_MACHINE
    elif req.query_type == QueryType.EVENTS_PER_HOUR:
        template = EVENTS_PER_HOUR
    else:
        raise HTTPException(status_code=400, detail="INVALID_QUERY_TYPE")

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
        project_id=PROJECT_ID,
        dataset_id=DATASET_ID,
        table_id=TABLE_ID,
        machine_filter="AND machine_id = @machine_id" if req.machine_id else ""
    )
    
    query_job = client.query(query, job_config=job_config)
    results = query_job.result()
    
    rows = [dict(row) for row in results]
    
    # Post-processing
    if req.query_type == QueryType.EVENTS_PER_HOUR:
        for r in rows:
            if "hour_bucket" in r:
                r["hour_bucket"] = r["hour_bucket"].isoformat()

    return {
        "metric_name": req.query_type.value.lower(),
        "requested_query": req.query_type.value,
        "effective_time_range": {
            "start": req.time_range.start,
            "end": req.time_range.end,
            "duration_days": round(delta.total_seconds() / 86400, 2)
        },
        "rows": rows,
        "source": {
            "type": "bigquery", 
            "job_id": query_job.job_id, 
            "table": f"{DATASET_ID}.{TABLE_ID}"
        },
        "citations": [{"type": "bigquery_job", "ref": query_job.job_id}]
    }

@router.post("/execute")
def execute_metrics(req: ExecuteRequest):
    try:
        return execute_metric_query(req)
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Metrics Execution Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Legacy endpoints for backward compatibility, internally calling the new unified logic
@router.post("/metrics/top-downtime-reasons")
def legacy_top_downtime(req: ExecuteRequest):
    req.query_type = QueryType.TOP_DOWNTIME_REASONS
    return execute_metrics(req)

@router.post("/metrics/downtime-by-machine")
def legacy_downtime_machine(req: ExecuteRequest):
    req.query_type = QueryType.DOWNTIME_BY_MACHINE
    return execute_metrics(req)

@router.post("/metrics/events-per-hour")
def legacy_events_hour(req: ExecuteRequest):
    req.query_type = QueryType.EVENTS_PER_HOUR
    return execute_metrics(req)

@router.post("/ask")
def legacy_ask(req: ExecuteRequest):
    # The /ask endpoint now expects the structure of ExecuteRequest
    # If the caller doesn't provide query_type, it will fail validation (Deterministic)
    return execute_metrics(req)
