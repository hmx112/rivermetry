from __future__ import annotations

from collections import defaultdict

US_LAUNCH_REGIONS = {
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut",
    "Delaware", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
    "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan",
    "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire",
    "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
    "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
    "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington", "West Virginia",
    "Wisconsin", "Wyoming", "District of Columbia",
}

MAJOR_RIVER_TERMS = (
    "MISSISSIPPI RIVER", "MISSOURI RIVER", "COLORADO RIVER", "COLUMBIA RIVER", "OHIO RIVER",
    "RIO GRANDE", "SACRAMENTO RIVER", "HUDSON RIVER", "DELAWARE RIVER", "POTOMAC RIVER",
    "TENNESSEE RIVER", "ARKANSAS RIVER", "SNAKE RIVER", "GREEN RIVER", "PLATTE RIVER",
    "RED RIVER", "SUSQUEHANNA RIVER", "CHATTAHOOCHEE RIVER", "GUADALUPE RIVER",
    "AMERICAN RIVER", "MERCED RIVER", "YELLOWSTONE RIVER", "KANSAS RIVER", "CONNECTICUT RIVER",
)

PRIORITY_STATES = {
    "California", "Colorado", "Texas", "Florida", "Washington", "Oregon", "Montana", "Wyoming",
    "Utah", "Arizona", "Tennessee", "North Carolina", "Pennsylvania", "New York",
}


def history_score(years: float | None) -> int:
    years_value = float(years or 0)
    if years_value >= 30:
        return 10
    if years_value >= 10:
        return 8
    if years_value >= 5:
        return 6
    if years_value >= 1:
        return 4
    return 0


def demand_score(item: dict) -> int:
    score = 5
    name = str(item.get("station_name") or item.get("river_name") or "").upper()
    if any(term in name for term in MAJOR_RIVER_TERMS):
        score += 8
    area = float(item.get("drainage_area") or 0)
    if area >= 10000:
        score += 7
    elif area >= 2000:
        score += 5
    elif area >= 500:
        score += 3
    elif area >= 100:
        score += 1
    if item.get("state_name") in PRIORITY_STATES:
        score += 3
    return min(25, score)


def enriched_score(item: dict) -> int:
    return min(
        100,
        min(35, int(item.get("data_quality_score", 0)))
        + demand_score(item)
        + (15 if item.get("nwps_forecast") else 0)
        + history_score(item.get("history_years"))
        + min(10, int(item.get("geographic_score", 0)))
        + min(5, int(item.get("nearby_score", 0))),
    )


def select_launch_locations(items: list[dict], limit: int = 150) -> list[dict]:
    eligible = []
    for item in items:
        if item.get("state_name") not in US_LAUNCH_REGIONS:
            continue
        if item.get("hard_gate") is not True:
            continue
        if float(item.get("history_years") or 0) < 1:
            continue
        enriched = dict(item)
        enriched["demand_score"] = demand_score(enriched)
        enriched["history_score"] = history_score(enriched.get("history_years"))
        enriched["nwps_match"] = bool(enriched.get("nwps_forecast"))
        enriched["score"] = enriched_score(enriched)
        enriched["status"] = "preview"
        eligible.append(enriched)

    eligible.sort(
        key=lambda item: (
            -item["score"],
            -float(item.get("drainage_area") or 0),
            item["location_id"],
        )
    )

    by_state: dict[str, list[dict]] = defaultdict(list)
    for item in eligible:
        by_state[item["state_name"]].append(item)

    selected: list[dict] = []
    selected_ids: set[str] = set()
    selected_nwps_lids: set[str] = set()

    def add(item: dict) -> bool:
        if item["location_id"] in selected_ids:
            return False
        nwps_lid = str(item.get("nwps_lid") or "")
        if nwps_lid and nwps_lid in selected_nwps_lids:
            return False
        selected.append(item)
        selected_ids.add(item["location_id"])
        if nwps_lid:
            selected_nwps_lids.add(nwps_lid)
        return True

    for state in sorted(by_state, key=lambda name: (-by_state[name][0]["score"], name)):
        if len(selected) >= limit:
            break
        for item in by_state[state]:
            if add(item):
                break

    for item in eligible:
        if len(selected) >= limit:
            break
        add(item)

    return selected
