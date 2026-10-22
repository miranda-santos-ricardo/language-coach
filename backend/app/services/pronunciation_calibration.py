"""Offline human-label calibration audit; no acoustic grading or audio processing.

Labels are expert observations, not ground-truth phonetic probabilities.
Only opaque recording/annotator IDs should be included in input manifests.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Any

LOCALES = frozenset({'fr-CA', 'en-CA', 'en-US', 'en-GB'})
LABELS = frozenset({'intelligible', 'partly_intelligible', 'not_intelligible', 'cannot_judge'})
MAX_RECORDINGS = 1000
MAX_ANNOTATIONS = 5000


class CalibrationInputError(ValueError):
    pass


@dataclass(frozen=True)
class Recording:
    id: str
    locale: str
    scenario: str
    method_version: str
    capture_condition: str
    reference_id: str | None = None


@dataclass(frozen=True)
class Annotation:
    recording_id: str
    annotator_id: str
    intelligibility: str
    pronunciation_observation: str  # categorical observation, not numeric score
    regional_variant_valid: bool | None


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not (1 <= len(value) <= 80) or not all(c.isascii() and (c.isalnum() or c in '-_.') for c in value):
        raise CalibrationInputError('IDs must be opaque ASCII identifiers of 1–80 characters')
    return value


def _text(value: Any, field: str, max_length: int = 100) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= max_length:
        raise CalibrationInputError(f'Invalid {field}')
    return value


def _recording(raw: Any) -> Recording:
    if not isinstance(raw, dict) or set(raw) - {'id', 'locale', 'scenario', 'method_version', 'capture_condition', 'reference_id'}:
        raise CalibrationInputError('Invalid recording structure')
    locale = raw.get('locale')
    if locale not in LOCALES:
        raise CalibrationInputError('Unsupported locale')
    reference = raw.get('reference_id')
    return Recording(_identifier(raw.get('id')), locale,
                     _text(raw.get('scenario'), 'scenario'),
                     _text(raw.get('method_version'), 'method_version'),
                     _text(raw.get('capture_condition'), 'capture_condition'),
                     _identifier(reference) if reference is not None else None)


def _annotation(raw: Any) -> Annotation:
    if not isinstance(raw, dict) or set(raw) - {'recording_id', 'annotator_id', 'intelligibility', 'pronunciation_observation', 'regional_variant_valid'}:
        raise CalibrationInputError('Invalid annotation structure')
    label = raw.get('intelligibility')
    if label not in LABELS:
        raise CalibrationInputError('Invalid intelligibility label')
    observation = raw.get('pronunciation_observation')
    if observation not in {'no_specific_issue_observed', 'specific_issue_observed', 'cannot_judge'}:
        raise CalibrationInputError('Invalid pronunciation observation')
    regional = raw.get('regional_variant_valid')
    if regional is not None and not isinstance(regional, bool):
        raise CalibrationInputError('Invalid regional variant flag')
    return Annotation(_identifier(raw.get('recording_id')),
                      _identifier(raw.get('annotator_id')), label, observation, regional)


def audit_calibration_manifest(manifest: dict[str, Any], *, min_dual_annotated_per_locale: int = 3) -> dict[str, Any]:
    """Audit human-annotation coverage and exact agreement, NOT learner pronunciation accuracy.

    Pairs are chosen deterministically by annotator ID. Recordings with >2 raters report
    all unordered pairs. 'cannot_judge' is counted in coverage but excluded from agreement.
    """
    if not isinstance(manifest, dict) or set(manifest) != {'schema_version', 'recordings', 'annotations'} or manifest['schema_version'] != 'calibration-v1':
        raise CalibrationInputError('Unsupported calibration manifest schema')
    recordings_raw, annotations_raw = manifest['recordings'], manifest['annotations']
    if not isinstance(recordings_raw, list) or not isinstance(annotations_raw, list) or len(recordings_raw) > MAX_RECORDINGS or len(annotations_raw) > MAX_ANNOTATIONS:
        raise CalibrationInputError('Invalid collection size')
    if type(min_dual_annotated_per_locale) is not int or min_dual_annotated_per_locale < 1:
        raise CalibrationInputError('Invalid minimum coverage')
    recordings = [_recording(x) for x in recordings_raw]
    recording_by_id = {r.id: r for r in recordings}
    if len(recording_by_id) != len(recordings):
        raise CalibrationInputError('Duplicate recording ID')
    annotations = [_annotation(x) for x in annotations_raw]
    grouped: dict[str, list[Annotation]] = defaultdict(list)
    seen = set()
    for a in annotations:
        if a.recording_id not in recording_by_id:
            raise CalibrationInputError('Annotation refers to unknown recording')
        key = (a.recording_id, a.annotator_id)
        if key in seen:
            raise CalibrationInputError('Duplicate annotation by same rater')
        seen.add(key)
        grouped[a.recording_id].append(a)

    by_locale: dict[str, dict[str, Any]] = {}
    for locale in sorted(LOCALES):
        local = [r for r in recordings if r.locale == locale]
        dual = 0
        eligible = 0
        agreement = 0
        disagreement = 0
        excluded = 0
        regional_flags = 0
        for r in local:
            people = sorted(grouped[r.id], key=lambda a: a.annotator_id)
            if len(people) >= 2:
                dual += 1
            regional_flags += sum(a.regional_variant_valid is True for a in people)
            for i, a in enumerate(people):
                for b in people[i + 1:]:
                    if 'cannot_judge' in (a.intelligibility, b.intelligibility):
                        excluded += 1
                    else:
                        eligible += 1
                        agreement += (a.intelligibility == b.intelligibility)
                        disagreement += (a.intelligibility != b.intelligibility)
        by_locale[locale] = {
            'recordings': len(local), 'dual_annotated_recordings': dual,
            'eligible_annotation_pairs': eligible, 'agreeing_pairs': agreement,
            'disagreeing_pairs': disagreement, 'excluded_cannot_judge_pairs': excluded,
            'exact_agreement_fraction': round(agreement / eligible, 4) if eligible else None,
            'regional_variant_valid_flags': regional_flags,
            'coverage_status': 'READY_FOR_REVIEW' if dual >= min_dual_annotated_per_locale and eligible >= min_dual_annotated_per_locale else 'INSUFFICIENT_EVIDENCE',
        }
    return {
        'schema_version': 'calibration-report-v1',
        'status': 'HUMAN_ANNOTATION_AUDIT_ONLY',
        'recordings': len(recordings), 'annotations': len(annotations),
        'by_locale': by_locale,
        'limitations': [
            'Agreement measures rater consistency, not pronunciation accuracy or phoneme correctness.',
            'Coverage readiness is not validation of a scoring engine or fairness.',
            'No recording, transcript, personal identity, human score, or raw audio is retained by this function.',
            'Coarse audio descriptors from Step 3.2 must never be used as pronunciation correctness labels.',
            'Regional fairness requires separately designed and reviewed sampling and analysis.',
        ],
    }
