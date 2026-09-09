from __future__ import annotations

from pathlib import Path

import yaml

from .domain import CheckCard, VerificationCase


class CheckCardRegistry:
    """Load versioned engineering checks from YAML assets.

    The registry owns card discovery and validation.  It intentionally does not
    execute geometry; the runtime receives a validated ``VerificationCase``.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self._cards: dict[str, CheckCard] = {}
        self.reload()

    def reload(self) -> None:
        cards: dict[str, CheckCard] = {}
        if self.root.exists():
            paths = sorted(
                [*self.root.glob("*.yaml"), *self.root.glob("*.yml")]
            )
        else:
            paths = []

        for path in paths:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            card = CheckCard.model_validate(payload)
            if card.id in cards:
                raise ValueError(f"duplicate check card id: {card.id}")
            cards[card.id] = card

        self._cards = cards

    def ids(self) -> list[str]:
        return sorted(self._cards)

    def list(self) -> list[CheckCard]:
        return [self._cards[card_id] for card_id in self.ids()]

    def get(self, card_id: str) -> CheckCard:
        try:
            return self._cards[card_id]
        except KeyError as exc:
            raise KeyError(f"unknown check card: {card_id}") from exc

    def case(self, card_id: str) -> VerificationCase:
        return self.get(card_id).to_case()

    def cases(self, card_ids: list[str] | None = None) -> list[VerificationCase]:
        ids = card_ids if card_ids is not None else self.ids()
        return [self.case(card_id) for card_id in ids]
