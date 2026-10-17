"""CLI: offline by default. Live inference requires a deliberate double opt-in."""
import argparse
import json
import os
from pathlib import Path

from app.evaluation.deterministic import load_dataset
from app.evaluation.quality import QualityRunSettings, run_quality_evaluation

DATASET = Path(__file__).resolve().parents[2] / "evaluations" / "coach_cases_v1.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Language Coach quality checks (offline by default)")
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--mode", choices=("dry-run", "live"), default="dry-run")
    parser.add_argument("--max-cases", type=int, default=14)
    parser.add_argument("--allow-paid-api-calls", action="store_true", help="Required only for live mode")
    parser.add_argument("--output", type=Path, help="Optional report JSON path (no learner text stored)")
    args = parser.parse_args(argv)
    settings = QualityRunSettings(mode=args.mode, max_cases=args.max_cases)

    # Validate both consent gates BEFORE loading clients, creating connections,
    # or making any possible paid request.
    authorized = (args.allow_paid_api_calls and os.environ.get("LANGUAGE_COACH_EVAL_LIVE") == "YES")
    if args.mode == "live" and not authorized:
        parser.error("Live evaluation disabled: requires --allow-paid-api-calls AND LANGUAGE_COACH_EVAL_LIVE=YES")
    cases = load_dataset(args.dataset)
    provider = None
    if args.mode == "live":
        from app.services.conversation_dependencies import get_conversation_llm
        provider = get_conversation_llm()

    report = run_quality_evaluation(cases, settings=settings, provider=provider, live_authorized=authorized)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["failed"] == 0 and report["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
