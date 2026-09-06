# Rivermetry

**Live River Levels & Streamflow**

Rivermetry is a global-ready river-conditions platform. Release 1 starts in the United States with official USGS observations and optional NOAA/NWS National Water Prediction Service forecasts.

## Release 1 status

- `data/locations.json` contains exactly 150 validated live USGS locations across all 50 states plus the District of Columbia.
- Live locations require fresh USGS discharge (`00060`) and gage-height (`00065`) observations and at least one year of history; the current launch set was selected from a larger real-data candidate pool.
- NOAA/NWS forecast bindings are added only where the official NWPS gauge report indicates forecasts are issued.
- `worker/current-observation/data/live-locations.json` is generated from the same live registry and CI verifies that it stays in sync.
- The release gate blocks production-shaped builds unless exactly 150 validated USGS locations are present.

## Production principles

- No paid data API is required for Release 1.
- No LLM is used in the production runtime.
- Cloudflare Pages + Worker free-tier operation is the initial target.
- Every provider must be enabled and commercially approved in `data/sources.json` and documented in `docs/DATA-SOURCES.md` before production use.
- Rivermetry does not create custom safety or flood-risk judgements.
- USGS discovery first identifies gauges with fresh observations, then fetches metadata only for the bounded live-gauge pool.

## Commands

```bash
python -m pip install -e '.[dev]'
python -m pytest -v
python -m ruff check .
rivermetry release-gate
rivermetry export-worker-allowlist
BASE_URL=https://rivermetry.example WORKER_BASE_URL=https://current.rivermetry.example rivermetry build --output dist
```

Candidate discovery and controlled launch regeneration are available through the GitHub Actions workflows. The validated promotion workflow discovers real USGS gauges, selects the launch set, applies the release gate, verifies the Worker allowlist, and builds the production-shaped site before a registry can be committed.

## Deployment

The code and validated launch registry are ready for deployment configuration. Production domain and Cloudflare Pages/Worker credentials are intentionally not committed to the repository.

Repository variables: `SITE_NAME`, `BASE_URL`, `WORKER_BASE_URL`, `CLOUDFLARE_PAGES_PROJECT`.

Repository secrets: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, optional free `USGS_API_KEY`.
