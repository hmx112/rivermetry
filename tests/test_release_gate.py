from rivermetry.cli import release_gate


def test_unvalidated_registry_is_blocked(tmp_path):
    registry = tmp_path / "locations.json"
    registry.write_text("[]\n")

    errors = release_gate(registry)

    assert errors
    assert "exactly 150" in errors[0]
