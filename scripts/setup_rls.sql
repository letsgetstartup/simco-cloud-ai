-- 1. Identity-Bound Policy for Tenant: test_tenant
CREATE OR REPLACE ROW ACCESS POLICY rls_test_tenant
ON `{{PROJECT_ID}}.simco_ai.events_fact`
GRANT TO ("serviceAccount:metrics-tenant-test@{{PROJECT_ID}}.iam.gserviceaccount.com")
FILTER USING (tenant_id = "test_tenant");

-- 2. Identity-Bound Policy for Tenant: demo_tenant
CREATE OR REPLACE ROW ACCESS POLICY rls_demo_tenant
ON `{{PROJECT_ID}}.simco_ai.events_fact`
GRANT TO ("serviceAccount:metrics-tenant-demo@{{PROJECT_ID}}.iam.gserviceaccount.com")
FILTER USING (tenant_id = "demo_tenant");

-- Repeat similar patterns for events_daily_rollup and dq_metrics...
CREATE OR REPLACE ROW ACCESS POLICY rls_rollup_test_tenant
ON `{{PROJECT_ID}}.simco_ai.events_daily_rollup`
GRANT TO ("serviceAccount:metrics-tenant-test@{{PROJECT_ID}}.iam.gserviceaccount.com")
FILTER USING (tenant_id = "test_tenant");

CREATE OR REPLACE ROW ACCESS POLICY rls_dq_test_tenant
ON `{{PROJECT_ID}}.simco_ai.dq_metrics`
GRANT TO ("serviceAccount:metrics-tenant-test@{{PROJECT_ID}}.iam.gserviceaccount.com")
FILTER USING (tenant_id = "test_tenant");
