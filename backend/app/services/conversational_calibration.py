"""Phase 7 Step 5.5.1: deterministic, offline conversational calibration harness.

This harness measures contract compliance and concordance with independently supplied
human reference annotations. It does not generate reference judgments, CEFR levels,
or proficiency scores, and never invokes a model or external service.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable

from app.services.conversational_evidence import (
    DIMENSIONS, LOCALES, ConversationalAssessmentDraft,
)

ALLOWED_STATUSES = frozenset({'NOT_ASSESSED', 'INSUFFICIENT_EVIDENCE', 'MODEL_JUDGMENT'})
REFERENCE_STATUSES = frozenset({'NOT_ASSESSED', 'INSUFFICIENT_EVIDENCE', 'HUMAN_REVIEWED'})


class CalibrationContractError(ValueError):
    pass


@dataclass(frozen=True)
class CalibrationCase:
    case_id: str
    locale: str
    context: str
    scenario_type: str
    text: str
    origin: str
    # Human labels must be independently collected and adjudicated before use.
    human_reference: tuple[str, ...] | None = None

    def __post_init__(self):
        if not self.case_id or not self.case_id.strip() or len(self.case_id) > 100:
            raise CalibrationContractError('Invalid case id')
        if self.locale not in LOCALES or self.context not in ('professional', 'conversational'):
            raise CalibrationContractError('Invalid locale or context')
        if self.scenario_type not in ('executive_update', 'stakeholder_discussion', 'technical_explanation', 'general'):
            raise CalibrationContractError('Invalid scenario type')
        if type(self.text) is not str or not self.text.strip() or len(self.text) > 10000:
            raise CalibrationContractError('Invalid submitted text')
        if self.origin not in ('TYPED', 'STT_UNEDITED', 'USER_EDITED', 'VOICE_TEXT_UNKNOWN'):
            raise CalibrationContractError('Invalid origin')
        if self.human_reference is not None and (type(self.human_reference) is not tuple or
            len(self.human_reference) != len(DIMENSIONS) or
            any(s not in REFERENCE_STATUSES for s in self.human_reference)):
            raise CalibrationContractError('Invalid reference labels')


@dataclass(frozen=True)
class CaseAudit:
    case_id: str
    contract_valid: bool
    errors: tuple[str, ...]
    assessed_dimensions: int
    abstained_dimensions: int
    human_agreements: int | None
    human_comparable: int | None


@dataclass(frozen=True)
class CalibrationReport:
    case_count: int
    valid_count: int
    invalid_count: int
    assessed_count: int
    abstained_count: int
    human_agreements: int
    human_comparable: int
    unreferenced_cases: int
    audits: tuple[CaseAudit, ...]

    @property
    def human_agreement_rate(self) -> float | None:
        return (self.human_agreements / self.human_comparable
                if self.human_comparable else None)

    @property
    def abstention_rate(self) -> float | None:
        count = self.assessed_count + self.abstained_count
        return self.abstained_count / count if count else None

    @property
    def release_ready(self) -> bool:
        # Data alone never certifies release: human review, external validation,
        # operational sign-off, and real auth/PostgreSQL evidence remain necessary.
        return False


def audit_case(case: CalibrationCase, draft: ConversationalAssessmentDraft) -> CaseAudit:
    if type(case) is not CalibrationCase or type(draft) is not ConversationalAssessmentDraft:
        raise CalibrationContractError('Expected typed case and assessment draft')
    errors: list[str] = []
    if draft.locale != case.locale or draft.context != case.context or draft.text_origin != case.origin:
        errors.append('CASE_METADATA_MISMATCH')
    if draft.status not in ('REVIEWED', 'INSUFFICIENT_EVIDENCE', 'AWAITING_EVALUATOR'):
        errors.append('INVALID_DRAFT_STATUS')
    if len(draft.dimensions) != len(DIMENSIONS) or tuple(x.dimension for x in draft.dimensions) != DIMENSIONS:
        errors.append('DIMENSION_CONTRACT_MISMATCH')
    assessed = abstained = 0
    statuses: list[str] = []
    for observation in draft.dimensions:
        statuses.append(observation.status)
        if observation.status not in ALLOWED_STATUSES:
            errors.append('INVALID_MODEL_PROVENANCE')
        if observation.status == 'MODEL_JUDGMENT':
            assessed += 1
            if not observation.supporting_quote or observation.supporting_quote not in case.text:
                errors.append('UNSUPPORTED_QUOTE')
        else:
            abstained += 1
            if observation.supporting_quote is not None:
                errors.append('QUOTE_ON_ABSTENTION')
    if len(case.text.split()) < 4 and assessed:
        errors.append('ASSESSED_INSUFFICIENT_TEXT')
    if draft.status == 'REVIEWED' and not assessed:
        errors.append('REVIEWED_WITHOUT_ASSESSMENT')
    if draft.status != 'REVIEWED' and assessed:
        errors.append('UNREVIEWED_WITH_ASSESSMENT')
    comparable = agreements = None
    if case.human_reference is not None and not errors:
        # Agreement is on assess-vs-abstain only; HUMAN_REVIEWED is NOT an
        # ordinal or semantic correctness label. Do not interpret as accuracy.
        comparable = len(DIMENSIONS)
        agreements = sum((status == 'MODEL_JUDGMENT') == (ref == 'HUMAN_REVIEWED')
                         for status, ref in zip(statuses, case.human_reference))
    return CaseAudit(case.case_id, not errors, tuple(sorted(set(errors))), assessed, abstained,
                     agreements, comparable)


def run_calibration(cases: tuple[CalibrationCase, ...],
                    assessor: Callable[[CalibrationCase], ConversationalAssessmentDraft]) -> CalibrationReport:
    if type(cases) is not tuple or not cases or not callable(assessor):
        raise CalibrationContractError('Nonempty cases and deterministic assessor required')
    if len({c.case_id for c in cases}) != len(cases):
        raise CalibrationContractError('Duplicate case id')
    audits: list[CaseAudit] = []
    for case in cases:
        if type(case) is not CalibrationCase:
            raise CalibrationContractError('Invalid case')
        try:
            audit = audit_case(case, assessor(case))
        except Exception:
            # No raw text or provider exception is emitted in the audit report.
            audit = CaseAudit(case.case_id, False, ('ASSESSOR_FAILED',), 0, 0, None, None)
        audits.append(audit)
    valid = tuple(a for a in audits if a.contract_valid)
    return CalibrationReport(
        len(audits), len(valid), len(audits) - len(valid),
        sum(a.assessed_dimensions for a in valid), sum(a.abstained_dimensions for a in valid),
        sum(a.human_agreements or 0 for a in valid),
        sum(a.human_comparable or 0 for a in valid),
        sum(c.human_reference is None for c in cases), tuple(audits))
