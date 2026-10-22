"""Read metadata-only calibration manifest and emit human annotation audit JSON."""
import argparse
import json
from pathlib import Path
from app.services.pronunciation_calibration import CalibrationInputError, audit_calibration_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description='Offline calibration annotation audit (no pronunciation scores)')
    parser.add_argument('--manifest', required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.manifest.stat().st_size > 512_000:
            raise CalibrationInputError('Manifest is too large')
        data = json.loads(args.manifest.read_text(encoding='utf-8'))
        print(json.dumps(audit_calibration_manifest(data), indent=2, ensure_ascii=False))
    except (OSError, json.JSONDecodeError, CalibrationInputError) as exc:
        parser.exit(2, f'Calibration manifest rejected: {type(exc).__name__}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
