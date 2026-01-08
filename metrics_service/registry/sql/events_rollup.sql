SELECT
  event_date as date,
  event_type,
  reason_code,
  SUM(event_count) as total_events,
  SUM(total_duration_seconds) as total_duration
FROM `{project_id}.{dataset_id}.events_daily_rollup`
WHERE tenant_id = @tenant_id
  AND site_id = @site_id
  AND event_date BETWEEN DATE(@start_ts) AND DATE(@end_ts)
  {machine_filter}
GROUP BY 1, 2, 3
ORDER BY 1 ASC
