"""Pure text rendering of the contestability report.

Kept separate from the Qt dashboard so the formatting logic is testable without
a display and reusable for a CLI / log output.
"""

from __future__ import annotations

from ..engine.pool import ChampionReport


def remaining_bar(report: ChampionReport, width: int = 10) -> str:
    filled = round(report.remaining_pct * width)
    return "#" * filled + "-" * (width - filled)


def top_contestable(rows: list[ChampionReport], n: int = 10,
                    cost: int | None = None) -> list[ChampionReport]:
    """Most-available champions first; optionally filter to a cost tier."""
    pool = [r for r in rows if cost is None or r.cost == cost]
    return sorted(pool, key=lambda r: (-r.remaining, r.cost, r.name))[:n]


def format_row(r: ChampionReport, name_width: int = 16) -> str:
    flag = "!" if r.over_counted else " "
    return (
        f"{flag}{r.name:<{name_width}.{name_width}} "
        f"c{r.cost} "
        f"[{remaining_bar(r)}] "
        f"{r.remaining:>2}/{r.total:<2} left  "
        f"held {r.held}"
    )


def format_report(rows: list[ChampionReport], by_cost: bool = True) -> str:
    """Render the full report as a text table, grouped by cost if requested."""
    if not rows:
        return "(no champion data)"
    lines: list[str] = []
    if by_cost:
        for cost in sorted({r.cost for r in rows}):
            tier = sorted(
                (r for r in rows if r.cost == cost),
                key=lambda r: (-r.remaining, r.name),
            )
            lines.append(f"--- {cost}-cost "
                         f"({tier[0].total} copies each) ---")
            lines.extend(format_row(r) for r in tier)
            lines.append("")
    else:
        lines.extend(format_row(r) for r in
                     sorted(rows, key=lambda r: (-r.remaining, r.cost, r.name)))
    return "\n".join(lines).rstrip()
