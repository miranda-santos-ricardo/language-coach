from dataclasses import replace
from uuid import uuid4
import pytest
from app.services.conversational_evidence import (ConversationalEvidence, ConversationalEvidenceError, DimensionObservation, DIMENSIONS)
from app.services.professional_communication_rubrics import (get_communication_rubric, RUBRIC_VERSION, RubricReviewSubmission, validate_rubric_review)


def sample(**kwargs):
    v=dict(user_id=uuid4(), practice_session_id=uuid4(), conversation_turn_id=uuid4(),
           client_request_id=uuid4(),locale='fr-CA',context='professional',scenario='Explain project status',
           text='Nous présentons les risques du projet et les décisions.',origin='USER_EDITED',
           authorized_turn=True,stt_original_available=True)
    v.update(kwargs)
    return ConversationalEvidence(**v)


def observations(kind='HUMAN_REVIEWED', assessed=('relevance',)):
    return tuple(DimensionObservation(d,kind if d in assessed else 'NOT_ASSESSED',
         'Review supported by the excerpt' if d in assessed else 'Not assessed',
         'risques' if d in assessed else None) for d in DIMENSIONS)


@pytest.mark.parametrize('locale', ['fr-CA','en-CA','en-US','en-GB'])
@pytest.mark.parametrize('context', ['professional','conversational'])
def test_supported_combinations(locale,context):
    r=get_communication_rubric(locale=locale,context=context)
    assert (r.locale,r.context)==(locale,context)
    assert tuple(c.dimension for c in r.criteria)==DIMENSIONS
    assert r.version==RUBRIC_VERSION

@pytest.mark.parametrize('scenario', ['executive_update','stakeholder_discussion','technical_explanation','general'])
def test_scenario_guidance(scenario):
    r=get_communication_rubric(locale='fr-CA', context='professional',scenario_type=scenario)
    assert r.scenario_type==scenario
    assert len(r.reviewer_instructions)>=9

@pytest.mark.parametrize('kwargs', [dict(locale='fr-FR',context='professional'),dict(locale='en-CA',context='executive'),dict(locale='en-US',context='professional',scenario_type='sales_pitch')])
def test_invalid_rubrics(kwargs):
    with pytest.raises(ConversationalEvidenceError):get_communication_rubric(**kwargs)


def test_all_dimensions_have_criteria_and_limitations():
    r=get_communication_rubric(locale='fr-CA',context='professional')
    assert all(x.question and x.positive_indicators and x.limitations for x in r.criteria)


def test_rubric_contains_no_score_or_cefr_result():
    r=get_communication_rubric(locale='fr-CA',context='professional')
    assert 'score' not in r.to_dict() and 'cefr' not in r.to_dict()
    assert all('score' not in vars(x) for x in r.criteria)


def test_deterministic_and_serializable():
    a=get_communication_rubric(locale='en-GB',context='conversational')
    b=get_communication_rubric(locale='en-GB',context='conversational')
    assert a.to_dict()==b.to_dict()


def test_reviewer_provenance_and_quote():
    evidence=sample()
    review=RubricReviewSubmission(RUBRIC_VERSION,'general','human-r1','HUMAN_REVIEWED',observations())
    output=validate_rubric_review(evidence,review)
    assert output.status=='REVIEWED' and output.dimensions[0].supporting_quote=='risques'


def test_model_review_is_declared_not_assumed():
    review=RubricReviewSubmission(RUBRIC_VERSION,'general','model-r1','MODEL_JUDGMENT',observations('MODEL_JUDGMENT'))
    assert validate_rubric_review(sample(),review).status=='REVIEWED'


def test_incorrect_rubric_version_rejected():
    review=RubricReviewSubmission('rubric-v0','general','r1','HUMAN_REVIEWED',observations())
    with pytest.raises(ConversationalEvidenceError):validate_rubric_review(sample(),review)


def test_unknown_scenario_rejected():
    review=RubricReviewSubmission(RUBRIC_VERSION,'unknown','r1','HUMAN_REVIEWED',observations())
    with pytest.raises(ConversationalEvidenceError):validate_rubric_review(sample(),review)


def test_quote_not_present_rejected():
    o=list(observations());o[0]=replace(o[0],supporting_quote='missing quote')
    review=RubricReviewSubmission(RUBRIC_VERSION,'general','r1','HUMAN_REVIEWED',tuple(o))
    with pytest.raises(ConversationalEvidenceError):validate_rubric_review(sample(),review)


def test_short_text_cannot_be_reviewed():
    review=RubricReviewSubmission(RUBRIC_VERSION,'general','r1','HUMAN_REVIEWED',observations())
    with pytest.raises(ConversationalEvidenceError):validate_rubric_review(sample(text='risques'),review)


def test_reviewer_kind_mismatch_rejected():
    review=RubricReviewSubmission(RUBRIC_VERSION,'general','r1','MODEL_JUDGMENT',observations())
    with pytest.raises(ConversationalEvidenceError):validate_rubric_review(sample(),review)


def test_persuasion_on_neutral_task_abstains():
    review=RubricReviewSubmission(RUBRIC_VERSION,'executive_update','r1','HUMAN_REVIEWED',observations(assessed=('persuasiveness',)))
    with pytest.raises(ConversationalEvidenceError):validate_rubric_review(sample(),review)


def test_persuasion_when_declared_accepted():
    review=RubricReviewSubmission(RUBRIC_VERSION,'stakeholder_discussion','r1','HUMAN_REVIEWED',observations(assessed=('persuasiveness',)))
    assert validate_rubric_review(sample(scenario='Recommend a mitigation to stakeholders'),review).status=='REVIEWED'


def test_no_network_or_model_executed():
    r=get_communication_rubric(locale='fr-CA',context='professional')
    assert 'never infer exact speech' in ' '.join(r.reviewer_instructions).lower()
