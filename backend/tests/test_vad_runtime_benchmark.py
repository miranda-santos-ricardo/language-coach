from pathlib import Path
from types import SimpleNamespace
import json
import pytest
from app.services.vad_runtime_benchmark import evaluate_intervals, benchmark_file
from app.services.vad_runtime_benchmark_cli import main


def seg(a,b): return {'start_ms':a,'end_ms':b}


def test_perfect_agreement():
    r=evaluate_intervals([seg(100,400)],[seg(100,400)],1000)
    assert r['speech_iou']==1 and r['speech_precision']==1 and r['speech_recall']==1


def test_partial_agreement():
    r=evaluate_intervals([seg(0,400)],[seg(200,600)],1000)
    assert r['overlap_ms']==200 and r['false_positive_ms']==200 and r['false_negative_ms']==200
    assert r['speech_iou']==0.3333


def test_no_speech_not_perfect():
    r=evaluate_intervals([],[],1000)
    assert r['speech_iou'] is None and r['speech_recall'] is None


def test_false_positive():
    r=evaluate_intervals([seg(100,200)],[],1000)
    assert r['false_positive_ms']==100 and r['speech_recall'] is None


def test_missed_speech():
    r=evaluate_intervals([],[seg(100,200)],1000)
    assert r['false_negative_ms']==100 and r['speech_precision'] is None


@pytest.mark.parametrize('bad',[[seg(-1,10)],[seg(10,10)],[seg(5,30),seg(20,40)], [seg(0,101)]])
def test_invalid_bounds(bad):
    with pytest.raises(ValueError): evaluate_intervals(bad,[],100)


def test_reject_boolean_bounds():
    with pytest.raises(ValueError): evaluate_intervals([seg(True,40)],[],100)


def test_reject_noninteger_duration():
    with pytest.raises(ValueError): evaluate_intervals([],[],True)


def fake_compare(audio, *, locale, consent):
    assert audio == b'valid bytes' and consent
    return (SimpleNamespace(speech_segments=[SimpleNamespace(start_ms=100,end_ms=400)],intersection_over_union=.5),
            SimpleNamespace(recording_duration_ms=1000))


def test_file_benchmark_with_annotations(tmp_path):
    audio=tmp_path/'a.wav';audio.write_bytes(b'valid bytes')
    ann=tmp_path/'ann.json';ann.write_text(json.dumps({'duration_ms':1000,'speech_intervals':[seg(100,400)]}))
    r=benchmark_file(audio,locale='fr-CA',consent=True,annotation_file=ann,compare=fake_compare)
    assert r['reference_comparison']['speech_recall']==1
    assert r['status']=='EXPLORATORY_ONLY' and 'valid bytes' not in repr(r)


def test_no_annotations(tmp_path):
    a=tmp_path/'a';a.write_bytes(b'valid bytes')
    assert benchmark_file(a,locale='en-GB',consent=True,compare=fake_compare)['reference_comparison'] is None


def test_no_consent(tmp_path):
    with pytest.raises(ValueError,match='consent'):
        benchmark_file(tmp_path/'missing',locale='fr-CA',consent=False,compare=fake_compare)


def test_bad_locale(tmp_path):
    with pytest.raises(ValueError,match='locale'):
        benchmark_file(tmp_path/'missing',locale='fr-FR',consent=True,compare=fake_compare)


def test_oversized(tmp_path):
    a=tmp_path/'big';a.write_bytes(b'x'*(10*1024*1024+1))
    with pytest.raises(ValueError,match='size'):
        benchmark_file(a,locale='en-CA',consent=True,compare=fake_compare)


def test_annotation_duration_mismatch(tmp_path):
    a=tmp_path/'a';a.write_bytes(b'valid bytes')
    b=tmp_path/'b';b.write_text(json.dumps({'duration_ms':2000,'speech_intervals':[]}))
    with pytest.raises(ValueError,match='mismatch'):
        benchmark_file(a,locale='fr-CA',consent=True,annotation_file=b,compare=fake_compare)


def test_cli_requires_consent(capsys):
    assert main(['--audio','missing','--locale','en-US'])==1
    assert 'FAILED' in capsys.readouterr().err
