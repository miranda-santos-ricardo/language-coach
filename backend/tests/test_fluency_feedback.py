from dataclasses import replace
import pytest
from app.services.fluency_feedback import build_fluency_feedback, FluencyFeedbackError
from app.services.fluency_runtime_integration import FluencyObservation
from app.services.fluency_temporal import SpeechInterval, calculate_temporal_metrics


def obs(locale='fr-CA', segments=None, evidence='validated_speech_vad'):
    segments = [SpeechInterval(1000,3000),SpeechInterval(3500,4500)] if segments is None else segments
    timing=calculate_temporal_metrics(locale=locale,recording_duration_ms=6000,speech_intervals=segments,evidence_method=evidence)
    return FluencyObservation('fluency-observation-v1','EXPLORATORY_ONLY',locale,'silero-vad-local',timing,None,45.0,())

@pytest.mark.parametrize('locale', ['fr-CA','en-CA','en-US','en-GB'])
@pytest.mark.parametrize('context', ['professional','conversational'])
def test_localized_evidence_only(locale, context):
    result=build_fluency_feedback(obs(locale),context=context)
    assert result.status=='OBSERVATIONAL_ONLY'
    assert result.locale==locale and result.context==context
    assert len(result.items)==4
    assert '500 ms' in result.items[1].message or '200 ms' in result.items[1].message
    assert 'score' not in result.items[0].message.lower()
    assert 'fluency-feedback-v1'==result.to_dict()['schema_version']

def test_pauses_threshold_is_recomputed():
    result=build_fluency_feedback(obs(),context='professional',minimum_pause_ms=600)
    assert 'Aucune' in result.items[1].message

def test_insufficient_abstains_without_exercise():
    result=build_fluency_feedback(obs(segments=[],evidence='unavailable'), context='conversational')
    assert result.status=='INSUFFICIENT_EVIDENCE'
    assert len(result.items)==1 and result.items[0].kind=='limitation'

def test_energy_abstains_even_with_intervals():
    result=build_fluency_feedback(obs(evidence='energy_activity'),context='professional')
    assert result.status=='INSUFFICIENT_EVIDENCE'

@pytest.mark.parametrize('context',['other','formal',''])
def test_reject_context(context):
    with pytest.raises(FluencyFeedbackError):build_fluency_feedback(obs(),context=context)

@pytest.mark.parametrize('threshold',[-1,60001,1.5,True])
def test_invalid_threshold(threshold):
    with pytest.raises(FluencyFeedbackError):build_fluency_feedback(obs(),context='professional',minimum_pause_ms=threshold)

def test_no_raw_audio_or_transcript():
    d=build_fluency_feedback(obs(),context='professional').to_dict()
    assert 'audio' not in d and 'transcript' not in d and 'word_count' not in d

@pytest.mark.parametrize('field,value', [('status','MEASURED'),('detector','rms'),('schema_version','other'),('locale','de-DE')])
def test_bad_provenance(field,value):
    with pytest.raises(FluencyFeedbackError):build_fluency_feedback(replace(obs(),**{field:value}),context='professional')

def test_mismatched_locale():
    with pytest.raises(FluencyFeedbackError):build_fluency_feedback(replace(obs(),locale='en-US'),context='professional')

def test_invalid_timing_state():
    original=obs()
    with pytest.raises(FluencyFeedbackError):build_fluency_feedback(replace(original,timing=replace(original.timing,speech_duration_ms=0)),context='professional')

def test_input_type():
    with pytest.raises(FluencyFeedbackError):build_fluency_feedback({},context='professional')
