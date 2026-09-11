from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.check_registry import CheckCardRegistry
from server.domain import RuleAuthority


def test_registry_loads_the_three_mvp_golden_check_cards():
    registry = CheckCardRegistry(ROOT / "checks")

    assert registry.ids() == [
        "ANG_MOTOR_YAW",
        "CLR_BAT_BRACKET",
        "DIR_BAT_GROUND",
    ]

    for card_id in registry.ids():
        card = registry.get(card_id)
        assert card.rule.authority == RuleAuthority.FORMAL
        assert card.ground_truth is not None
        assert card.ground_truth.get("status") == "LOCKED"
        assert card.ground_truth.get("source_ref")
        assert card.ground_truth.get("tolerance") is not None

    assert registry.get("CLR_BAT_BRACKET").executor == "minimum_clearance"
    assert registry.get("DIR_BAT_GROUND").executor == "directional_distance"
    assert registry.get("ANG_MOTOR_YAW").executor == "angle"


def test_headroom_is_not_in_mvp_product_check_registry():
    registry = CheckCardRegistry(ROOT / "checks")
    assert "HEADROOM_FRONT" not in registry.ids()
    assert not (ROOT / "checks/headroom_front.yaml").exists()


def test_registry_rejects_duplicate_card_ids(tmp_path: Path):
    card = """
id: DUPLICATE
version: '0.1'
title: Duplicate
source: test
source_ref: test
engineering_domain: static_clearance
verification_method: ANALYSIS_GEOMETRY
executor: minimum_clearance
target: a
counterpart: b
required_bindings: [a, b]
rule:
  authority: FORMAL
  operator: ">="
  threshold: 1
  unit: mm
"""
    (tmp_path / "a.yaml").write_text(card, encoding="utf-8")
    (tmp_path / "b.yaml").write_text(card, encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate check card id"):
        CheckCardRegistry(tmp_path)
