# AB Logistics OS — Technical Pitch Deck

## 1) The Problem

- Fragmented logistics stack: routing, invoicing, reconciliation, ESG and compliance split across tools.
- Fiscal risk under Ley Antifraude: broken invoice traceability, weak integrity controls, audit friction.
- Opaque ESG reporting: delayed CO2 calculations, non-standard fleet emissions criteria, low board visibility.
- Financial inconsistency risk: mixed rounding behaviors and non-deterministic invoice math across systems.

---

## 2) The Solution — AB Logistics OS

**One-stop búnker** for:

- Financial operations
- Sustainability intelligence
- Legal/fiscal compliance

Single tenant-aware platform (`empresa_id` scoped) with deterministic data flows from route execution to fiscal evidence.

---

## 3) Core Pillars

### Fiscal Integrity

- VeriFactu invoice chaining with `SHA-256` (`hash_anterior` -> `hash_registro`).
- XAdES-BES signing flow available via fiscal core (`sign_invoice_xades`) including `xades:SignedProperties`.
- Immutable fiscal trail fields (`num_factura`, `hash_*`) aligned with antifraud evidence requirements.

### Financial Precision

- Decimal-only math engine in `backend/app/core/math_engine.py`.
- Monetary quantization at 2 decimals with `ROUND_HALF_EVEN` (banking-safe rounding).
- Deterministic totals: `base + IVA (+ RE) = total` with controlled cent-level adjustments.

### Sustainability

- Real-time CO2 estimation pipeline by route/fleet context.
- Euro engine uses fleet emission profile (`normativa_euro`) to modulate footprint.
- ESG monthly and audit-ready outputs over facturado operations.

### AI / Automation

- LogisAdvisor: contextual Q&A over operational, financial and ESG state.
- Automated bank reconciliation service against invoice references and amount rules.
- Streaming advisory UX + operational quick actions for finance/traffic roles.

---

## 4) Product Architecture Snapshot

- **Data Layer**: Supabase/Postgres multi-tenant model with strict `empresa_id` scoping.
- **Fiscal Layer**: hash chain + XML signature + QR/verification metadata.
- **Finance Layer**: EBITDA and margin computation over invoice/gasto net values.
- **Ops Layer**: Maps-driven route distance/time validation and fleet assignment.
- **Intelligence Layer**: advisor chat, reconciliation automation, KPI exposure.

---

## 5) Traction — Sandbox (`DEMO-LOGISTICS-001`)

Source: `backend/scripts/seed_sandbox.py`

- Fleet seeded: **10 trucks** (Euro III-IV-V-VI mix, fallback-safe constraints).
- Routes seeded: **50/50 validated** through Maps API flow (**100% matched routes dataset**).
- Invoices seeded: **100** with VeriFactu sequential SHA-256 chaining.
- Fiscal chain check: `verifactu_chain_ok=true` in seeding output.
- Reconciliation showcase:
  - **10 paid-like bank transactions**
  - **5 pending/noise bank transactions**
  - Automated reconciliation execution included in seed flow.
- Financial scenario:
  - Target EBITDA margin set to **18%** (inside 15–20% band).
  - Expense seeding calibrated from net invoice revenue to preserve realistic operating margin.

---

## 6) Investment / Client Value

- Compliance-by-design reduces antifraud and audit exposure.
- Deterministic financial math reduces reporting disputes and closes faster.
- Unified logistics + fiscal + ESG stack lowers integration and operating complexity.
- Automation layer (advisor + reconciliation) scales back-office throughput without headcount-linear growth.
