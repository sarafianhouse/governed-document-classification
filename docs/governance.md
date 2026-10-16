# Governance controls

## Guardrails built into the engine

| Control | Where it is enforced |
|---|---|
| No file moves, renames, deletions or label changes | `run_classification` output (`filesMoved`, `sourceMutations`, `sensitivityChanges` are always 0); `tests/test_engine.py` |
| Sensitivity is set by people, not the model | Every result carries `sensitivitySource: "Human Reviewed"`; the run fails if any result differs |
| Exact population accounting | A run fails unless it returns exactly one result per document in the approved manifest |
| Evidence on every decision | Each result lists supporting and contradictory evidence plus the rules that fired |
| Doubt goes to people | Review is required below HIGH confidence, on conflicting evidence, on incomplete extraction, on folder-only hints and on exact duplicates |
| Unclassified documents never get a business destination | They route to `Intake / Exception Review` |
| Folder names cannot overrule content | Path evidence adds limited points and never picks the winning class |

## Rollout gates

1. **Discovery.** Read-only inventory of the full estate. Output: counts, sizes, duplicate candidates. No changes.
2. **Pilot 100.** A fixed set of real documents, approved by a person for the pilot. Rules are tuned until results are stable.
3. **Pilot 500.** A larger fixed set, using the same controls, to confirm the rules generalize.
4. **Reviewed routing.** Approved results are routed in batches with a written rollback.
5. **Labeling.** Sensitivity and retention labels are applied in a scoped pilot first, then expanded by policy.

Each gate needs an explicit decision from the business owner before the next one starts.
