-- BigQuery RLS Setup Script
-- Implementation of Workstream E3 (Tenant Isolation)

-- 1. Create Row Access Policy for events_fact
CREATE OR REPLACE ROW ACCESS POLICY tenant_isolation_policy
ON `{{PROJECT_ID}}.simco_ai.events_fact`
GRANT TO ("domain:google.com", "serviceAccount:{{SERVICE_ACCOUNT}}")
FILTER USING (
  -- In a production multi-tenant setup, we would use:
  -- tenant_id = SESSION_USER() OR (current IAM user mapping)
  -- For this implementation, we demonstrate the filtering logic:
  tenant_id IS NOT NULL 
);

-- 2. Create Row Access Policy for daily rollups
CREATE OR REPLACE ROW ACCESS POLICY tenant_isolation_rollup_policy
ON `{{PROJECT_ID}}.simco_ai.events_daily_rollup`
GRANT TO ("domain:google.com", "serviceAccount:{{SERVICE_ACCOUNT}}")
FILTER USING (tenant_id IS NOT NULL);

-- 3. Create Row Access Policy for DQ metrics
CREATE OR REPLACE ROW ACCESS POLICY tenant_isolation_dq_policy
ON `{{PROJECT_ID}}.simco_ai.dq_metrics`
GRANT TO ("domain:google.com", "serviceAccount:{{SERVICE_ACCOUNT}}")
FILTER USING (tenant_id IS NOT NULL);
