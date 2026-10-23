"""Opt-in local CLI for the Phase 7 Step 4.5 validation chain."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.services.fluency_validation import validate_fluency_pipeline
from app.services.speech_analysis_prototype import MAX_INPUT_BYTES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Local exploratory fluency pipeline validation')
    parser.add_argument('--audio', required=True, type=Path)
    parser.add_argument('--locale', required=True, choices=('fr-CA', 'en-CA', 'en-US', 'en-GB'))
    parser.add_argument('--context', choices=('professional', 'conversational'), default='conversational')
    parser.add_argument('--consent', action='store_true', help='Confirm permission to process this recording locally')
    args = parser.parse_args(argv)
    try:
        if not args.consent:
            raise ValueError('Consent required')
        # Check size before reading. File access is CLI-only, not in the service.
        if not args.audio.is_file() or not 0 < args.audio.stat().st_size <= MAX_INPUT_BYTES:
            raise ValueError('Unusable audio input')
        report = validate_fluency_pipeline(
            args.audio.read_bytes(), locale=args.locale, context=args.context, consent=True,
        )
    except Exception as exc:
        # Never expose local paths, audio or exception strings.
        print(json.dumps({'status': 'FAILED', 'error_type': type(exc).__name__}), file=sys.stderr)
        return 1
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
