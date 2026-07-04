"""
chamber/ — the PRESENTATION layer of the psychomanteum (occult-themed CLI/TUI).

One-way dependency: chamber depends on eval/, never the reverse. The compute and
aggregation live in eval/ (model-string-pure, no-network core); chamber renders
what they produce. The first surface is the Rich one-shot SCRY verdict table
(scry_table.py); a Textual app + constellation charts come later (P2.3 / P8).

Deps live in chamber/requirements.txt (rich now; typer/textual/textual-plot
later) — kept OUT of eval/requirements.txt so the compute core stays minimal.
"""
