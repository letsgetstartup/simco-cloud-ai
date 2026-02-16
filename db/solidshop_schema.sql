-- SolidShop AI PostgreSQL schema (v1)
-- Note: uses UUID PKs and tenant-scoped uniqueness.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1) Multi-tenant and security
CREATE TABLE tenants (
  tenant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  timezone TEXT NOT NULL DEFAULT 'UTC',
  currency TEXT NOT NULL DEFAULT 'USD',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
  user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  email TEXT NOT NULL,
  full_name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, email)
);

CREATE TABLE roles (
  role_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  name TEXT NOT NULL,
  UNIQUE (tenant_id, name)
);

CREATE TABLE user_roles (
  user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  role_id UUID NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, role_id)
);

CREATE TABLE permissions (
  permission_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL
);

CREATE TABLE role_permissions (
  role_id UUID NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
  permission_id UUID NOT NULL REFERENCES permissions(permission_id) ON DELETE CASCADE,
  PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE audit_log (
  audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  entity_type TEXT NOT NULL,
  entity_id UUID NOT NULL,
  action TEXT NOT NULL,
  before_json JSONB,
  after_json JSONB,
  user_id UUID REFERENCES users(user_id),
  ts TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE system_events (
  event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  entity_type TEXT NOT NULL,
  entity_id UUID NOT NULL,
  event_code TEXT NOT NULL,
  payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  ts TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2) Parties
CREATE TABLE customers (
  customer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  name TEXT NOT NULL,
  terms_code TEXT,
  credit_limit NUMERIC(14,2),
  status TEXT NOT NULL DEFAULT 'active',
  UNIQUE (tenant_id, name)
);

CREATE TABLE customer_contacts (
  contact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id UUID NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  email TEXT,
  phone TEXT
);

CREATE TABLE vendors (
  vendor_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  name TEXT NOT NULL,
  lead_time_days INTEGER,
  rating NUMERIC(5,2),
  UNIQUE (tenant_id, name)
);

CREATE TABLE vendor_contacts (
  contact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  vendor_id UUID NOT NULL REFERENCES vendors(vendor_id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  email TEXT,
  phone TEXT
);

-- 3) Items, machines, and resources
CREATE TABLE items (
  item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  part_no TEXT NOT NULL,
  rev TEXT,
  description TEXT,
  uom TEXT NOT NULL,
  UNIQUE (tenant_id, part_no, rev)
);

CREATE TABLE materials (
  material_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  spec TEXT NOT NULL,
  form TEXT,
  uom TEXT NOT NULL
);

CREATE TABLE tools (
  tool_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  tool_no TEXT NOT NULL,
  type TEXT,
  vendor_id UUID REFERENCES vendors(vendor_id),
  min_qty NUMERIC(12,3) DEFAULT 0,
  UNIQUE (tenant_id, tool_no)
);

CREATE TABLE machines (
  machine_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  name TEXT NOT NULL,
  type TEXT,
  cell TEXT,
  UNIQUE (tenant_id, name)
);

CREATE TABLE machine_signals (
  signal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  machine_id UUID NOT NULL REFERENCES machines(machine_id),
  ts TIMESTAMPTZ NOT NULL,
  state TEXT NOT NULL,
  spindle NUMERIC(12,3),
  feed NUMERIC(12,3),
  alarm TEXT
);

-- 4) CRM and quoting
CREATE TABLE rfqs (
  rfq_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  customer_id UUID NOT NULL REFERENCES customers(customer_id),
  received_ts TIMESTAMPTZ NOT NULL,
  due_ts TIMESTAMPTZ,
  status TEXT NOT NULL
);

CREATE TABLE rfq_lines (
  rfq_line_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rfq_id UUID NOT NULL REFERENCES rfqs(rfq_id) ON DELETE CASCADE,
  item_id UUID REFERENCES items(item_id),
  part_desc TEXT,
  qty NUMERIC(14,3) NOT NULL,
  target_price NUMERIC(14,2)
);

CREATE TABLE quotes (
  quote_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  customer_id UUID NOT NULL REFERENCES customers(customer_id),
  quote_no TEXT NOT NULL,
  status TEXT NOT NULL,
  valid_until DATE,
  terms_code TEXT,
  created_by UUID REFERENCES users(user_id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, quote_no)
);

CREATE TABLE quote_lines (
  quote_line_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  quote_id UUID NOT NULL REFERENCES quotes(quote_id) ON DELETE CASCADE,
  item_id UUID REFERENCES items(item_id),
  rev TEXT,
  qty NUMERIC(14,3) NOT NULL,
  unit_price NUMERIC(14,4) NOT NULL,
  lead_time_days INTEGER
);

CREATE TABLE quote_estimates (
  estimate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  quote_line_id UUID NOT NULL REFERENCES quote_lines(quote_line_id) ON DELETE CASCADE,
  material_cost NUMERIC(14,2) NOT NULL DEFAULT 0,
  labor_cost NUMERIC(14,2) NOT NULL DEFAULT 0,
  overhead_cost NUMERIC(14,2) NOT NULL DEFAULT 0,
  outside_cost NUMERIC(14,2) NOT NULL DEFAULT 0,
  margin_pct NUMERIC(7,3)
);

CREATE TABLE quote_operations (
  qop_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  quote_line_id UUID NOT NULL REFERENCES quote_lines(quote_line_id) ON DELETE CASCADE,
  op_seq INTEGER NOT NULL,
  work_center TEXT NOT NULL,
  setup_min INTEGER NOT NULL DEFAULT 0,
  run_min_per_part NUMERIC(12,3) NOT NULL DEFAULT 0
);

-- 5) Jobs, routing, time
CREATE TABLE jobs (
  job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  job_no TEXT NOT NULL,
  customer_id UUID NOT NULL REFERENCES customers(customer_id),
  status TEXT NOT NULL,
  promised_date DATE,
  priority INTEGER NOT NULL DEFAULT 3,
  sales_order_ref TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, job_no)
);

