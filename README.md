# Governed Document Classification

An evidence-based classifier for unstructured business documents, built so an organization can find out what is in its file shares without letting automation move, relabel or delete anything on its own.

This repository is the classification core of a larger document-governance program I led: inventory a Microsoft 365 file estate, extract text, classify every document, flag exact duplicates, and stage the results for human review before any routing or sensitivity labeling. The surrounding platform (inventory, extraction, database and labeling services) is described in [docs/architecture.md](docs/architecture.md). The engine, rules and tests are here.

## Why it exists

Most AI-classification projects fail the trust test, not the accuracy test. Legal, finance and compliance owners will not accept a model that silently moves or labels files. This engine was designed around the opposite assumption:

- **Recommend, never act.** The engine proposes a class, a business function and a destination. Nothing is moved, renamed, relabeled or deleted. The output records `filesMoved: 0`, `sourceMutations: 0` and `sensitivityChanges: 0`, and the tests enforce it.
- **Show the evidence.** Every decision lists the signals that supported it, the signals that contradicted it and the rule that fired, so a reviewer can see why, not just what.
- **Route doubt to people.** Anything below the high-confidence threshold, with conflicting evidence, with incomplete text extraction, or that duplicates another file is sent to human review.
- **Version everything.** Rules live in configuration (`config/rules.json`) with their own version, separate from the engine version, so every result can be traced to the exact rule set that produced it.

## How it decides

1. **Text evidence first.** Each rule names the signals it requires (for example an invoice number, an invoice date and an amount due), supporting signals that add confidence, and contradictory signals that subtract it (quote language on an "invoice").
2. **Confidence bands.** Scores of 85 and above are HIGH, 60 to 84 MEDIUM, and below 60 LOW. Only HIGH, uncontested, fully extracted documents can be machine-classified.
3. **Competing rules.** If two incompatible classes score within 10 points of each other, the winner is penalized and usually goes to review.
4. **Folder names are weaker evidence.** Paths can add a small bonus to a class that the text already supports, but they can never choose the class, satisfy a required signal or, on their own, reach HIGH.
5. **Search tags, not decisions.** Retailers, products, brands, partners, year and lifecycle (draft, final, archive) are pulled from paths as metadata and never change the class.
6. **Exact duplicates.** Files with identical content hashes are grouped, the canonical copy is identified, and every copy keeps the context of the others. Nothing is dropped.

## Results from the pilot program

The rules were tuned on a fixed, human-approved pilot set of 100 real documents, re-run unchanged after every rule revision:

| Rule set | Classified | HIGH confidence | Unknown or Other |
|---|---:|---:|---:|
| v1 | 63 of 100 | 52 | 37 |
| v2.1 | 99 of 100 | 63 | 1 |

Throughout the pilot, zero files were moved, zero sensitivity labels were changed by automation, and exact-duplicate groups were flagged for review rather than removed. The same controls were then carried into a 500-document pilot and an estate-wide inventory with a six-figure file count.

Pilot data is not included. Everything in `examples/` is synthetic.

## Try it

Requires Python 3.10 or later. No third-party packages are needed for the engine; `openpyxl` is optional for the Excel review workbook.

```bash
python examples/run_demo.py          # classify the synthetic sample set
python -m unittest -v                 # run the guardrail tests
```

Sample output:

```
INV-20418.pdf                              Invoice                100 HIGH   Review Required
Master Supply Agreement - Tailspin.docx    Agreement              100 HIGH   Machine Classified
Protein Shake Sell Sheet 2025.pdf          Sell Sheet              90 HIGH   Machine Classified
Q3 Line Review.pptx                        Presentation            90 HIGH   Machine Classified
Quote 7781.pdf                             None                    55 LOW    Review Required
scan_0042.tif                              Media Asset             70 MEDIUM Review Required
INV-20418 (copy).pdf                       Invoice                 95 HIGH   Review Required
Records Retention Policy.docx              Policy                  90 HIGH   Machine Classified
```

The invoice and its copy go to review because they are exact duplicates; the quote goes because it carries contradictory evidence; the scan goes because its text extraction was incomplete. The full review report is written to `examples/sample_report.md`.

## Repository layout

```
classifier/engine.py         Pure classification functions (no file, network or database I/O)
config/rules.json            Versioned rules, thresholds, routing and path-evidence policy
examples/                    Synthetic extraction input, demo script and sample report
tests/test_engine.py         Guardrail and behavior tests
docs/architecture.md         The surrounding Microsoft 365 / Azure platform
docs/governance.md           Controls, review workflow and rollout gates
```

## About

Designed and directed by [Steven E. Sarafian](https://www.linkedin.com/in/steven-e-sarafian), technology executive focused on business systems, data platforms and governed AI. Built with an AI-assisted engineering workflow under my direction. Company names in the examples (Contoso, Fabrikam, Northwind, Tailspin) are fictional.
