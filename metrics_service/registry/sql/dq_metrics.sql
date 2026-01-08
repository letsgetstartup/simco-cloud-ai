SELECT 
  SUM(batch_size) as total_batch_size,
  SUM(missing_machine_count) as total_missing_machine,
  SUM(negative_duration_count) as total_negative_duration,
  SUM(missing_start_ts_count) as total_missing_start_ts
FROM `{project_id}.{dataset_id}.dq_metrics`
WHERE tenant_id = @tenant_id
  AND site_id = @site_id
  AND run_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
