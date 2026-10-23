"""Offline opt-in Silero benchmark command. Print a metadata-only JSON report."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

from app.services.vad_runtime_benchmark import benchmark_file


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Opt-in local Silero VAD runtime benchmark')
    p.add_argument('--audio', required=True, type=Path)
    p.add_argument('--locale', required=True, choices=['fr-CA','en-CA','en-US','en-GB'])
    p.add_argument('--annotations', type=Path)
    p.add_argument('--consent', action='store_true', help='Confirm permission to process this audio locally')
    a = p.parse_args(argv)
    try:
        result = benchmark_file(a.audio, locale=a.locale, consent=a.consent, annotation_file=a.annotations)
    except Exception as exc:
        # Do not print user-controlled paths, content, or raw exception strings.
        print(
            json.dumps({
                "status": "FAILED",
                "error_type": type(exc).__name__,
            }),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
