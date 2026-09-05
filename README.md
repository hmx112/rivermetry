# Rivermetry

**Live River Levels & Streamflow**

Rivermetry is a global-ready public information service for river observations and official forecasts. Release 1 targets the United States with a curated registry of 150 locations using official USGS observations and optional NOAA/NWS NWPS forecasts.

## Production principles

- No paid river-data API is required for Release 1.
- No LLM API is part of the production runtime.
- Static hosting plus a small Cloudflare Worker are designed for free-tier operation at launch.
- Every provider must be explicitly enabled in `data/sources.json` before production use.
- Rivermetry does not create proprietary flood-risk, safety, or fishing-condition labels.
- Production deployment is blocked until real launch locations pass the release gate.

## Local development

```bash
python -m pip install -e '.[dev]'
python -m pytest -v
BASE_URL=https://rivermetry.example WORKER_BASE_URL=https://current.rivermetry.example \
  rivermetry build --fixtures --output dist
```

## Planned production variables

Repository variables:

- `SITE_NAME=Rivermetry`
- `BASE_URL=<registered Rivermetry HTTPS origin>`
- `WORKER_BASE_URL=<deployed Worker HTTPS origin>`
- `CLOUDFLARE_PAGES_PROJECT=rivermetry`

Repository secrets:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- optional `USGS_API_KEY`

The actual production domain is intentionally not hard-coded before registration and connection.
