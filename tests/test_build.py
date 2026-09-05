import json

from rivermetry.build.guard import guard_output
from rivermetry.build.site import build_site


def test_fixture_build_live_only_in_sitemap(tmp_path,monkeypatch):
    registry=tmp_path/'locations.json'
    registry.write_text(json.dumps([{'location_id':'us-ca-a','status':'live','country_code':'us','region_code':'california','slug':'river-a','river_name':'River A','station_name':'River A at Town','observation_provider':'usgs','station_id':'1','latitude':1,'longitude':2,'timezone':'UTC','state_name':'California'},{'location_id':'us-ca-b','status':'preview','country_code':'us','region_code':'california','slug':'river-b','river_name':'River B','station_name':'River B at Town','observation_provider':'usgs','station_id':'2','latitude':1,'longitude':2,'timezone':'UTC','state_name':'California'}]))
    monkeypatch.setenv('BASE_URL','https://rivermetry.example')
    monkeypatch.setenv('WORKER_BASE_URL','https://current.rivermetry.example')
    build_site(tmp_path/'dist',True,registry)
    sitemap=(tmp_path/'dist'/'sitemap.xml').read_text()
    assert '/us/california/river-a/' in sitemap
    assert '/us/california/river-b/' not in sitemap
    assert guard_output(tmp_path/'dist')==[]
