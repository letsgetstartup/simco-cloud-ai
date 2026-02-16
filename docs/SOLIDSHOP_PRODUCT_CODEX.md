# SolidShop AI — Product Codex (JobBOSS-Style CNC ERP)

## Legal and IP Notice
Build **JobBOSS-like parity by outcomes and workflows**, but do **not** copy JobBOSS UI assets, proprietary text, internal schema names, or documentation verbatim. Use original naming, original UX, and equivalent capabilities based on public ERP patterns and internal shop requirements.

## 1) Product Vision
SolidShop AI is an ERP for small and midsize CNC job shops across the lifecycle:
**Lead/RFQ → Quote → Job → Traveler/Routing → Scheduling → Time/Material Capture → Quality → Shipping → Invoicing → Purchasing/Inventory/Tool Crib → Maintenance**.

### Outcomes
- Replace spreadsheet-first workflows.
- Improve on-time delivery, gross margin, machine utilization, and cash velocity.
- Preserve traceability between quote assumptions and actual job outcomes.

## 2) Reference Architecture
- Frontend: React (production) / Streamlit (MVP).
- API: FastAPI or Node with clear domain services.
- Database: PostgreSQL as system-of-record; optional Firestore for event streaming and realtime views.
- Eventing: Pub/Sub/Kafka for machine state and workflow events.
- AI Gateway: Gemini/OpenAI with tenant-scoped logging and guardrails.
- Security: JWT + RBAC, optional SSO, row-level tenant security.

### NFRs
- Auditability on every write operation.
- Referential integrity with strict FK usage.
- P95 latency target under 500ms for transactional screens.
- Encryption in transit and at rest.
- Multi-tenant isolation via `tenant_id` on all business entities.

## 3) Functional Modules
- CRM & Quoting
- Job Management (Traveler + Routing + WIP)
- Finite Scheduling and Dispatch
- Inventory & Tool Crib
- Purchasing & Receiving
- Quality (Inspection, NCR, CAPA)
- Shipping & Invoicing
- Maintenance
- Admin (Users, Roles, Policies)

## 4) Core Workflow Requirements
1. RFQ → Quote → Approval → Convert to Job
2. Release Job → Generate Traveler → Finite schedule operations
3. Clock setup/run → Update WIP → Inspection → Completion
4. Issue materials/tools and track consumption
5. Shipment → Invoice → Payment receipt
6. PO creation → Receiving → Inventory update
7. NCR → CAPA → Closure
8. PM due → Maintenance work order → Closure and schedule impact

## 5) Standard Status Catalog
- Quotes: Draft, Sent, Won, Lost, Expired, Voided
- Jobs: Draft, Released, In Process, On Hold, Complete, Closed
- Operations: Not Started, Queued, Setup, Running, Inspection, Done, Blocked
- POs: Draft, Sent, Partially Received, Received, Closed, Cancelled
- Shipments: Draft, Packed, Shipped, Cancelled
- Invoices: Draft, Posted, Paid, Partially Paid, Void
- NCR: Open, Contained, Dispositioned, Closed
- CAPA: Open, In Progress, Verified, Closed

## 6) AI Layer
### Module agents
Each agent must return:
1. Diagnosis
2. Prioritized actions
3. KPI impact estimate
4. Follow-up questions

### Orchestrator
Input: module outputs + KPI goals + constraints.
Output: 30/60/90 plan with owners, dependencies, and measurable targets.

### Guardrails
- Mask sensitive financial and personal fields.
- Persist prompts, tool calls, and responses with tenant scoping.
- Human approvals required for schedule overrides, invoice updates, vendor switching, and CAPA disposition changes.

## 7) Reporting Baseline
- Executive scorecard (OTD, utilization, win rate, scrap/rework, invoice lag, cash collected)
- WIP aging
- Job estimate vs actual variance
- Dispatch list by machine/cell
- Late/at-risk jobs
- Tool stockout risk
- Vendor OTD/quality
- NCR summary by part/customer/machine

All reports must support filters, drill-down, and CSV export.

## 8) Definition of JobBOSS-style Parity
SolidShop AI reaches parity when the platform can:
- Quote with operation-level costing and convert to executable jobs.
- Track traveler sequencing with labor capture and WIP transitions.
- Schedule with finite machine capacity and dispatch queues.
- Manage inventory, tools, purchasing, and receiving.
- Run quality workflows (inspection, NCR, CAPA).
- Ship and invoice with full traceability.
- Produce costing variance and WIP aging.
- Enforce RBAC and immutable audit trails.
