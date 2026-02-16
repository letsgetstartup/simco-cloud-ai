# SolidShop AI — UAT Test Plan (JobBOSS-Style Outcome Parity)

## 1. Purpose
Validate that **SolidShop AI** achieves **JobBOSS-style operational parity by outcomes** for CNC job-shop workflows across quoting, job control, routing/travelers, finite scheduling, inventory/purchasing, quality, shipping/invoicing, maintenance, and auditability.

## 2. Scope

### In Scope
- RFQ → Quote → Approval → Job Conversion (including operation-level estimates)
- Job Release → Routing/Traveler creation → Finite scheduling → Dispatch
- Time capture (setup/run/indirect) → WIP movement → Scrap handling
- Material/tool issue, allocation, shortages, PO and receiving
- Inspection → NCR → CAPA lifecycle
- Shipping → Invoicing → Payment application
- Preventive maintenance and downtime impact on schedule
- RBAC/permissions enforcement and audit trail
- Standard reports and drill-down traceability

### Out of Scope (unless explicitly enabled)
- Accounting sync (QB/Xero)
- MTConnect/OPC-UA live machine connectivity
- Advanced MRP beyond “MRP-lite”

## 3. Roles & Responsibilities
- **UAT Lead**: Owns execution, defect triage, sign-off
- **Business SMEs**: Sales, Planner, Shop Supervisor, Buyer, Quality, AR, Maintenance
- **QA Analyst**: Test evidence, repeatability, regression checks
- **Dev Support**: Fixes and hot patches

## 4. UAT Environment & Configuration
- Environment: `uat.solidshop.ai`
- Single tenant: `SolidShopDemo`
- Timezone: configurable (default: America/Chicago)
- Currency: USD
- Document numbering enabled:
  - Quote: `Q-YYYY-#####`
  - Work Order: `WO-#####`
  - PO: `PO-#####`
  - Invoice: `INV-#####`

## 5. Test Data Prerequisites

### Users (minimum)
- Sales User (role: Sales)
- Planner User (role: Planner)
- Shop Supervisor (role: Supervisor)
- Buyer (role: Buyer)
- Quality Engineer (role: Quality)
- AR Clerk (role: AR)
- Maintenance Tech (role: Maintenance)

### Seeded Masters (minimum)
- Customers: 2 (net terms, ship-to addresses)
- Vendors: 2 (lead times, rating)
- Items: 5 (part_no, rev, default routing template)
- Materials: 5 (spec, form, uom)
- Tools: 10 (min_qty, vendor linkage)
- Machines: 3 (capacity calendars, shift assignment)
- Employees: 2 (rates)
- Reason codes: scrap reasons, downtime reasons, NCR dispositions

### Baseline Inventory
- At least one material intentionally below requirement to trigger shortage scenario
- At least one tool below safety stock to trigger reorder suggestion

## 6. Evidence Requirements (per test case)
Each test case must capture:
- Screenshots of key screens
- Generated document numbers (quote/job/PO/invoice)
- Audit log entries (who/when/what)
- Report outputs (CSV/PDF where applicable)
- Calculations verifying quantities/minutes/costs

## 7. Severity Definitions
- **S1 Critical**: financial or traceability corruption, data loss, unauthorized access, cannot complete core workflow
- **S2 High**: incorrect totals/costs/schedule, broken role permissions, cannot ship/invoice
- **S3 Medium**: UI defects, minor validation issues, report formatting
- **S4 Low**: cosmetic, copy, non-blocking

## 8. End-to-End Scenarios

### UAT-01 RFQ → Quote → Approval → Convert to Job
**Actor(s):** Sales  
**Preconditions:** Customer exists, item exists, routing template exists (optional)

**Steps:**
1. Create RFQ with 1 RFQ line (qty, due date).
2. Create Quote from RFQ.
3. Add Quote Line with unit price, lead time days, and estimate breakdown (material, labor, overhead, outside).
4. Add Quote Operations (seq 10/20/30) with setup/run minutes.
5. Approve Quote.
6. Convert Quote → Job.

**Expected Results:**
- Job created with `WO-#####`
- Job Line created with correct qty/rev and linkage to quote_line
- Job Ops created (seq preserved) with planned minutes
- “Estimate vs Actual” baseline stored for variance reporting
- Audit: approval + conversion entries exist
- Event timeline records conversion and job release readiness

**Pass Criteria:** All entity counts match (1 job, 1 line, N ops) and traceability links present.

### UAT-02 Job Release → Finite Scheduling → Dispatch Queue
**Actor(s):** Planner

**Steps:**
1. Release job (status transitions to Released/In Process).
2. Run scheduler for the next 10 working days.
3. Review Gantt or machine schedule.
4. Open Dispatch Queue per machine.

**Expected Results:**
- No schedule slot exceeds machine daily capacity
- Ops are placed within available windows considering shift calendars
- Dispatch queue ranks jobs by priority/due date rules
- Locked slots remain locked if applied

