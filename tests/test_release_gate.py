from rivermetry.cli import release_gate

def test_unvalidated_registry_is_blocked():
    errors=release_gate('data/locations.json')
    assert errors
    assert 'exactly 150' in errors[0]