CREATE TABLE job_lines (
  job_line_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id UUID NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
  item_id UUID REFERENCES items(item_id),
  part_no TEXT,
  rev TEXT,
  qty_ordered NUMERIC(14,3) NOT NULL,
  qty_completed NUMERIC(14,3) NOT NULL DEFAULT 0,
  scrap_qty NUMERIC(14,3) NOT NULL DEFAULT 0
);

CREATE TABLE job_ops (
  job_op_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_line_id UUID NOT NULL REFERENCES job_lines(job_line_id) ON DELETE CASCADE,
  op_seq INTEGER NOT NULL,
  status TEXT NOT NULL,
  machine_id UUID REFERENCES machines(machine_id),
  setup_min INTEGER NOT NULL DEFAULT 0,
  run_min NUMERIC(12,3) NOT NULL DEFAULT 0,
  queue_min INTEGER NOT NULL DEFAULT 0,
  start_ts TIMESTAMPTZ,
  end_ts TIMESTAMPTZ,
  UNIQUE (job_line_id, op_seq)
);

CREATE TABLE employees (
  employee_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  name TEXT NOT NULL,
  badge TEXT,
  rate NUMERIC(12,2)
);

CREATE TABLE timecards (
  timecard_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id UUID NOT NULL REFERENCES employees(employee_id),
  job_op_id UUID REFERENCES job_ops(job_op_id),
  type TEXT NOT NULL,
  start_ts TIMESTAMPTZ NOT NULL,
  end_ts TIMESTAMPTZ,
  minutes INTEGER,
  notes TEXT
);

-- 6) Scheduling
CREATE TABLE schedule_orders (
  sched_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  job_op_id UUID NOT NULL REFERENCES job_ops(job_op_id),
  required_minutes INTEGER NOT NULL,
  earliest_start TIMESTAMPTZ,
  due_ts TIMESTAMPTZ,
  priority INTEGER NOT NULL DEFAULT 3
);

CREATE TABLE schedule_slots (
  slot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  machine_id UUID NOT NULL REFERENCES machines(machine_id),
  sched_id UUID NOT NULL REFERENCES schedule_orders(sched_id) ON DELETE CASCADE,
  start_ts TIMESTAMPTZ NOT NULL,
  end_ts TIMESTAMPTZ NOT NULL,
  locked_bool BOOLEAN NOT NULL DEFAULT FALSE
);

-- 7) Inventory and purchasing
CREATE TABLE warehouses (
  wh_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  name TEXT NOT NULL,
  UNIQUE (tenant_id, name)
);

CREATE TABLE bins (
  bin_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  wh_id UUID NOT NULL REFERENCES warehouses(wh_id) ON DELETE CASCADE,
  code TEXT NOT NULL,
  UNIQUE (wh_id, code)
);

CREATE TABLE inventory_items (
  inv_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  item_id UUID REFERENCES items(item_id),
  material_id UUID REFERENCES materials(material_id),
  tool_id UUID REFERENCES tools(tool_id),
  bin_id UUID REFERENCES bins(bin_id),
  qty_on_hand NUMERIC(14,3) NOT NULL DEFAULT 0,
  qty_allocated NUMERIC(14,3) NOT NULL DEFAULT 0
);

