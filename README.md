# Rivermetry

**Live River Levels & Streamflow**

Rivermetry is a global-ready static river-conditions platform. Release 1 starts in the United States with official USGS observations and optional NOAA/NWS National Water Prediction Service forecasts.

## Production principles

- No paid data API is required for Release 1.
- No LLM is used in production runtime.
- Cloudflare Pages + Worker free-tier operation is the initial target.
- Every provider must be enabled and commercially approved in `data/sources.json` and documented in `docs/DATA-SOURCES.md` before production use.
- Rivermetry does not create custom safety/flood-risk judgements.
- USGS discovery first identifies gauges with fresh 00060 discharge and 00065 gage-height observations, then fetches metadata only for that bounded live-gauge pool.

## Commands

```bash
python -m pip install -e '.[dev]'
BASE_URL=https://rivermetry.example WORKER_BASE_URL=https://current.rivermetry.example rivermetry build --fixtures --output dist
rivermetry discover-usgs --output usgs-candidates.json --limit 450
rivermetry audit-registry --input usgs-candidates.json --output audit.json
rivermetry export-worker-allowlist
rivermetry release-gate
```

`data/locations.json` intentionally starts empty. The site is not deployable until online discovery and validation produce exactly 150 real live USGS locations. This prevents development fixtures from becoming public data.

## Deployment variables

Repository variables: `SITE_NAME`, `BASE_URL`, `WORKER_BASE_URL`, `CLOUDFLARE_PAGES_PROJECT`.

Repository secrets: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, optional free `USGS_API_KEY`.
