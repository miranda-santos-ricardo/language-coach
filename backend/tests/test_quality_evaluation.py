"""No test may create a real OpenAI client or spend API credits."""
import json
from pathlib import Path

import pytest

from app.evaluation.deterministic import load_dataset
from app.evaluation.quality import QualityRunSettings, run_quality_evaluation
from app.evaluation.quality_report import main
from app.services.llm import LLMResult

DATA = Path(__file__).resolve().parents[1] / "evaluations" / "coach_cases_v1.json"


class MockProvider:
    def __init__(self, outputs):
        self.outputs = outputs
        self.calls = 0

    def generate(self, *, instructions, messages):
        self.calls += 1
        assert "Return only one valid JSON object" in instructions
        assert messages[-1].role == "user"
        content = self.outputs[self.calls - 1]
        return LLMResult(content=content, model="mock-model", input_tokens=110, output_tokens=90)


def test_dry_run_passes_all_reference_cases_and_skips_provider():
    report = run_quality_evaluation(load_dataset(DATA), settings=QualityRunSettings())
    assert report["mode"] == "dry-run" and report["total"] == 14
    assert report["passed"] == 14 and report["failed"] == report["errors"] == 0
    assert all(r["subjective_quality"] == "not_assessed" for r in report["cases"])


def test_live_requires_authorization_and_provider():
    with pytest.raises(PermissionError):
        run_quality_evaluation(load_dataset(DATA), settings=QualityRunSettings(mode="live"))


def test_mock_live_matches_contract_and_records_usage():
    case = load_dataset(DATA)[0]
    p = MockProvider([json.dumps(case["reference_output"])])
    r = run_quality_evaluation([case], settings=QualityRunSettings(mode="live", max_cases=1), provider=p, live_authorized=True)
    assert p.calls == 1 and r["passed"] == 1
    assert r["cases"][0]["input_tokens"] == 110
    assert r["cases"][0]["human_review_required"] is True
    assert r["cases"][0]["prompt_version"] == "coach-v3"


def test_mock_live_detects_wrong_status():
    case = load_dataset(DATA)[1]
    payload = json.loads(json.dumps(case["reference_output"]))
    payload["feedback"]["grammar"]["status"] = "correct"
    p = MockProvider([json.dumps(payload)])
    r = run_quality_evaluation([case], settings=QualityRunSettings(mode="live"), provider=p, live_authorized=True)
    assert r["failed"] == 1 and "status_mismatch:grammar" in r["cases"][0]["failures"]


def test_mock_live_handles_invalid_output_without_leaking_content():
    case = load_dataset(DATA)[0]
    p = MockProvider(["SECRET invalid JSON"])
    r = run_quality_evaluation([case], settings=QualityRunSettings(mode="live"), provider=p, live_authorized=True)
    assert r["failed"] == 1
    assert "SECRET" not in json.dumps(r)


def test_mock_live_sanitizes_provider_failure():
    class FailingProvider:
        def generate(self, **kwargs):
            raise RuntimeError("secret-provider-token")
    r = run_quality_evaluation(load_dataset(DATA)[:1], settings=QualityRunSettings(mode="live"), provider=FailingProvider(), live_authorized=True)
    assert r["errors"] == 1 and "secret-provider-token" not in json.dumps(r)


def test_case_budget_prevents_extra_calls():
    cases = load_dataset(DATA)
    p = MockProvider([json.dumps(case["reference_output"]) for case in cases[:2]])
    r = run_quality_evaluation(cases, settings=QualityRunSettings(mode="live", max_cases=2), provider=p, live_authorized=True)
    assert p.calls == 2 and r["total"] == 2


@pytest.mark.parametrize("bad", [0, 51, -1])
def test_invalid_case_limits_rejected(bad):
    with pytest.raises(ValueError):
        QualityRunSettings(max_cases=bad)


def test_cli_offline_generates_report(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("LANGUAGE_COACH_EVAL_LIVE", raising=False)
    report_file = tmp_path / "report.json"
    assert main(["--max-cases", "2", "--output", str(report_file)]) == 0
    report = json.loads(report_file.read_text())
    assert report["mode"] == "dry-run" and report["total"] == 2
    assert json.loads(capsys.readouterr().out)["passed"] == 2


def test_cli_rejects_live_without_double_confirmation(monkeypatch):
    monkeypatch.delenv("LANGUAGE_COACH_EVAL_LIVE", raising=False)
    with pytest.raises(SystemExit) as exc:
        main(["--mode", "live", "--max-cases", "1", "--allow-paid-api-calls"])
    assert exc.value.code == 2
