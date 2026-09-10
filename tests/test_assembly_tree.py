from __future__ import annotations

from pathlib import Path

from server.cad.assembly_tree import IMPORT_SCHEMA_VERSION, serialize_assembly_tree
from server.cad.step_reader import Occurrence, StepModel


IDENTITY = (
    1.0, 0.0, 0.0, 0.0,
    0.0, 1.0, 0.0, 0.0,
    0.0, 0.0, 1.0, 0.0,
    0.0, 0.0, 0.0, 1.0,
)
BBOX = (0.0, 0.0, 0.0, 1.0, 1.0, 1.0)


def node(path: str, name: str, children=None) -> Occurrence:
    return Occurrence(
        path=path,
        name=name,
        shape=None,
        transform=IDENTITY,
        bbox=BBOX,
        is_valid=True,
        children=list(children or []),
    )


def fixture_model() -> StepModel:
    battery = node("/Vehicle/Body/battery", "battery")
    bracket = node("/Vehicle/Body/bracket", "bracket")
    body = node("/Vehicle/Body", "Body", [battery, bracket])
    vehicle = node("/Vehicle", "Vehicle", [body])
    occurrences = {n.path: n for n in (vehicle, body, battery, bracket)}
    return StepModel(
        model_id="fixture",
        version="V1",
        path=Path("fixture.step"),
        schema="AP242",
        source_unit="mm",
        coordinate_contract="X-forward/Y-left/Z-up",
        roots=[vehicle],
        occurrences=occurrences,
    )


def flatten(nodes):
    result = []
    for item in nodes:
        result.append(item)
        result.extend(flatten(item["children"]))
    return result


def test_canonical_tree_preserves_hierarchy_and_stats():
    payload = serialize_assembly_tree(fixture_model())
    assert payload["import_schema_version"] == IMPORT_SCHEMA_VERSION
    assert payload["stats"] == {
        "occurrence_count": 4,
        "parent_count": 2,
        "leaf_count": 2,
        "max_depth": 3,
    }

    vehicle = payload["roots"][0]
    body = vehicle["children"][0]
    battery = body["children"][0]
    assert vehicle["parent_id"] is None
    assert body["parent_id"] == vehicle["occurrence_id"]
    assert battery["parent_id"] == body["occurrence_id"]
    assert battery["original_path"] == "/Vehicle/Body/battery"
    assert battery["geometry_ref"] == {
        "kind": "occurrence_path",
        "value": "/Vehicle/Body/battery",
    }


def test_occurrence_ids_are_deterministic_and_unique():
    first = flatten(serialize_assembly_tree(fixture_model())["roots"])
    second = flatten(serialize_assembly_tree(fixture_model())["roots"])
    first_ids = [item["occurrence_id"] for item in first]
    second_ids = [item["occurrence_id"] for item in second]
    assert first_ids == second_ids
    assert len(first_ids) == len(set(first_ids))
    assert all(item.startswith("occ_") for item in first_ids)
