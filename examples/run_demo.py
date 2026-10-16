"""Classify the synthetic sample set and write a Markdown review report.

Run from the repository root:  python examples/run_demo.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from classifier.engine import build_markdown_report, run_classification

ROOT = Path(__file__).resolve().parent.parent

rules = json.loads((ROOT / "config" / "rules.json").read_text())
extraction = json.loads((ROOT / "examples" / "sample_extraction.json").read_text())
aggregate = run_classification(extraction, rules, expected_population=len(extraction["results"]))

for r in aggregate["results"]:
    print(f"{r['filename']:<42} {str(r['contentClass']):<22} {r['contentClassConfidenceScore']:>3} "
          f"{r['contentClassConfidenceBand']:<6} {r['classificationStatus']}")

out = ROOT / "examples" / "sample_report.md"
out.write_text(build_markdown_report(aggregate))
print(f"\nReport written to {out.relative_to(ROOT)}")
