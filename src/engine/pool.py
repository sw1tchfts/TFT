"""Pool-tracking engine for TFT champion scouting.

This module is pure Python (no third-party deps) so it is fast to import and
trivial to unit test. It models the TFT champion pool: every champion has a
fixed number of copies in a shared pool determined by its cost. As units appear
on player boards/benches, copies are removed from the pool. The fewer copies of
a champion that are held by others, the more contestable that champion is for
you.

Key TFT mechanic: star level maps to copies consumed.
    1-star = 1 copy, 2-star = 3 copies, 3-star = 9 copies.

Snapshots are keyed by *source* (an opponent slot or yourself). Re-scouting the
same source overwrites that source's previous snapshot, so boards that change
over the game never get double-counted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

# A unit's star level -> how many copies of that champion it represents.
STAR_TO_COPIES = {1: 1, 2: 3, 3: 9}

# Canonical source ids.
SELF_SOURCE = "self"
OPPONENT_SOURCES = tuple(f"opp{i}" for i in range(1, 8))  # opp1..opp7
ALL_SOURCES = (SELF_SOURCE,) + OPPONENT_SOURCES


@dataclass(frozen=True)
class Unit:
    """A single champion instance observed in a snapshot."""

    api_name: str
    star: int = 1

    def copies(self) -> int:
        if self.star not in STAR_TO_COPIES:
            raise ValueError(f"invalid star level {self.star!r} for {self.api_name}")
        return STAR_TO_COPIES[self.star]


@dataclass
class Champion:
    api_name: str
    name: str
    cost: int
    traits: tuple[str, ...] = ()
    portrait: str = ""


@dataclass
class ChampionReport:
    api_name: str
    name: str
    cost: int
    total: int          # copies in the full pool
    held: int           # copies currently held across all sources
    remaining: int      # copies still available to roll (clamped >= 0)
    over_counted: bool  # True if held exceeded total (likely a detection error)

    @property
    def remaining_pct(self) -> float:
        return (self.remaining / self.total) if self.total else 0.0


class PoolTracker:
    """Tracks consumed copies per champion across multiple board snapshots."""

    def __init__(self, set_data: dict):
        self.set_number = set_data.get("set")
        self.set_name = set_data.get("name", "")
        self.pool_sizes_by_cost: dict[int, int] = {
            int(k): int(v) for k, v in set_data["pool_sizes_by_cost"].items()
        }
        self.champions: dict[str, Champion] = {}
        for c in set_data["champions"]:
            self.champions[c["apiName"]] = Champion(
                api_name=c["apiName"],
                name=c["name"],
                cost=int(c["cost"]),
                traits=tuple(c.get("traits", [])),
                portrait=c.get("portrait", ""),
            )
        # source id -> list of Units (latest snapshot for that source)
        self._snapshots: dict[str, list[Unit]] = {}
        # api_names seen in snapshots that aren't in this set (detection noise)
        self.unknown_seen: set[str] = set()

    # -- pool math ---------------------------------------------------------

    def pool_total(self, api_name: str) -> int:
        champ = self.champions[api_name]
        return self.pool_sizes_by_cost[champ.cost]

    # -- snapshot management ----------------------------------------------

    def update_source(self, source_id: str, units: Iterable) -> None:
        """Replace the snapshot for a source.

        `units` may be Unit objects, (api_name, star) tuples, or
        {"api_name"/"apiName", "star"} dicts. Unknown champions are recorded in
        `unknown_seen` and skipped so detection noise can't corrupt counts.
        """
        normalized: list[Unit] = []
        for u in units:
            unit = self._coerce_unit(u)
            if unit.api_name not in self.champions:
                self.unknown_seen.add(unit.api_name)
                continue
            normalized.append(unit)
        self._snapshots[source_id] = normalized

    def clear_source(self, source_id: str) -> None:
        self._snapshots.pop(source_id, None)

    def reset(self) -> None:
        self._snapshots.clear()
        self.unknown_seen.clear()

    @staticmethod
    def _coerce_unit(u) -> Unit:
        if isinstance(u, Unit):
            return u
        if isinstance(u, dict):
            name = u.get("api_name") or u.get("apiName")
            return Unit(name, int(u.get("star", 1)))
        # assume sequence (api_name, star)
        api_name = u[0]
        star = int(u[1]) if len(u) > 1 else 1
        return Unit(api_name, star)

    # -- aggregation -------------------------------------------------------

    def held(self) -> dict[str, int]:
        """Copies held per champion across every source snapshot."""
        counts: dict[str, int] = {}
        for units in self._snapshots.values():
            for unit in units:
                counts[unit.api_name] = counts.get(unit.api_name, 0) + unit.copies()
        return counts

    def held_by_source(self, api_name: str) -> dict[str, int]:
        """Per-source breakdown of copies held for one champion."""
        out: dict[str, int] = {}
        for source_id, units in self._snapshots.items():
            n = sum(u.copies() for u in units if u.api_name == api_name)
            if n:
                out[source_id] = n
        return out

    def report(self, sort_by: str = "remaining") -> list[ChampionReport]:
        """Build a per-champion report.

        sort_by:
            "remaining"  -> most contestable first (default)
            "held"       -> most contested first
            "cost"       -> by cost then name
            "name"       -> alphabetical
        """
        held = self.held()
        rows: list[ChampionReport] = []
        for api_name, champ in self.champions.items():
            total = self.pool_total(api_name)
            h = held.get(api_name, 0)
            rows.append(
                ChampionReport(
                    api_name=api_name,
                    name=champ.name,
                    cost=champ.cost,
                    total=total,
                    held=h,
                    remaining=max(total - h, 0),
                    over_counted=h > total,
                )
            )

        keymap = {
            "remaining": lambda r: (-r.remaining, r.cost, r.name),
            "held": lambda r: (-r.held, r.cost, r.name),
            "cost": lambda r: (r.cost, r.name),
            "name": lambda r: (r.name,),
        }
        if sort_by not in keymap:
            raise ValueError(f"unknown sort_by {sort_by!r}")
        rows.sort(key=keymap[sort_by])
        return rows
