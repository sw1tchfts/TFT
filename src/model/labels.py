"""Label space shared by the synthetic generator, trainer, and inference.

Champion classes are the set's apiNames plus a sentinel EMPTY class for slots
with no unit. Star classes are the three star levels (1/2/3).
"""

from __future__ import annotations

import json
import os

EMPTY = "__empty__"
STAR_LEVELS = (1, 2, 3)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_SET_DATA = os.path.join(REPO_ROOT, "config", "set_data.json")


class LabelSpace:
    """Maps champion apiNames and star levels to/from contiguous indices."""

    def __init__(self, api_names: list[str]):
        # EMPTY is always index 0; champions follow, sorted for stability.
        self.classes = [EMPTY] + sorted(api_names)
        self.index = {name: i for i, name in enumerate(self.classes)}
        self.star_index = {s: i for i, s in enumerate(STAR_LEVELS)}

    @property
    def num_classes(self) -> int:
        return len(self.classes)

    @property
    def num_stars(self) -> int:
        return len(STAR_LEVELS)

    @property
    def empty_index(self) -> int:
        return self.index[EMPTY]

    def champ_to_idx(self, api_name: str) -> int:
        return self.index[api_name]

    def idx_to_champ(self, idx: int) -> str:
        return self.classes[idx]

    def star_to_idx(self, star: int) -> int:
        return self.star_index[star]

    def idx_to_star(self, idx: int) -> int:
        return STAR_LEVELS[idx]

    def is_empty(self, idx: int) -> bool:
        return idx == self.empty_index

    # -- construction ------------------------------------------------------

    @classmethod
    def from_set_data(cls, path: str = DEFAULT_SET_DATA) -> "LabelSpace":
        with open(path) as fh:
            data = json.load(fh)
        return cls([c["apiName"] for c in data["champions"]])

    def to_dict(self) -> dict:
        return {"classes": self.classes, "star_levels": list(STAR_LEVELS)}

    def save(self, path: str) -> None:
        with open(path, "w") as fh:
            json.dump(self.to_dict(), fh, indent=2)
            fh.write("\n")

    @classmethod
    def load(cls, path: str) -> "LabelSpace":
        with open(path) as fh:
            d = json.load(fh)
        # reconstruct from non-empty classes to keep ordering identical
        api_names = [c for c in d["classes"] if c != EMPTY]
        return cls(api_names)