CREATE TABLE purchase_orders (
  po_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  vendor_id UUID NOT NULL REFERENCES vendors(vendor_id),
  po_no TEXT NOT NULL,
  status TEXT NOT NULL,
  created_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  expected_ts TIMESTAMPTZ,
  UNIQUE (tenant_id, po_no)
);

CREATE TABLE po_lines (
  po_line_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  po_id UUID NOT NULL REFERENCES purchase_orders(po_id) ON DELETE CASCADE,
  item_id UUID REFERENCES items(item_id),
  material_id UUID REFERENCES materials(material_id),
  tool_id UUID REFERENCES tools(tool_id),
  qty NUMERIC(14,3) NOT NULL,
  unit_cost NUMERIC(14,4) NOT NULL
);

CREATE TABLE receipts (
  receipt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  po_id UUID NOT NULL REFERENCES purchase_orders(po_id),
  received_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  receiver_user_id UUID REFERENCES users(user_id)
);

CREATE TABLE receipt_lines (
  rline_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  receipt_id UUID NOT NULL REFERENCES receipts(receipt_id) ON DELETE CASCADE,
  po_line_id UUID NOT NULL REFERENCES po_lines(po_line_id),
  qty_received NUMERIC(14,3) NOT NULL,
  lot_no TEXT
);

-- 8) Quality
CREATE TABLE inspections (
  insp_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  job_op_id UUID NOT NULL REFERENCES job_ops(job_op_id),
  type TEXT NOT NULL,
  status TEXT NOT NULL
);

CREATE TABLE ncrs (
  ncr_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  job_id UUID REFERENCES jobs(job_id),
  job_op_id UUID REFERENCES job_ops(job_op_id),
  severity TEXT NOT NULL,
  disposition TEXT,
  cost_estimate NUMERIC(14,2)
);

-- 9) Shipping and invoicing
CREATE TABLE shipments (
  ship_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  customer_id UUID NOT NULL REFERENCES customers(customer_id),
  ship_no TEXT NOT NULL,
  ship_date DATE,
  carrier TEXT,
  tracking TEXT,
  status TEXT NOT NULL,
  UNIQUE (tenant_id, ship_no)
);

CREATE TABLE shipment_lines (
  sline_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ship_id UUID NOT NULL REFERENCES shipments(ship_id) ON DELETE CASCADE,
  job_line_id UUID NOT NULL REFERENCES job_lines(job_line_id),
  qty_shipped NUMERIC(14,3) NOT NULL
);

CREATE TABLE invoices (
  invc_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  customer_id UUID NOT NULL REFERENCES customers(customer_id),
  invoice_no TEXT NOT NULL,
  invoice_date DATE NOT NULL,
  status TEXT NOT NULL,
  terms_code TEXT,
  UNIQUE (tenant_id, invoice_no)
);

CREATE TABLE invoice_lines (
  iline_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  invc_id UUID NOT NULL REFERENCES invoices(invc_id) ON DELETE CASCADE,
  job_line_id UUID REFERENCES job_lines(job_line_id),
  sline_id UUID REFERENCES shipment_lines(sline_id),
  qty NUMERIC(14,3) NOT NULL,
  unit_price NUMERIC(14,4) NOT NULL,
  tax NUMERIC(14,2) NOT NULL DEFAULT 0
);

CREATE TABLE payments (
  pay_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  invc_id UUID NOT NULL REFERENCES invoices(invc_id),
  amount NUMERIC(14,2) NOT NULL,
  method TEXT,
  ts TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 10) Maintenance
CREATE TABLE maintenance_plans (
  mp_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  machine_id UUID NOT NULL REFERENCES machines(machine_id),
  interval_days INTEGER,
  interval_hours INTEGER,
  checklist_json JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE maintenance_work_orders (
  mwo_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  machine_id UUID NOT NULL REFERENCES machines(machine_id),
  status TEXT NOT NULL,
  opened_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_ts TIMESTAMPTZ,
  notes TEXT
);

CREATE TABLE downtime_events (
  de_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
  machine_id UUID NOT NULL REFERENCES machines(machine_id),
  start_ts TIMESTAMPTZ NOT NULL,
  end_ts TIMESTAMPTZ,
  reason_code TEXT,
  cost_est NUMERIC(14,2)
);

CREATE INDEX idx_jobs_tenant_status ON jobs (tenant_id, status);
CREATE INDEX idx_job_ops_machine_status ON job_ops (machine_id, status);
CREATE INDEX idx_audit_entity ON audit_log (tenant_id, entity_type, entity_id);
CREATE INDEX idx_events_entity ON system_events (tenant_id, entity_type, entity_id, ts DESC);
CREATE INDEX idx_schedule_machine_time ON schedule_slots (machine_id, start_ts, end_ts);
