# Architecture

The classifier in this repository is one stage of a document-governance pipeline built on Microsoft 365 and Azure. Only the classification stage is published here; the other stages are described so the design decisions make sense.

```
SharePoint / OneDrive / Google Drive
        │  read-only (Microsoft Graph, app-only)
        ▼
1. Inventory      Azure Functions (Python) enumerate sites, libraries and files; checkpointed, resumable scans
        │
        ▼
2. Inventory DB   Azure SQL, accessed with a managed identity; one row per file, plus content hashes
        │
        ▼
3. Extraction     Native text for Office and PDF; OCR for scans and images; size thresholds and skip reasons recorded
        │
        ▼
4. Classification This repository: rules + evidence → class, confidence, business function, proposed destination
        │
        ▼
5. Human review   Review workbook and exception queue; reviewers confirm or change every flagged result
        │
        ▼
6. Governance     Only after approval: routing, Microsoft Purview sensitivity and retention labels, duplicate archiving
```

## Design decisions

| Decision | Reason |
|---|---|
| Read-only Graph access for inventory and extraction | The discovery phase cannot damage the estate, which makes it easy to approve. |
| Pure-function classifier | It can be tested without a tenant, re-run on the same input for an audit, and replaced without touching inventory or labeling. |
| Rules in versioned configuration, not code | Business owners can review the rules, and every result names the rule version that produced it. |
| Fixed pilot populations (100, then 500) | Every rule change is measured on the same documents, so improvements are real rather than sampling noise. |
| Exact-hash duplicate groups, never automatic removal | Duplicates are the biggest storage win and the biggest risk; a person confirms which copy stays. |
| Labeling is a separate, gated stage | Sensitivity and retention labels have legal effect, so they are applied only from approved review results, with a documented rollback. |
| Microsoft and Google parity | The same taxonomy and rules apply across SharePoint and Google Drive, so a hybrid company has one standard. |
