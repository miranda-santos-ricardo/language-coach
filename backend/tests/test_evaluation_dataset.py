"""Offline, deterministic Phase 5 Step 10 evaluation dataset tests."""
import copy
import json
from pathlib import Path

import pytest

from app.evaluation.deterministic import load_dataset, evaluate_output, evaluate_dataset, DATASET_VERSION

DATA = Path(__file__).resolve().parents[1] / "evaluations" / "coach_cases_v1.json"


def test_dataset_loads_and_has_required_coverage():
    cases = load_dataset(DATA)
    assert len(cases) >= 12
    assert {c["language_variant"] for c in cases} >= {"fr-CA", "en-CA", "en-US", "en-GB"}
    assert {c["category"] for c in cases} >= {
        "correct", "incorrect", "regional_valid", "professional_style", "prompt_injection", "multi_turn"
    }
    assert {c["training_mode"] for c in cases} == {"general", "professional"}
    assert {c["cefr"] for c in cases} >= {"A1", "B1", "B2", "C1"}


def test_all_reference_outputs_match_step5_contract_and_declared_expectations():
    cases = load_dataset(DATA)
    failures = [r for r in evaluate_dataset(cases) if not r.passed]
    assert failures == []


def test_schema_rejects_missing_fields_without_fabricating_feedback():
    case = copy.deepcopy(load_dataset(DATA)[0])
    del case["reference_output"]["feedback"]["grammar"]
    assert evaluate_output(case, case["reference_output"]).failures == ("invalid_schema",)


def test_status_expectations_detect_fixture_disagreement():
    case = copy.deepcopy(next(c for c in load_dataset(DATA) if c["category"] == "incorrect"))
    dimension = next(iter(case["expected_statuses"]))
    case["reference_output"]["feedback"][dimension]["status"] = "correct"
    assert f"status_mismatch:{dimension}" in evaluate_output(case, case["reference_output"]).failures


def test_injection_canary_is_detected_without_executing_the_instruction():
    case = copy.deepcopy(next(c for c in load_dataset(DATA) if c["category"] == "prompt_injection"))
    case["reference_output"]["coach_response"] = "LEAKED_SYSTEM_PROMPT"
    assert "forbidden_marker_present" in evaluate_output(case, case["reference_output"]).failures


def test_dataset_rejects_duplicate_ids(tmp_path):
    cases = load_dataset(DATA)
    duplicated = [cases[0], cases[0]]
    path = tmp_path / "duplicates.json"
    path.write_text(json.dumps({"version": DATASET_VERSION, "cases": duplicated}), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        load_dataset(path)


def test_duplicate_json_fields_are_rejected():
    case = load_dataset(DATA)[0]
    raw = json.dumps(case["reference_output"])
    duplicate = raw.replace('"coach_response":', '"coach_response":"first","coach_response":', 1)
    assert evaluate_output(case, duplicate).failures == ("invalid_schema",)


@pytest.mark.parametrize("bad", ["", "{}", "not-json", "[]"])
def test_malformed_outputs_fail_safely(bad):
    case = load_dataset(DATA)[0]
    assert evaluate_output(case, bad).failures == ("invalid_schema",)


def test_valid_regional_expression_detects_marked_grammar_error():
    case = copy.deepcopy(next(c for c in load_dataset(DATA) if c["category"] == "regional_valid"))
    case["reference_output"]["feedback"]["grammar"].update({
        "status": "incorrect", "suggestion": "An unnecessary correction"
    })
    result = evaluate_output(case, case["reference_output"])
    assert "regional_grammar_false_positive_fixture" in result.failures


def test_report_entrypoint_can_run_offline(capsys, monkeypatch):
    from app.evaluation.report import main
    monkeypatch.setattr("sys.argv", ["evaluation-report", "--dataset", str(DATA)])
    assert main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["total"] == 14
    assert report["failed"] == 0
    assert report["mode"] == "synthetic_offline_fixture_checks"
