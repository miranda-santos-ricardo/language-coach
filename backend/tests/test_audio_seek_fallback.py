"""Step 4.2b.1: seek-dependent media decoding, privacy, and error regressions."""
import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.speech_analysis_prototype import (
    AudioAnalysisError, SAMPLE_RATE, MAX_DURATION_SECONDS, _decode_pcm,
)


def result(code=0, data=b'\x01\x00' * 100):
    return subprocess.CompletedProcess([], code, data, b'')


def test_pipe_success_does_not_touch_disk():
    with patch('app.services.speech_analysis_prototype.shutil.which', return_value='ffmpeg'), \
         patch('app.services.speech_analysis_prototype.subprocess.run', return_value=result()) as run, \
         patch('app.services.speech_analysis_prototype.tempfile.mkstemp') as temp:
        assert _decode_pcm(b'safe', ffmpeg_binary='ffmpeg', timeout_seconds=2)
        assert run.call_count == 1
        assert run.call_args.args[0][-1] == 'pipe:1'
        temp.assert_not_called()


@pytest.mark.parametrize('first', [result(0, b''), result(1, b''), result(0, b'\x01')], ids=['empty','error','odd-pcm'])
def test_fallback_uses_private_file_then_deletes(tmp_path, monkeypatch, first):
    import tempfile
    original = tempfile.mkstemp
    paths = []
    def mkstemp(*args, **kwargs):
        fd, path = original(*args, dir=tmp_path, **kwargs)
        paths.append(path)
        return fd, path
    def fake_run(command, **kwargs):
        if len(paths) == 0:
            assert command[command.index('-i') + 1] == 'pipe:0'
            assert kwargs['input'] == b'mp4'
            return first
        source = command[command.index('-i') + 1]
        assert source == paths[0]
        assert Path(source).read_bytes() == b'mp4'
        assert kwargs['input'] is None
        return result()
    monkeypatch.setattr('app.services.speech_analysis_prototype.tempfile.mkstemp', mkstemp)
    monkeypatch.setattr('app.services.speech_analysis_prototype.subprocess.run', fake_run)
    monkeypatch.setattr('app.services.speech_analysis_prototype.shutil.which', lambda _: 'ffmpeg')
    assert _decode_pcm(b'mp4', ffmpeg_binary='ffmpeg', timeout_seconds=2)
    assert paths and not Path(paths[0]).exists()


def test_failed_retry_still_cleans_file(tmp_path, monkeypatch):
    import tempfile
    original = tempfile.mkstemp
    paths=[]
    def mkstemp(*args, **kwargs):
        fd,path=original(*args, dir=tmp_path, **kwargs)
        paths.append(path)
        return fd,path
    monkeypatch.setattr('app.services.speech_analysis_prototype.tempfile.mkstemp', mkstemp)
    monkeypatch.setattr('app.services.speech_analysis_prototype.subprocess.run', lambda *a, **k: result(1, b''))
    monkeypatch.setattr('app.services.speech_analysis_prototype.shutil.which', lambda _: 'ffmpeg')
    with pytest.raises(AudioAnalysisError, match='could not be decoded'):
        _decode_pcm(b'invalid', ffmpeg_binary='ffmpeg', timeout_seconds=2)
    assert paths and not Path(paths[0]).exists()


def test_timeout_during_retry_cleans_file(tmp_path, monkeypatch):
    import tempfile
    original=tempfile.mkstemp
    paths=[]
    def mkstemp(*args, **kwargs):
        fd,path=original(*args, dir=tmp_path, **kwargs)
        paths.append(path)
        return fd,path
    calls=0
    def fake_run(*args, **kwargs):
        nonlocal calls
        calls+=1
        if calls == 1:
            return result(1,b'')
        raise subprocess.TimeoutExpired(args[0], kwargs['timeout'])
    monkeypatch.setattr('app.services.speech_analysis_prototype.tempfile.mkstemp', mkstemp)
    monkeypatch.setattr('app.services.speech_analysis_prototype.subprocess.run', fake_run)
    monkeypatch.setattr('app.services.speech_analysis_prototype.shutil.which', lambda _: 'ffmpeg')
    with pytest.raises(AudioAnalysisError, match='timeout'):
        _decode_pcm(b'valid', ffmpeg_binary='ffmpeg', timeout_seconds=2)
    assert paths and not Path(paths[0]).exists()


def test_oversize_rejected_before_file():
    with patch('app.services.speech_analysis_prototype.tempfile.mkstemp') as temp:
        with pytest.raises(AudioAnalysisError, match='10 MiB'):
            _decode_pcm(b'x'*(10*1024*1024+1), ffmpeg_binary='ffmpeg', timeout_seconds=2)
        temp.assert_not_called()


def test_duration_limit_applies_to_retry(tmp_path, monkeypatch):
    import tempfile
    original=tempfile.mkstemp
    paths=[]
    def mkstemp(*args, **kwargs):
        fd,path=original(*args, dir=tmp_path, **kwargs)
        paths.append(path)
        return fd,path
    calls=0
    def fake_run(*a, **k):
        nonlocal calls
        calls+=1
        return result(1,b'') if calls==1 else result(0, b'\x00\x00'*(SAMPLE_RATE*(MAX_DURATION_SECONDS+1)))
    monkeypatch.setattr('app.services.speech_analysis_prototype.tempfile.mkstemp', mkstemp)
    monkeypatch.setattr('app.services.speech_analysis_prototype.subprocess.run', fake_run)
    monkeypatch.setattr('app.services.speech_analysis_prototype.shutil.which', lambda _: 'ffmpeg')
    with pytest.raises(AudioAnalysisError, match='exceeds 60'):
        _decode_pcm(b'audio', ffmpeg_binary='ffmpeg', timeout_seconds=2)
    assert paths and not Path(paths[0]).exists()


@pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='ffmpeg unavailable')
def test_real_seek_dependent_mp4_from_synthetic_audio(tmp_path):
    """Generate synthetic audio only; MP4 non-faststart puts moov after media."""
    mp4=tmp_path/'sample.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi',
                    '-i','sine=frequency=440:duration=1','-c:a','aac','-b:a','96k',str(mp4)],
                   check=True, timeout=20)
    audio=mp4.read_bytes()
    decoded=_decode_pcm(audio,ffmpeg_binary='ffmpeg',timeout_seconds=10)
    assert len(decoded)>SAMPLE_RATE
