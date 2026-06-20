"""Tests for the pure text report renderer."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.engine.pool import ChampionReport  # noqa: E402
from src.ui.render import (  # noqa: E402
    format_report,
    format_row,
    remaining_bar,
    top_contestable,
)


def make_row(name, cost, total, held):
    return ChampionReport(
        api_name=name, name=name, cost=cost, total=total, held=held,
        remaining=max(total - held, 0), over_counted=held > total,
    )


def test_remaining_bar_full_and_empty():
    full = make_row("A", 1, 30, 0)
    empty = make_row("B", 1, 30, 30)
    assert remaining_bar(full, width=10) == "#" * 10
    assert remaining_bar(empty, width=10) == "-" * 10


def test_top_contestable_orders_by_remaining():
    rows = [make_row("A", 1, 30, 20), make_row("B", 1, 30, 5), make_row("C", 1, 30, 10)]
    top = top_contestable(rows, n=2)
    assert [r.name for r in top] == ["B", "C"]  # most remaining first


def test_top_contestable_cost_filter():
    rows = [make_row("A", 1, 30, 0), make_row("B", 5, 9, 0)]
    top = top_contestable(rows, cost=5)
    assert [r.name for r in top] == ["B"]


def test_format_row_flags_over_count():
    over = make_row("X", 1, 30, 33)
    assert format_row(over).startswith("!")
    normal = make_row("Y", 1, 30, 3)
    assert normal in [normal]  # sanity
    assert format_row(normal).startswith(" ")


def test_format_report_groups_by_cost():
    rows = [make_row("A", 1, 30, 0), make_row("B", 5, 9, 0)]
    out = format_report(rows, by_cost=True)
    assert "1-cost" in out
    assert "5-cost" in out
    assert out.index("1-cost") < out.index("5-cost")


def test_format_report_empty():
    assert format_report([]) == "(no champion data)"
