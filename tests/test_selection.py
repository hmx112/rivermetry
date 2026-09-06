from rivermetry.selection import demand_score, history_score, select_launch_locations


def item(id_, state, river, area, years, forecast=False, quality=35):
    return {
        "location_id": id_,
        "state_name": state,
        "station_name": river,
        "river_name": river,
        "drainage_area": area,
        "history_years": years,
        "nwps_forecast": forecast,
        "hard_gate": True,
        "data_quality_score": quality,
        "geographic_score": 10,
        "nearby_score": 3,
    }


def test_excludes_non_us_regions_and_short_history():
    items = [
        item("ca", "British Columbia", "River", 1000, 20),
        item("short", "California", "River", 1000, 0.5),
        item("ok", "California", "River", 1000, 2),
    ]
    assert [x["location_id"] for x in select_launch_locations(items, 10)] == ["ok"]


def test_forecast_major_river_and_large_basin_rank_higher():
    strong = item("strong", "Texas", "Colorado River at Example", 15000, 35, True)
    weak = item("weak", "Texas", "Small Creek at Example", 20, 2, False)
    out = select_launch_locations([weak, strong], 2)
    assert out[0]["location_id"] == "strong"
    assert out[0]["score"] > out[1]["score"]


def test_one_per_state_is_chosen_before_extra_locations():
    items = [
        item("ca1", "California", "Colorado River at A", 15000, 30, True),
        item("ca2", "California", "Sacramento River at B", 9000, 30, True),
        item("ri1", "Rhode Island", "Pawcatuck River at C", 500, 10, False),
    ]
    out = select_launch_locations(items, 2)
    assert {x["state_name"] for x in out} == {"California", "Rhode Island"}


def test_same_nwps_lid_is_not_selected_twice_when_an_alternative_exists():
    first = item("nv1", "Nevada", "Colorado River at A", 15000, 40, True)
    duplicate = item("nv2", "Nevada", "Colorado River at B", 12000, 40, True)
    alternative = item("nv3", "Nevada", "Truckee River at C", 8000, 40, True)
    first["nwps_lid"] = "SAME"
    duplicate["nwps_lid"] = "SAME"
    alternative["nwps_lid"] = "OTHER"

    out = select_launch_locations([first, duplicate, alternative], 2)

    assert [x["location_id"] for x in out] == ["nv1", "nv3"]
    assert len({x["nwps_lid"] for x in out}) == 2


def test_history_and_demand_scores_are_bounded():
    assert history_score(40) == 10
    assert history_score(0.2) == 0
    assert demand_score(item("x", "California", "Colorado River", 100000, 40, True)) <= 25
