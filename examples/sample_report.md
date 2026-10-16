# Classification Pilot 8 Results

- Documents accounted for: 8/8
- Classified: 7
- HIGH / MEDIUM / LOW: 6 / 1 / 1
- Review required: 4
- Unknown/Other: 1
- Processing failures: 0
- Extraction skips: 0
- Exact duplicate groups / documents flagged: 1 / 2
- Sensitivity: General for all 8 (Human Reviewed)
- Files moved: 0; source mutations: 0

## ContentClass

| Value | Count |
|---|---:|
| Agreement | 1 |
| Invoice | 2 |
| Media Asset | 1 |
| Policy | 1 |
| Presentation | 1 |
| Sell Sheet | 1 |
| Unknown | 1 |

## BusinessFunction

| Value | Count |
|---|---:|
| Administrative | 1 |
| Finance | 2 |
| Legal | 1 |
| Marketing | 1 |
| Sales | 3 |

## Proposed routing

| Value | Count |
|---|---:|
| Contracts | 1 |
| Documents | 3 |
| Intake / Exception Review | 4 |

## Confidence bands

| Value | Count |
|---|---:|
| HIGH | 6 |
| LOW | 1 |
| MEDIUM | 1 |

## Rules fired

| Value | Count |
|---|---:|
| AGR-001 | 1 |
| CON-001 | 1 |
| COR-001 | 2 |
| INV-001 | 3 |
| MED-001 | 1 |
| MKT-001 | 1 |
| POL-001 | 1 |
| PRO-001 | 1 |
| PRS-001 | 1 |
| QUO-001 | 1 |
| RET-001 | 1 |
| SEL-001 | 1 |

## Attribute evidence frequency

| Value | Count |
|---|---:|
| agreementLanguage | 1 |
| amountDue | 2 |
| billTo | 2 |
| contractNumber | 1 |
| effectiveDate | 1 |
| governingLaw | 1 |
| invoiceDate | 2 |
| invoiceHeading | 2 |
| invoiceNumber | 3 |
| invoiceTotal | 1 |
| lineItemLanguage | 2 |
| marketingLanguage | 1 |
| mediaFileType | 1 |
| partyLanguage | 1 |
| pathContractFolder | 1 |
| pathFinanceFolder | 1 |
| pathInvoiceFolder | 1 |
| pathLegalFolder | 1 |
| pathPolicyFolder | 1 |
| pathPresentationFolder | 1 |
| pathRetailer | 1 |
| pathSellSheetFolder | 1 |
| paymentTerms | 1 |
| policyLanguage | 1 |
| presentationStructure | 1 |
| procedureLanguage | 1 |
| productIdentifier | 1 |
| quoteLanguage | 1 |
| sellSheetLanguage | 1 |
| signatureLanguage | 1 |
| subtotal | 1 |
| tax | 1 |

## Path Evidence

- Documents with any path tag (retailer, product, brand, partner or year): 4
- Retailer / product / brand / partner / year: 2 / 1 / 0 / 1 / 2
- Lifecycle tag (draft, close-out, sync conflict, ...): 0
- Class supported by folder evidence: 5
- Class suggested from folder only (always review): 0
- BusinessFunction filled from folder: 0
- ContentTopic filled from folder: 3

### Path retailers

| Value | Count |
|---|---:|
| Example Mart | 1 |
| Northwind Grocers | 1 |

### Path products

| Value | Count |
|---|---:|
| Daily Protein Shake | 1 |

### Path partners

| Value | Count |
|---|---:|
| Tailspin Logistics | 1 |

### Path period year

| Value | Count |
|---|---:|
| 2025 | 2 |

## Exceptions

| Source item | File | Candidate | Score | Reason |
|---|---|---|---:|---|
| doc-001 | INV-20418.pdf | Invoice | 100 | Exact content duplicate group; confirm duplicate handling |
| doc-005 | Quote 7781.pdf | Quote | 55 | Confidence below HIGH threshold or class not established; Conflicting evidence |
| doc-006 | scan_0042.tif | Media Asset | 70 | Confidence below HIGH threshold or class not established; Extraction status is PARTIAL |
| doc-007 | INV-20418 (copy).pdf | Invoice | 95 | Exact content duplicate group; confirm duplicate handling |

## Exact Duplicate Groups

| Group | Source item | Duplicate of | Filename |
|---|---|---|---|
| 0261cf6580a5abbab06a | doc-001 | (canonical) | INV-20418.pdf |
| 0261cf6580a5abbab06a | doc-007 | doc-001 | INV-20418 (copy).pdf |
