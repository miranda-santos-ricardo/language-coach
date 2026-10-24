"""Offline, validated synthetic reference case bank for Phase 7 Step 5.5.2.

Synthetic challenge tags and review focus are not human reference judgments.
Human labels must be independently collected and reviewed before comparison.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.services.conversational_calibration import CalibrationCase, CalibrationContractError
from app.services.conversational_evidence import DIMENSIONS

SCHEMA_VERSION = 'conversational-reference-bank-v1'
DEFAULT_BANK_PATH = Path(__file__).resolve().parents[1] / 'evaluation' / 'conversation_cases_v1.json'
REQUIRED_LOCALES = frozenset(('fr-CA', 'en-CA', 'en-US', 'en-GB'))
REQUIRED_SCENARIOS = frozenset(('executive_update', 'stakeholder_discussion', 'technical_explanation', 'general'))
CHALLENGE_TAGS = frozenset((
    'clear_update', 'sequencing', 'vague_timeline', 'informal_register',
    'stakeholder_empathy', 'voice_text_only', 'respectful_disagreement', 'risk',
    'technical_precision', 'access_control', 'jargon_ambiguity',
    'regional_expression', 'register_context', 'insufficient_text', 'abstention',
    'uncertainty', 'collaboration', 'direct_feedback', 'governance', 'politeness',
    'dialect_variation',
))
TOP_LEVEL_KEYS = frozenset(('schema_version', 'bank_version', 'reference_status', 'reference_policy', 'cases'))
CASE_KEYS = frozenset(('case_id','locale','context','scenario_type','origin','text',
                       'challenge_tags','review_focus','human_reference'))


@dataclass(frozen=True)
class BankCase:
    calibration: CalibrationCase
    challenge_tags: tuple[str, ...]
    review_focus: tuple[str, ...]


@dataclass(frozen=True)
class ReferenceCaseBank:
    version: str
    cases: tuple[BankCase, ...]
    reference_status: str = 'SYNTHETIC_UNREVIEWED'

    @property
    def calibration_cases(self) -> tuple[CalibrationCase, ...]:
        return tuple(item.calibration for item in self.cases)

    def select(self, *, locale: str | None = None, scenario_type: str | None = None,
               tag: str | None = None) -> tuple[BankCase, ...]:
        return tuple(item for item in self.cases
                     if (locale is None or item.calibration.locale == locale)
                     and (scenario_type is None or item.calibration.scenario_type == scenario_type)
                     and (tag is None or tag in item.challenge_tags))


def _nonempty_strings(value: object, allowed: frozenset[str] | None = None) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or any(type(x) is not str or not x.strip() for x in value):
        raise CalibrationContractError('Invalid reference bank tags/focus')
    result = tuple(value)
    if len(set(result)) != len(result) or (allowed is not None and not set(result) <= allowed):
        raise CalibrationContractError('Duplicate or unsupported tags/focus')
    return result


def parse_reference_case_bank(payload: object) -> ReferenceCaseBank:
    if type(payload) is not dict or set(payload) != TOP_LEVEL_KEYS:
        raise CalibrationContractError('Invalid bank structure')
    if payload['schema_version'] != SCHEMA_VERSION or payload['reference_status'] != 'SYNTHETIC_UNREVIEWED':
        raise CalibrationContractError('Unsupported schema or review status')
    if type(payload['bank_version']) is not str or not payload['bank_version'].strip():
        raise CalibrationContractError('Missing bank version')
    if type(payload['reference_policy']) is not str or not payload['reference_policy'].strip():
        raise CalibrationContractError('Missing reference policy')
    records = payload['cases']
    if type(records) is not list or not records:
        raise CalibrationContractError('Empty reference bank')
    items: list[BankCase] = []
    for record in records:
        if type(record) is not dict or set(record) != CASE_KEYS:
            raise CalibrationContractError('Invalid bank case structure')
        if record['human_reference'] is not None:
            raise CalibrationContractError('Human labels cannot be invented in synthetic reference bank')
        focus = _nonempty_strings(record['review_focus'], frozenset(DIMENSIONS))
        tags = _nonempty_strings(record['challenge_tags'], CHALLENGE_TAGS)
        try:
            case = CalibrationCase(**{key: record[key] for key in (
                'case_id', 'locale', 'context', 'scenario_type', 'text', 'origin', 'human_reference')})
        except (TypeError, CalibrationContractError) as exc:
            raise CalibrationContractError('Invalid bank calibration case') from exc
        items.append(BankCase(case, tags, focus))
    ids = [item.calibration.case_id for item in items]
    if len(ids) != len(set(ids)):
        raise CalibrationContractError('Duplicate reference case identifiers')
    return ReferenceCaseBank(payload['bank_version'], tuple(items))


def load_reference_case_bank(path: str | Path = DEFAULT_BANK_PATH) -> ReferenceCaseBank:
    with Path(path).open('r', encoding='utf-8') as source:
        return parse_reference_case_bank(json.load(source))


def bank_coverage(bank: ReferenceCaseBank) -> dict[str, object]:
    """Descriptive coverage only; not a quality or release-readiness score."""
    if type(bank) is not ReferenceCaseBank:
        raise CalibrationContractError('Invalid case bank')
    return {
        'case_count': len(bank.cases),
        'locales': tuple(sorted({c.calibration.locale for c in bank.cases})),
        'scenario_types': tuple(sorted({c.calibration.scenario_type for c in bank.cases})),
        'contexts': tuple(sorted({c.calibration.context for c in bank.cases})),
        'voice_text_unknown_count': sum(c.calibration.origin == 'VOICE_TEXT_UNKNOWN' for c in bank.cases),
        'short_text_count': sum(len(c.calibration.text.split()) < 4 for c in bank.cases),
        'human_reviewed_count': sum(c.calibration.human_reference is not None for c in bank.cases),
        'required_locale_coverage': REQUIRED_LOCALES.issubset({c.calibration.locale for c in bank.cases}),
        'required_scenario_coverage': REQUIRED_SCENARIOS.issubset({c.calibration.scenario_type for c in bank.cases}),
    }
