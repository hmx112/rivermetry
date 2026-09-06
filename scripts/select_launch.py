from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path

import httpx

from rivermetry.enrichment import enrich_candidates
from rivermetry.selection import US_LAUNCH_REGIONS, select_launch_locations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", default="launch-artifacts")
    parser.add_argument("--limit", type=int, default=150)
    args = parser.parse_args()

    candidates = json.loads(Path(args.input).read_text())
    if not isinstance(candidates, list):
        raise SystemExit("candidate input must be a JSON array")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with httpx.Client(follow_redirects=True) as client:
        enriched = enrich_candidates(client, candidates, os.environ.get("USGS_API_KEY"))
    selected = select_launch_locations(enriched, args.limit)

    us_candidates = [item for item in candidates if item.get("state_name") in US_LAUNCH_REGIONS]
    history_eligible = [item for item in enriched if float(item.get("history_years") or 0) >= 1]
    report = {
        "raw_candidates": len(candidates),
        "us_launch_region_candidates": len(us_candidates),
        "history_eligible_candidates": len(history_eligible),
        "nwps_matches": sum(bool(item.get("nwps_match")) for item in enriched),
        "nwps_forecasts": sum(bool(item.get("nwps_forecast")) for item in enriched),
        "selected": len(selected),
        "selected_states": len({item.get("state_name") for item in selected}),
        "selected_by_state": dict(sorted(Counter(item.get("state_name") for item in selected).items())),
        "selected_with_nwps_forecast": sum(bool(item.get("nwps_forecast")) for item in selected),
        "selected_history_years": {
            "min": min((float(item.get("history_years") or 0) for item in selected), default=0),
            "max": max((float(item.get("history_years") or 0) for item in selected), default=0),
        },
    }

    (output_dir / "usgs-candidates-enriched.json").write_text(
        json.dumps(enriched, indent=2, sort_keys=True)
    )
    (output_dir / "launch-preview.json").write_text(json.dumps(selected, indent=2, sort_keys=True))
    (output_dir / "launch-selection-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True)
    )

    print(json.dumps(report, indent=2, sort_keys=True))
    if len(selected) != args.limit:
        print(f"expected {args.limit} preview locations, got {len(selected)}")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
