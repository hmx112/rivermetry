from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

import httpx

from rivermetry.build.guard import guard_output
from rivermetry.build.site import build_site
from rivermetry.discovery import discover_usgs_candidates
from rivermetry.models import LocationStatus
from rivermetry.refresh import refresh_live_snapshots
from rivermetry.registry.audit import audit_candidates
from rivermetry.registry.loader import load_locations


def export_worker_allowlist(output: str | Path, registry: str | Path = "data/locations.json") -> int:
    live = [loc for loc in load_locations(registry) if loc.status == LocationStatus.LIVE]
    payload = {
        loc.location_id: {
            "station_id": loc.station_id,
            "country_code": loc.country_code,
            "region_code": loc.region_code,
        }
        for loc in live
    }
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def release_gate(registry: str | Path = "data/locations.json") -> list[str]:
    locations = load_locations(registry)
    live = [loc for loc in locations if loc.status == LocationStatus.LIVE]
    errors = []
    if len(live) != 150:
        errors.append(f"release requires exactly 150 live locations; found {len(live)}")
    if any(loc.observation_provider != "usgs" or not loc.station_id for loc in live):
        errors.append("every live location must have a USGS station")
    if any(not loc.launch_validated_at for loc in live):
        errors.append("every live location must have launch validation metadata")
    return errors


def _guard_built_output(output: str | Path) -> int:
    errors = guard_output(output)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 4
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rivermetry")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--fixtures", action="store_true")
    build.add_argument("--output", default="dist")
    build.add_argument("--registry", default="data/locations.json")
    refresh = sub.add_parser("refresh-static")
    refresh.add_argument("--output", default="dist")
    refresh.add_argument("--registry", default="data/locations.json")
    refresh.add_argument("--workers", type=int, default=6)
    audit = sub.add_parser("audit-registry")
    audit.add_argument("--input", default="data/locations.json")
    audit.add_argument("--output", default="audit.json")
    allow = sub.add_parser("export-worker-allowlist")
    allow.add_argument("--output", default="worker/current-observation/data/live-locations.json")
    allow.add_argument("--registry", default="data/locations.json")
    discover = sub.add_parser("discover-usgs")
    discover.add_argument("--output", default="usgs-candidates.json")
    discover.add_argument("--limit", type=int, default=450)
    gate = sub.add_parser("release-gate")
    gate.add_argument("--registry", default="data/locations.json")

    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            build_site(
                args.output,
                fixture_mode=args.fixtures,
                registry_path=args.registry,
            )
            return _guard_built_output(args.output)
        if args.command == "refresh-static":
            locations = load_locations(args.registry)
            with httpx.Client(follow_redirects=True) as client:
                snapshots = refresh_live_snapshots(
                    client,
                    locations,
                    os.environ.get("USGS_API_KEY"),
                    max_workers=args.workers,
                )
            build_site(
                args.output,
                fixture_mode=False,
                registry_path=args.registry,
                snapshots=snapshots,
            )
            return _guard_built_output(args.output)
        if args.command == "audit-registry":
            raw = json.loads(Path(args.input).read_text())
            Path(args.output).write_text(json.dumps(audit_candidates(raw), indent=2))
            return 0
        if args.command == "export-worker-allowlist":
            return export_worker_allowlist(args.output, args.registry)
        if args.command == "discover-usgs":
            with httpx.Client(follow_redirects=True) as client:
                candidates = discover_usgs_candidates(
                    client,
                    args.limit,
                    os.environ.get("USGS_API_KEY"),
                )
            Path(args.output).write_text(json.dumps(candidates, indent=2))
            print(f"discovered {len(candidates)} USGS candidates")
            return 0 if candidates else 3
        if args.command == "release-gate":
            errors = release_gate(args.registry)
            for error in errors:
                print(error, file=sys.stderr)
            return 4 if errors else 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(exc, file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
