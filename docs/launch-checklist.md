# Release 1 Launch Checklist

- [ ] `rivermetry.com` or final HTTPS domain registered and `BASE_URL` configured.
- [ ] Cloudflare Pages project connected.
- [ ] Current-observation Worker deployed; CORS restricted to production origin.
- [ ] Exactly 150 U.S. locations marked `live` after online validation.
- [ ] Every live USGS station has a successful launch audit timestamp.
- [ ] Explicit USGS→NWPS match file reviewed for forecast-enabled locations.
- [ ] `rivermetry release-gate` exits 0.
- [ ] Full Python/Worker tests and Ruff pass in GitHub Actions.
- [ ] Source attribution visually checked.
- [ ] Sitemap contains live pages only; preview/candidate pages excluded.
- [ ] Privacy and methodology pages published.
- [ ] Search Console submission ready.
- [ ] Rollback: redeploy the previous successful Pages artifact and Worker version.