**Pass Criteria:** Capacity constraints enforced + dispatch queue visible for each machine.

### UAT-03 Time Capture → WIP Updates → Scrap
**Actor(s):** Shop Supervisor

**Steps:**
1. Start setup timecard for Op 10 (employee A).
2. End setup; start run timecard.
3. Mark op complete → status moves to Inspection.
4. Record scrap event (qty + reason).
5. Verify job line `qty_completed` and `scrap_qty`.

**Expected Results:**
- Timecards compute minutes correctly and attach to job_op
- WIP status transitions create audit + system events
- Scrap reduces effective completed qty and updates costing bucket
- WIP screen shows accurate quantities and op states

**Pass Criteria:** Totals reconcile: `qty_ordered = qty_completed + remaining + scrap` (per policy).

### UAT-04 Material Issue → Shortage → PO → Receiving
**Actor(s):** Buyer + Supervisor

**Steps:**
1. From job material requirements, issue available material.
2. Trigger shortage for remaining qty (below required).
3. Create PO for shortage qty with vendor lead time.
4. Receive PO line partially, then fully.

**Expected Results:**
- Inventory moves recorded (issue, receipt)
- On-hand, allocated, and issued reconcile at each step
- Job material requirement shows required, issued, and remaining quantities
- PO status transitions: Draft → Sent → Partially Received → Received/Closed
- Audit exists for inventory movements and PO changes

**Pass Criteria:** No negative inventory; allocations behave predictably.

### UAT-05 Inspection → NCR → CAPA
**Actor(s):** Quality Engineer

**Steps:**
1. Create inspection record for op in Inspection status.
2. Record at least one failed measurement.
3. Create NCR from failed inspection with disposition.
4. Create CAPA action, assign owner, set due date.
5. Verify CAPA closure requires verification step.

**Expected Results:**
- Inspection results stored and reportable
- NCR created with linkage to job/job_op and cost estimate
- CAPA lifecycle enforced: Open → In Progress → Verified → Closed
- Reports show NCR counts and CAPA status by period

**Pass Criteria:** Lifecycle rules enforced and traceability complete.

### UAT-06 Ship → Invoice → Payment
**Actor(s):** AR Clerk

**Steps:**
1. Create shipment for completed quantity; pack and ship.
2. Auto-create invoice from shipment.
3. Post invoice.
4. Apply partial payment then full payment.

**Expected Results:**
- Shipment lines trace to job lines and reduce ready-to-ship quantities
- Invoice lines trace to shipment/job and compute totals correctly
- Invoice status: Draft → Posted → Partially Paid → Paid
- A/R reports reflect balances

**Pass Criteria:** Financial totals consistent and traceable.

### UAT-07 Preventive Maintenance → Downtime → Schedule Impact
**Actor(s):** Maintenance Tech + Planner

**Steps:**
1. Mark PM due; open maintenance work order for Machine 1.
2. Record downtime window (2 hours) with reason code.
3. Re-run scheduler.

**Expected Results:**
- Machine availability reduced for downtime window
- Scheduling shifts impacted ops to other windows/machines (if allowed)
- Bottleneck metrics update; late risk recalculated
- Maintenance work order lifecycle captured and auditable

**Pass Criteria:** Scheduling respects downtime.

### UAT-08 AI Module Agents + Orchestrator
**Actor(s):** Planner + Supervisor

**Steps:**
1. Run Scheduling agent: “Which operations risk missing due date and why?”
2. Run Inventory agent: “Which tools/materials risk stockout in next 2 weeks?”
3. Run Orchestrator with target: “Increase throughput 12% next quarter without headcount.”

**Expected Results:**
- Agents output diagnosis, prioritized actions, KPI impact estimate, and follow-up questions
- Orchestrator outputs 30/60/90 plan, module owners, dependencies/risks, and measurable targets
- AI output references actual data fields (no hallucinated entities)

**Pass Criteria:** Output format compliance + data-grounded recommendations.

## 9. Negative & Control Tests (Mandatory)

### UAT-09 RBAC / Unauthorized Actions
- Sales cannot post invoices
- Buyer cannot close CAPA
- Supervisor cannot change vendor scorecard

**Expected:** Action blocked with clear message; audit logs attempted action.

### UAT-10 Invalid State Transitions
- Cannot ship when job not complete
- Cannot close job with open NCR (if policy requires)
- Cannot receive PO beyond ordered quantity (unless over-receipt enabled)

**Expected:** Validation prevents transition.

### UAT-11 Data Integrity
- Deleting a job with timecards is blocked (or soft-delete only)
- Orphan ops cannot exist without job_line

**Expected:** DB constraints and service validation enforce integrity.

## 10. Exit Criteria
- All UAT-01…UAT-11 pass
- No open S1/S2 defects
- Audit log entries exist for all write transitions
- Role-based permissions verified by negative tests
- Standard reports available and consistent with transactional data
- Sign-off by SMEs + UAT Lead
