# metrics_service/bq_queries.py

TOP_DOWNTIME_REASONS = """
SELECT
  COALESCE(reason_code, reason_text, 'UNKNOWN') as reason,
  COUNT(*) as event_count,
  COALESCE(SUM(duration_seconds), 0) / 60 as downtime_minutes
FROM `{project_id}.{dataset_id}.{table_id}`
WHERE tenant_id = @tenant_id
  AND site_id = @site_id
  AND start_ts >= @start_ts
  AND start_ts < @end_ts
  AND event_type IN UNNEST(@event_types)
  {machine_filter}
GROUP BY 1
ORDER BY downtime_minutes DESC
LIMIT 10
"""

DOWNTIME_BY_MACHINE = """
SELECT
  machine_id,
  COALESCE(SUM(duration_seconds), 0) / 60 as downtime_minutes
FROM `{project_id}.{dataset_id}.{table_id}`
WHERE tenant_id = @tenant_id
  AND site_id = @site_id
  AND start_ts >= @start_ts
  AND start_ts < @end_ts
  AND event_type IN UNNEST(@event_types)
  AND machine_id IS NOT NULL
GROUP BY 1
ORDER BY downtime_minutes DESC
"""

EVENTS_PER_HOUR = """
SELECT
  TIMESTAMP_TRUNC(start_ts, HOUR) as hour_bucket,
  COUNT(*) as event_count,
  COALESCE(SUM(duration_seconds), 0) / 60 as downtime_minutes
FROM `{project_id}.{dataset_id}.{table_id}`
WHERE tenant_id = @tenant_id
  AND site_id = @site_id
  AND start_ts >= @start_ts
  AND start_ts < @end_ts
  AND event_type IN UNNEST(@event_types)
  {machine_filter}
GROUP BY 1
ORDER BY 1 ASC
"""
