from rivermetry.adapters.usgs import normalize_latest_records, normalize_series_records

def test_latest_and_missing_are_normalized():
    p={'features':[{'properties':{'monitoring_location_id':'USGS-1','parameter_code':'00065','value':'4.2','unit_of_measure':'ft','time':'2026-09-05T00:00:00Z','approval_status':'Provisional'}}]}
    r=normalize_latest_records(p)
    assert r['1']['water_level'].value==4.2
    assert r['1']['streamflow'] is None

def test_series_sorting():
    p={'features':[{'properties':{'parameter_code':'00065','value':'4.2','time':'2026-09-05T01:00:00Z'}},{'properties':{'parameter_code':'00065','value':'4.1','time':'2026-09-05T00:00:00Z'}}]}
    r=normalize_series_records(p)
    assert r['water_level'][0].value==4.1
