"""Run with: python -m app.services.pronunciation_lab_cli --help

Local-only operator-invoked experiment. Never stores or transmits recordings.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.pronunciation_assessment import PronunciationRequest
from app.services.pronunciation_feasibility import compare_reference_audio


def main() -> int:
    parser = argparse.ArgumentParser(description='Offline exploratory audio comparison (NOT pronunciation grading)')
    parser.add_argument('--reference', required=True, type=Path, help='Consented reference audio file')
    parser.add_argument('--learner', required=True, type=Path, help='Consented learner audio file')
    parser.add_argument('--locale', required=True, choices=['fr-CA', 'en-CA', 'en-US', 'en-GB'])
    parser.add_argument('--consent', action='store_true', help='Confirm permission to process both files locally')
    args = parser.parse_args()
    if not args.consent:
        parser.error('Explicit --consent is required for both recordings')
    cap = 10 * 1024 * 1024
    for p in (args.reference, args.learner):
        if not p.is_file() or p.stat().st_size == 0 or p.stat().st_size > cap:
            parser.error('Both inputs must be files sized 1 byte to 10 MiB')
    reference = args.reference.read_bytes()
    learner = args.learner.read_bytes()
    result = compare_reference_audio(
        PronunciationRequest(audio=learner, locale=args.locale, processing_consent=True), reference
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
