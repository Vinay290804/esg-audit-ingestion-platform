# Data Model

The prototype centers on `NormalizedActivity`, not on source-specific tables. SAP, utility, and travel rows all become auditable activity rows with scope, normalized units, source reference, flags, review status, and estimated emissions.

## Core entities

- `Tenant`: company boundary. Every source, facility, batch, and activity belongs to a tenant so rows cannot mix across clients.
- `Facility`: tenant-owned lookup for SAP plant codes, utility facility codes, and employee home office codes.
- `SourceSystem`: the configured source of truth for a tenant, such as SAP S/4, utility portal export, or Concur extract. It records the source type and extraction mode.
- `IngestionBatch`: one import attempt, with filename, source, importer, imported timestamp, and row counts for accepted, warning, and failed records.
- `RawRecord`: immutable-ish source payload per row. It keeps the exact parsed row, row number, source row id, validation errors, and parser warnings.
- `NormalizedActivity`: the analyst-facing row. It stores Scope 1/2/3 category, facility mapping, activity date or billing period, original quantity/unit, normalized quantity/unit, estimated kg CO2e, source reference, suspicious reasons, and review state.
- `AuditEvent`: append-only review log for `ingested`, `approve`, `reject`, and `lock` actions, including before/after snapshots.

## Why this shape

The hard part is source variability, so source-specific records are preserved in `RawRecord.payload` while the review workflow operates on a stable normalized table. Analysts need one queue, not three separate apps.

`NormalizedActivity.raw_record` is one-to-one because this prototype treats each source row as one activity. In a fuller system, that would become one-to-many for rows that need allocation or splitting.

## Requirements coverage

- Multi-tenancy: every operational table is scoped through `Tenant`.
- Scope categorization: SAP fuel is Scope 1, purchased electricity is Scope 2, and business travel is Scope 3.
- Source of truth: `SourceSystem`, `IngestionBatch`, `RawRecord.source_row_id`, and `NormalizedActivity.source_reference` preserve where a row came from and when it was imported.
- Unit normalization: original `quantity`/`unit` and normalized `normalized_quantity`/`normalized_unit` are stored side by side.
- Audit trail: raw payloads remain available, and `AuditEvent` records each review state transition. Locked rows cannot be modified through the API.
