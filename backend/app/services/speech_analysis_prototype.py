"""Phase 7 Step 2: local, non-production acoustic-activity feasibility probe.

NOT speech VAD, pronunciation scoring, or an indication of speaking proficiency.
No upload, database, external API, network access, or retained raw audio.
Seek-dependent media may require a private, immediately deleted temporary input file.
Requires a locally installed ffmpeg binary; no new Python dependencies.
"""
from __future__ import annotations

import math
import os
import tempfile
import shutil
import struct
import subprocess
from dataclasses import asdict, dataclass

SAMPLE_RATE = 16_000
MAX_INPUT_BYTES = 10 * 1024 * 1024
MAX_DURATION_SECONDS = 60
FRAME_MS = 20


class AudioAnalysisError(ValueError):
    """Invalid/unusable input or decoding failure. Safe to map to controlled errors."""


@dataclass(frozen=True)
class Interval:
    start_ms: int
    end_ms: int


@dataclass(frozen=True)
class AcousticProbeResult:
    method: str
    sample_rate_hz: int
    duration_ms: int
    threshold_dbfs: float
    active_intervals: tuple[Interval, ...]
    internal_inactive_intervals: tuple[Interval, ...]
    active_duration_ms: int
    internal_inactive_duration_ms: int
    status: str
    limitations: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _decode_pcm(audio: bytes, *, ffmpeg_binary: str, timeout_seconds: int) -> bytes:
    """Decode safely, retrying seek-dependent containers via a private temporary file.

    First attempt remains pipe-only. Some MP4/3GP files require seeking to read
    the moov atom, which stdin cannot support. No audio is retained intentionally.
    """
    if not audio or len(audio) > MAX_INPUT_BYTES:
        raise AudioAnalysisError('Audio must be nonempty and at most 10 MiB')
    if timeout_seconds <= 0:
        raise AudioAnalysisError('Invalid decoder timeout')
    binary = shutil.which(ffmpeg_binary)
    if binary is None:
        raise AudioAnalysisError('Local ffmpeg binary unavailable')

    def command(source: str) -> list[str]:
        return [binary, '-nostdin', '-hide_banner', '-loglevel', 'error',
                '-i', source, '-map', '0:a:0', '-vn', '-ac', '1', '-ar', str(SAMPLE_RATE),
                '-t', str(MAX_DURATION_SECONDS + 1), '-f', 's16le', 'pipe:1']

    def run(cmd: list[str], payload: bytes | None = None) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(cmd, input=payload, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, timeout=timeout_seconds, check=False)
        except subprocess.TimeoutExpired as exc:
            raise AudioAnalysisError('Audio decoder timeout') from exc
        except OSError as exc:
            raise AudioAnalysisError('Audio decoder unavailable') from exc

    def valid(proc: subprocess.CompletedProcess) -> bool:
        return proc.returncode == 0 and bool(proc.stdout) and len(proc.stdout) % 2 == 0

    decoded = run(command('pipe:0'), audio)
    if not valid(decoded):
        # mkstemp creates a private file (0600 on POSIX). Close the descriptor
        # before spawning FFmpeg, required for Windows file sharing semantics.
        path = None
        try:
            fd, path = tempfile.mkstemp(prefix='language_coach_audio_', suffix='.bin')
            with os.fdopen(fd, 'wb') as stream:
                stream.write(audio)
            decoded = run(command(path))
        except OSError as exc:
            raise AudioAnalysisError('Temporary audio decoding unavailable') from exc
        finally:
            if path is not None:
                try:
                    os.unlink(path)
                except OSError as exc:
                    # Never silently leave a private audio artifact behind.
                    raise AudioAnalysisError('Temporary audio cleanup failed') from exc
    if not valid(decoded):
        raise AudioAnalysisError('Audio could not be decoded as mono PCM')
    if len(decoded.stdout) > MAX_DURATION_SECONDS * SAMPLE_RATE * 2:
        raise AudioAnalysisError('Decoded audio exceeds 60 seconds')
    return decoded.stdout


