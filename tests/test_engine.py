import json
import unittest
from pathlib import Path

from classifier.engine import analyze_path, classify_document, run_classification

ROOT = Path(__file__).resolve().parent.parent
RULES = json.loads((ROOT / "config" / "rules.json").read_text())
SAMPLE = json.loads((ROOT / "examples" / "sample_extraction.json").read_text())
BY_ID = {doc["sourceItemId"]: doc for doc in SAMPLE["results"]}


class GuardrailTests(unittest.TestCase):
    def setUp(self):
        self.aggregate = run_classification(SAMPLE, RULES, expected_population=len(SAMPLE["results"]))
        self.results = {r["sourceItemId"]: r for r in self.aggregate["results"]}

    def test_never_mutates_sources_or_labels(self):
        self.assertEqual(self.aggregate["sourceMutations"], 0)
        self.assertEqual(self.aggregate["filesMoved"], 0)
        self.assertEqual(self.aggregate["sensitivityChanges"], 0)
        self.assertTrue(all(r["sensitivitySource"] == "Human Reviewed" for r in self.results.values()))

    def test_population_must_match_manifest_exactly(self):
        with self.assertRaises(ValueError):
            run_classification(SAMPLE, RULES, expected_population=len(SAMPLE["results"]) + 1)

    def test_every_decision_carries_evidence(self):
        for result in self.results.values():
            self.assertTrue(result["evidence"], result["filename"])

    def test_exact_duplicates_are_flagged_not_dropped(self):
        original, copy = self.results["doc-001"], self.results["doc-007"]
        self.assertEqual(original["duplicateGroupId"], copy["duplicateGroupId"])
        self.assertEqual(copy["duplicateOfSourceItemId"], "doc-001")
        self.assertTrue(original["humanReviewRequired"] and copy["humanReviewRequired"])
        self.assertEqual(len(self.results), len(SAMPLE["results"]))

    def test_conflicting_evidence_goes_to_review(self):
        quote = self.results["doc-005"]
        self.assertTrue(quote["humanReviewRequired"])
        self.assertTrue(quote["contradictoryEvidence"])
        self.assertEqual(quote["proposedDestination"], "Intake / Exception Review")

    def test_incomplete_extraction_always_needs_review(self):
        self.assertTrue(self.results["doc-006"]["humanReviewRequired"])

    def test_clean_documents_are_machine_classified(self):
        self.assertEqual(self.results["doc-002"]["contentClass"], "Agreement")
        self.assertEqual(self.results["doc-008"]["classificationStatus"], "Machine Classified")


class PathEvidenceTests(unittest.TestCase):
    def test_folder_names_cannot_pick_the_class(self):
        doc = dict(BY_ID["doc-008"], sourcePath="Finance/Invoices/Records Retention Policy.docx")
        self.assertEqual(classify_document(doc, RULES)["contentClass"], "Policy")

    def test_folder_only_hint_is_capped_below_high(self):
        doc = {"sourceItemId": "x", "filename": "untitled.pdf", "sourcePath": "Legal/Contracts/untitled.pdf",
               "extractionStatus": "SUCCESS", "fullText": "", "attributes": {}}
        result = classify_document(doc, RULES)
        self.assertTrue(result["pathClassOnly"])
        self.assertNotEqual(result["contentClassConfidenceBand"], "HIGH")
        self.assertTrue(result["humanReviewRequired"])

    def test_tags_are_search_metadata(self):
        tags = analyze_path(BY_ID["doc-003"], RULES)["tags"]
        self.assertIn("Northwind Grocers", tags["retailers"])
        self.assertEqual(tags["periodYear"], 2025)


if __name__ == "__main__":
    unittest.main()
