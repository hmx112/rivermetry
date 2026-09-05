import json
from pathlib import Path

def test_enabled_sources_are_approved():
    sources=json.loads(Path('data/sources.json').read_text())
    for source_id in ('usgs_water_data','noaa_nwps'):
        item=sources[source_id]
        assert item['production_approved'] is True
        assert item['commercial_display'] is True
        assert item['checked_on']=='2026-09-05'
        assert item['terms_url'].startswith('https://')
        assert item['attribution']