def _intervals(flags: list[bool], frame_samples: int, total_samples: int) -> list[Interval]:
    output: list[Interval] = []
    start = None
    for index in range(len(flags) + 1):
        active = flags[index] if index < len(flags) else False
        if active and start is None:
            start = index
        elif not active and start is not None:
            s = round(start * frame_samples * 1000 / SAMPLE_RATE)
            e = round(min(index * frame_samples, total_samples) * 1000 / SAMPLE_RATE)
            if e > s:
                output.append(Interval(s, e))
            start = None
    return output


def probe_audio_activity(
    audio: bytes, *, threshold_dbfs: float = -35.0,
    min_active_ms: int = 120, bridge_gap_ms: int = 100,
    ffmpeg_binary: str = 'ffmpeg', timeout_seconds: int = 12,
) -> AcousticProbeResult:
    """Detect energy above a fixed threshold, NOT human speech.

    Fixed threshold aids reproducibility but is not robust to varying noise floors.
    Returned gaps are internal inactivity between detected active intervals only.
    """
    if not isinstance(audio, bytes):
        raise AudioAnalysisError('Audio input must be bytes')
    if not (-90.0 <= threshold_dbfs <= -3.0) or not math.isfinite(threshold_dbfs):
        raise AudioAnalysisError('Invalid threshold_dbfs')
    if min_active_ms < FRAME_MS or bridge_gap_ms < 0 or timeout_seconds <= 0:
        raise AudioAnalysisError('Invalid analysis configuration')
    pcm = _decode_pcm(audio, ffmpeg_binary=ffmpeg_binary, timeout_seconds=timeout_seconds)
    total_samples = len(pcm) // 2
    if total_samples == 0:
        raise AudioAnalysisError('No decoded samples')
    frame_samples = SAMPLE_RATE * FRAME_MS // 1000
    limit = 10 ** (threshold_dbfs / 20.0)
    flags: list[bool] = []
    for offset in range(0, total_samples, frame_samples):
        chunk = pcm[offset * 2:min(offset + frame_samples, total_samples) * 2]
        samples = struct.iter_unpack('<h', chunk)
        squares = sum((sample[0] / 32768.0) ** 2 for sample in samples)
        count = len(chunk) // 2
        flags.append(math.sqrt(squares / count) > limit)
    # Bridge brief inactive frames; retain leading/trailing quiet periods separately.
    max_bridge = bridge_gap_ms // FRAME_MS
    i = 0
    while i < len(flags):
        if flags[i]:
            i += 1
            continue
        begin = i
        while i < len(flags) and not flags[i]:
            i += 1
        if begin > 0 and i < len(flags) and i - begin <= max_bridge:
            flags[begin:i] = [True] * (i - begin)
    min_frames = math.ceil(min_active_ms / FRAME_MS)
    i = 0
    while i < len(flags):
        if not flags[i]:
            i += 1
            continue
        begin = i
        while i < len(flags) and flags[i]:
            i += 1
        if i - begin < min_frames:
            flags[begin:i] = [False] * (i - begin)
    intervals = _intervals(flags, frame_samples, total_samples)
    gaps = [Interval(left.end_ms, right.start_ms)
            for left, right in zip(intervals, intervals[1:]) if right.start_ms > left.end_ms]
    duration_ms = round(total_samples * 1000 / SAMPLE_RATE)
    return AcousticProbeResult(
        method='energy-rms-v0.1', sample_rate_hz=SAMPLE_RATE, duration_ms=duration_ms,
        threshold_dbfs=threshold_dbfs, active_intervals=tuple(intervals),
        internal_inactive_intervals=tuple(gaps),
        active_duration_ms=sum(x.end_ms - x.start_ms for x in intervals),
        internal_inactive_duration_ms=sum(x.end_ms - x.start_ms for x in gaps),
        status='ACTIVITY_DETECTED' if intervals else 'NO_ACTIVITY_DETECTED',
        limitations=(
            'Energy activity is not validated speech activity; noise/music can trigger detection.',
            'Inactive intervals are not proven linguistic pauses.',
            'No phonemes, pronunciation, prosody, intelligibility or CEFR are assessed.',
            'Fixed RMS threshold is sensitive to input level and background noise.',
            'Temporal resolution is 20 ms; frame rounding affects boundaries.',
        ),
    )
