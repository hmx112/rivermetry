from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path

from rivermetry.promotion import promote_launch_preview


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--validated-at")
    args = parser.parse_args()

    preview = json.loads(Path(args.input).read_text())
    if not isinstance(preview, list):
        raise SystemExit("launch preview must be a JSON array")
    validated_at = args.validated_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    registry = promote_launch_preview(preview, validated_at)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(f"promoted {len(registry)} validated live locations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
