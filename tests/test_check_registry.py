from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.check_registry import CheckCardRegistry
from server.domain import RuleAuthority


def test_registry_loads_the_four_mvp_check_cards():
    registry = CheckCardRegistry(ROOT / "checks")

    assert registry.ids() == [
        "ANG_MOTOR_YAW",
        "CLR_BAT_BRACKET",
        "DIR_BAT_GROUND",
        "HEADROOM_FRONT",
    ]

    headroom = registry.get("HEADROOM_FRONT")
    assert headroom.engineering_domain == "static_clearance"
    assert headroom.verification_method == "ANALYSIS_GEOMETRY"
    assert headroom.executor == "minimum_clearance"
    assert headroom.required_bindings == ["head_envelope", "roof_surface"]
    assert headroom.rule.authority == RuleAuthority.PROVISIONAL


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
