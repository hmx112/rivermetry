from pathlib import Path


def write_sitemap(root: Path, base_url: str, paths: list[str]) -> None:
    urls = "".join(f"<url><loc>{base_url}{path}</loc></url>" for path in sorted(set(paths)))
    (root / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>')


def write_robots(root: Path, base_url: str) -> None:
    (root / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base_url}/sitemap.xml\n")
