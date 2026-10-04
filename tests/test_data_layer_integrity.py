import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def _load_json(path: str):
    with (DATA_DIR / path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_state_crosswalk_entries_have_required_fields():
    entries = _load_json("state_crosswalk.json")
    assert isinstance(entries, dict)

    for code, entry in entries.items():
        assert code
        assert isinstance(entry, dict)
        assert entry.get("code")
        assert entry.get("state_name")
        assert entry.get("grid_id")
        assert isinstance(entry.get("cold_climate"), bool)


def test_grid_factors_have_required_fields():
    entries = _load_json("grid_factors.json")
    assert isinstance(entries, dict)

    for region, entry in entries.items():
        assert region
        assert isinstance(entry, dict)
        assert isinstance(entry.get("source_agency"), str) and entry.get("source_agency")
        assert entry.get("co2e_lb_per_mwh", 0) > 0


def test_nb_entries_are_present_and_load_without_schema_errors():
    state_crosswalk = _load_json("state_crosswalk.json")
    grid_factors = _load_json("grid_factors.json")

    nb_state = state_crosswalk.get("NB")
    assert nb_state is not None
    assert nb_state["code"] == "NB"
    assert nb_state["state_name"] == "New Brunswick"
    assert nb_state["grid_id"] == "NB"
    assert nb_state["cold_climate"] is True

    nb_grid = grid_factors.get("NB")
    assert nb_grid is not None
    assert nb_grid["param_id"] == "GRID_FACTOR_NB"
    assert nb_grid["co2e_lb_per_mwh"] == 613.4
    assert nb_grid["co2e_g_per_kwh_native"] == 278.233


def test_every_crosswalk_entry_resolves_to_existing_grid_factor():
    state_crosswalk = _load_json("state_crosswalk.json")
    grid_factors = _load_json("grid_factors.json")

    for code, entry in state_crosswalk.items():
        resolved_key = entry.get("subregion") or entry.get("primary_subregion") or entry.get("grid_id")
        assert resolved_key is not None, f"Crosswalk entry '{code}' has no subregion, primary_subregion, or grid_id."
        assert resolved_key in grid_factors, (
            f"Crosswalk entry '{code}' resolved to '{resolved_key}', which does not exist in grid_factors.json."
        )


def test_baselines_with_region_scope_have_source_agency():
    baselines = _load_json("afleet_baselines.json")
    assert isinstance(baselines, dict)

    def _check_region_scope(node):
        if isinstance(node, dict):
            if "region_scope" in node:
                assert isinstance(node.get("source_agency"), str) and node.get("source_agency")
            for v in node.values():
                _check_region_scope(v)
        elif isinstance(node, list):
            for item in node:
                _check_region_scope(item)

    _check_region_scope(baselines)



ESTIMATE_LABEL = "Engineering estimate pending citation"


def _param_nodes(node, path=""):
    if isinstance(node, dict):
        if "param_id" in node:
            yield path, node
        for k, v in node.items():
            yield from _param_nodes(v, f"{path}/{k}")
    elif isinstance(node, list):
        for i, item in enumerate(node):
            yield from _param_nodes(item, f"{path}[{i}]")


def test_every_parameter_has_a_source_or_the_estimate_label():
    # Citation rule: every parameter carries a real source, or the exact
    # estimate label. There is no third category.
    for filename in ("afleet_baselines.json", "grid_factors.json", "fx_rates.json"):
        for path, node in _param_nodes(_load_json(filename)):
            source = node.get("source") or node.get("source_agency")
            assert isinstance(source, str) and source.strip(), f"{filename}{path} ({node['param_id']}) has no source"
            if "estimate" in source.lower():
                assert ESTIMATE_LABEL in source, f"{filename}{path} uses a non-standard estimate label: {source!r}"
            assert "FleetPath Engineering" not in source


def test_fraction_parameters_are_labeled_as_fractions():
    for path, node in _param_nodes(_load_json("afleet_baselines.json")):
        unit = node.get("unit", "")
        if unit.startswith("%"):
            raise AssertionError(f"{path}: unit {unit!r} implies a percent, but values are stored as fractions")
