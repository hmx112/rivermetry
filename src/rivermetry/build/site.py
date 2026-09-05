from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import shutil

from rivermetry.build.output import write_robots, write_sitemap
from rivermetry.build.render import render, write_page
from rivermetry.config import Settings
from rivermetry.models import LocationStatus
from rivermetry.registry.loader import load_locations


def build_site(output: str | Path, fixture_mode: bool = False, registry_path: str | Path = "data/locations.json") -> Path:
    settings = Settings.from_env()
    root = Path(output)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    locations = load_locations(registry_path)
    live = [loc for loc in locations if loc.status == LocationStatus.LIVE]
    preview = [loc for loc in locations if loc.status == LocationStatus.PREVIEW]
    states: dict[str, list] = defaultdict(list)
    for loc in live:
        states[loc.region_code].append(loc)

    write_page(root, "/", render("home.html", settings=settings, live_count=len(live)))
    write_page(root, "/us/", render("country.html", settings=settings, states=states, live_count=len(live)))
    indexed = ["/", "/us/"]
    for region, group in states.items():
        path = f"/us/{region}/"
        write_page(root, path, render("region.html", settings=settings, region=region, locations=group))
        indexed.append(path)
        for loc in group:
            write_page(root, loc.public_path, render("location.html", settings=settings, loc=loc, preview=False, fixture=fixture_mode))
            indexed.append(loc.public_path)
    for loc in preview:
        write_page(root, loc.public_path, render("location.html", settings=settings, loc=loc, preview=True, fixture=fixture_mode))

    for info in ("methodology", "privacy"):
        path = f"/{info}/"
        write_page(root, path, render(f"{info}.html", settings=settings))
        indexed.append(path)
    static_src = Path("static")
    if static_src.exists():
        shutil.copytree(static_src, root / "static", dirs_exist_ok=True)
    write_sitemap(root, settings.base_url, indexed)
    write_robots(root, settings.base_url)
    return root
