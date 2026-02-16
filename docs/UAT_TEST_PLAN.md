# SolidShop AI — UAT Test Plan

## Scope
This UAT validates JobBOSS-style outcome parity for CNC job-shop workflows.

## Test Data Prerequisites
- One tenant with users in roles: Sales, Planner, Shop Supervisor, Buyer, Quality Engineer, AR Clerk, Maintenance Tech.
- Seeded records: 2 customers, 2 vendors, 5 items, 5 materials, 10 tools, 3 machines, 2 employees.

## End-to-End Scenarios

### UAT-01 RFQ to Quote to Job Conversion
1. Create RFQ and RFQ line.
2. Generate quote with operation-level estimate.
3. Approve quote.
4. Convert to job.

**Expected:** Job, job line, and operations are created with traceability to quote assumptions.

### UAT-02 Job Release to Scheduling
1. Release the job.
2. Run finite scheduler.
3. Review dispatch queue by machine.

**Expected:** No machine capacity overrun; operations are assigned in available windows.

### UAT-03 Time and WIP Updates
1. Start setup and run timecards.
2. Complete operation and move to inspection status.
3. Record scrap event.

**Expected:** WIP quantities and operation statuses update correctly; event timeline and audit entries exist.

### UAT-04 Material Issue and PO Receiving
1. Issue required material to job.
2. Create PO for shortage.
3. Receive PO line.

**Expected:** Inventory on-hand and allocated balances reconcile before and after receipt.

### UAT-05 Quality and CAPA
1. Log failed inspection and create NCR.
2. Create CAPA action and assign owner.
3. Close CAPA with verification.

**Expected:** NCR and CAPA lifecycle transitions are captured and reportable.

### UAT-06 Shipment and Invoicing
1. Ship completed quantity.
2. Auto-create invoice from shipment.
3. Apply payment.

**Expected:** Shipment and invoice trace back to job lines; invoice status moves to paid/partially paid based on payment.

### UAT-07 Preventive Maintenance Impact
1. Mark PM as due and open maintenance work order.
2. Register downtime event.
3. Re-run scheduling.

**Expected:** Machine availability reduction appears in scheduling outcomes and bottleneck metrics.

### UAT-08 AI Module Agent and Orchestrator
1. Run module agent for Scheduling and Inventory.
2. Run orchestrator with OTD and margin targets.

**Expected:** AI outputs diagnosis, actions, KPI impact estimate, follow-up questions, and a 30/60/90 cross-module plan.

## Exit Criteria
- All UAT scenarios pass.
- No Severity-1 or Severity-2 defects open.
- Audit log entries appear for all write transitions.
- Role-based permissions block unauthorized transitions.
