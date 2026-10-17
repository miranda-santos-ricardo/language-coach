"""Print reproducible offline fixture results. No inference or API calls."""
import argparse
import json
from pathlib import Path

from app.evaluation.deterministic import evaluate_dataset, load_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline language-coach evaluation fixture report")
    default = Path(__file__).resolve().parents[2] / "evaluations" / "coach_cases_v1.json"
    parser.add_argument("--dataset", type=Path, default=default)
    args = parser.parse_args()
    cases = load_dataset(args.dataset)
    results = evaluate_dataset(cases)
    report = {
        "dataset": args.dataset.name,
        "mode": "synthetic_offline_fixture_checks",
        "total": len(results),
        "passed": sum(r.passed for r in results),
        "failed": sum(not r.passed for r in results),
        "cases": [{"id": r.case_id, "passed": r.passed, "failures": list(r.failures)} for r in results],
        "disclaimer": "Not a measure of LLM language quality, security, or generalization.",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
