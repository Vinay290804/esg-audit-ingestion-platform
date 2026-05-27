# Tradeoffs

1. I did not build live SAP, utility, or Concur integrations.

   The prototype focuses on ingestion contracts and analyst review. Real connectors would require credentials, tenant-specific mappings, retry behavior, and support processes that cannot be honestly validated with fabricated access.

2. I did not build full emissions-factor governance.

   The app uses fixed demo factors to keep the assignment centered on source normalization and auditability. A production system needs factor libraries by region, year, category, methodology, and approval status.

3. I did not implement user accounts and role permissions.

   Django auth is available, but the review mechanics matter more for this prototype. In production, importers, reviewers, and auditors should have separate permissions, and audit locks should be enforced below the view layer too.
