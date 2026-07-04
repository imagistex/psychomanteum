#!/usr/bin/env python3
"""
chamber/scry_table.py — the one-shot SCRY verdict table (the P2 ship).

Reads a `scry-dashboard.json` (written by eval/scry_aggregate.py) and prints the
cross-model verdict: per model, how far the facet steered it toward the lineage's
region (block-bar + score), its voice win-rate, the cast/half-cast/mute glyph,
and any local perplexity signal — closed by the chamber's one-line interpretive
verdict and any honesty warnings.

This is the HEADLESS path: pure Rich, prints and exits. It mounts nothing
interactive (the Textual ScryScreen is later). Honors NO_COLOR / FORCE_COLOR via
Rich's Console. Run standalone:

    python chamber/scry_table.py <run>/scry-dashboard.json
    python -m chamber.scry_table  <run>/scry-dashboard.json
"""
from __future__ import annotations

import json
import sys

from rich.box import SIMPLE_HEAVY
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# --- the chamber palette (semantic roles; Rich maps to the terminal) ------------
GOLD = "#E8B765"       # candle-gold — primary / the spell is cast
GOLD_HI = "#F4D58D"
SILVER = "#C7CBD1"     # mirror-silver — body text
EMBER = "#B5552F"      # warnings / uninterpretable
AMETHYST = "#6E5A8E"   # in-progress / half-cast
DIM = "grey42"

_VERDICT_STYLE = {
    "cast": f"bold {GOLD}",
    "half-cast": AMETHYST,
    "mute": DIM,
    "uninterpretable": EMBER,
    "n/a": DIM,
}
_GLYPH = {"cast": "✦", "half-cast": "◐", "mute": "·", "uninterpretable": "⚠", "n/a": "—"}


def _bar(x, width: int = 12) -> Text:
    """A block-bar for a 0-1 value. None -> an empty rule. Gold fill, dim track."""
    if not isinstance(x, (int, float)):
        return Text("—".ljust(width), style=DIM)
    frac = max(0.0, min(1.0, float(x)))
    filled = int(round(frac * width))
    t = Text()
    t.append("█" * filled, style=GOLD)
    t.append("─" * (width - filled), style=DIM)
    return t


def _fmt(x, places=2) -> str:
    return f"{x:.{places}f}" if isinstance(x, (int, float)) else "—"


def render(dashboard: dict, console: Console | None = None) -> None:
    console = console or Console()

    facet = dashboard.get("facet_name", "?")
    judge = (dashboard.get("judge") or {}).get("model", "?")
    tier = dashboard.get("tier", "?")
    distractor = dashboard.get("distractor_facet", "?")
    th = dashboard.get("thresholds", {})

    # header
    head = Text()
    head.append("🪞  PSYCHOMANTEUM · scry\n", style=f"bold {GOLD_HI}")
    head.append(f"facet: ", style=DIM); head.append(f"{facet}", style=SILVER)
    head.append(f"    judge: ", style=DIM); head.append(f"{judge} (held)", style=SILVER)
    head.append(f"    tier: ", style=DIM); head.append(f"{tier}", style=SILVER)
    head.append(f"    distractor: ", style=DIM); head.append(f"{distractor}", style=SILVER)
    console.print(Panel(head, border_style=GOLD, box=SIMPLE_HEAVY, expand=False))

    # table
    table = Table(box=SIMPLE_HEAVY, border_style=DIM, header_style=f"bold {SILVER}",
                  expand=False, pad_edge=False)
    table.add_column("model", style=SILVER, no_wrap=True)
    table.add_column("steer → region", no_wrap=True)
    table.add_column("", justify="right", style=SILVER)        # numeric steer
    table.add_column("voice", justify="right", style=SILVER)
    table.add_column("the spell", no_wrap=True)
    table.add_column("self·ppl", justify="right", style=DIM)   # local bonus signal

    for r in dashboard.get("rows", []):
        v = r.get("verdict", "n/a")
        glyph = Text(f"{_GLYPH.get(v, '?')} {v}", style=_VERDICT_STYLE.get(v, SILVER))
        sp = r.get("self_perplexity") or {}
        sp_facet = sp.get("facet")
        name = Text(str(r.get("name", "?")), style=SILVER)
        if r.get("contaminated_backend"):
            name.append("  ⚠", style=EMBER)   # vendor-wrapper contamination flag
        table.add_row(
            name,
            _bar(r.get("steer_to_region")),
            _fmt(r.get("steer_to_region")),
            _fmt(r.get("voice_winrate")),
            glyph,
            _fmt(sp_facet, 1),
        )
    console.print(table)

    # legend
    cast_t = th.get("cast", 0.66); half_t = th.get("half_cast", 0.33)
    legend = Text()
    legend.append("✦ cast", style=_VERDICT_STYLE["cast"]); legend.append(f" (≥{cast_t})   ", style=DIM)
    legend.append("◐ half-cast", style=_VERDICT_STYLE["half-cast"]); legend.append(f" (≥{half_t})   ", style=DIM)
    legend.append("· mute", style=_VERDICT_STYLE["mute"]); legend.append("   ", style=DIM)
    legend.append("⚠ uninterpretable / contaminated", style=EMBER)
    console.print(legend)

    # the chamber speaks
    voice = dashboard.get("interpretive_voice")
    if voice:
        console.print(Text(f"\n{voice}", style=f"italic {GOLD}"))

    # honesty warnings
    warnings = dashboard.get("warnings") or []
    if warnings:
        console.print(Text("\nwarnings", style=f"bold {EMBER}"))
        for w in warnings:
            console.print(Text(f"  • {w}", style=EMBER))


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python chamber/scry_table.py <run>/scry-dashboard.json", file=sys.stderr)
        return 2
    path = argv[0]
    try:
        with open(path, "r") as fh:
            dashboard = json.load(fh)
    except (OSError, ValueError) as e:
        print(f"could not read scry-dashboard.json: {e}", file=sys.stderr)
        return 1
    render(dashboard)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
