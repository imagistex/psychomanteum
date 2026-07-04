"""
eval/cli.py — the single Bash entry point for the eval harness's compute layer.

The agents (`eval-prober`, `eval-scorer`, `verifier-resonance`) call the delegated
Python through THIS file, so they depend on one stable surface rather than on the
internal module layout. JSON in, JSON out.

Usage:
    python eval/cli.py <command> '<json-args>'

Commands (json-args map to the underlying function's keyword arguments):
    generate          {"system": "...", "user": "Describe loss.", "model": "headless-claude-code"}
    style-distance    {"texts": [...], "corpus_passages": [...], "corpus_weights"?: [...]}  -> {"distances", "method"}
    content-distance  {"texts": [...], "corpus_passages": [...], "corpus_weights"?: [...]}  -> {"distances", "method"}
    paired-stats      {"facet_vals": [...], "baseline_vals": [...]}     -> {mean_shift, ci_*, cohens_d, ...}
    fit-transfer      {"distance": [...], "style_shift": [...], "tier": "lean"|"full"}
    collapse-rate     {"facet_path": "examples/capital-realist.md"}
    confound-check    {"corpus_held_out_high_voice": [...], "distractor_outputs": [...], "corpus_passages": [...], "corpus_weights"?: [...]}  -> {confounded, margin, recommendation, ...}
    verbatim-echo     {"texts": [...], "corpus_passages": [...], "n_lo"?: 4, "n_hi"?: 8}  -> [{echo_fraction, per_n, longest_verbatim_span_tokens, ...}]
    semantic-echo     {"texts": [...], "corpus_passages": [...], "min_chars"?: 12}  -> [{semantic_echo_max, semantic_echo_mean, available, ...}]
    parse-claude      {"stdout": "<raw claude --output-format json stdout>"}  -> {text, ok, error}
    scry-estimate     {"n_models": 2, "n_probes": 11}  -> multi-model cost estimate (M3 gate)
    scry-aggregate    {"run_dir": "eval-runs/scry-..."}  -> compact summary (writes scry-dashboard.json)

Sign convention: paired-stats `mean_shift` (and fit-transfer's `style_shift` y-axis)
are toward-corpus POSITIVE — mean(baseline_dist - facet_dist). Optional
`corpus_weights` (parallel to `corpus_passages`) voice-stratifies the centroid
(high voice_charge -> 1.0, medium -> 0.5, low -> 0.0; or pass dict entries with a
`voice_charge` field). Omit for the original uniform centroid.

Environment: needs a Python with eval/requirements.txt installed (numpy, scikit-learn,
scipy). System Python may lack these — use a venv (see eval/README.md). `generate`
additionally needs the `claude` CLI on PATH (or codex/gemini for those models).

This file lives beside metrics.py and generate.py; run it as `python eval/cli.py ...`
so that directory is on sys.path[0] and the sibling imports resolve.
"""

from __future__ import annotations

import json
import sys

import metrics
import generate as gen
import scry
import scry_aggregate


def _dispatch(cmd: str, payload: dict):
    table = {
        "generate": lambda: gen.generate(**payload),
        "style-distance": lambda: metrics.style_distance_introspect(**payload),
        "content-distance": lambda: metrics.content_distance_introspect(**payload),
        "paired-stats": lambda: metrics.paired_stats(**payload),
        "fit-transfer": lambda: metrics.fit_transfer(**payload),
        "collapse-rate": lambda: metrics.collapse_rate(**payload),
        # round-3 instrument: the confound tripwire, the hollow-tell detector,
        # and the centralized claude-stdout parser (shared with the scorer's
        # pairwise path so the stream-json bug is fixed once, here).
        "confound-check": lambda: metrics.centroid_confound_check(**payload),
        "verbatim-echo": lambda: metrics.verbatim_echo(**payload),
        "semantic-echo": lambda: metrics.semantic_echo(**payload),
        "parse-claude": lambda: gen.parse_claude_stdout(**payload),
        # round-3 cohort fix: the scorer's INNER parse — pull a judgment object out
        # of a judge's prose-wrapped reply, string-aware (apostrophes/braces inside
        # string values can't break the brace match). Replaces ad-hoc brace-counting.
        "extract-json": lambda: gen.extract_json_object(**payload),
        # multi-model SCRY: dry-run cost estimate (M3 gate) + per-model dashboard
        # aggregation into scry-dashboard.json (returns a compact summary).
        "scry-estimate": lambda: scry.estimate_cost(**payload),
        "scry-aggregate": lambda: scry_aggregate.aggregate_summary(**payload),
    }
    if cmd not in table:
        return {"error": f"unknown command '{cmd}'", "available": sorted(table)}
    return table[cmd]()


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if len(argv) < 2:
        print(json.dumps({"error": "usage: python eval/cli.py <command> '<json-args>'",
                          "commands": ["generate", "style-distance", "content-distance",
                                       "paired-stats", "fit-transfer", "collapse-rate",
                                       "confound-check", "verbatim-echo", "semantic-echo",
                                       "parse-claude", "extract-json",
                                       "scry-estimate", "scry-aggregate"]}))
        return 2
    cmd = argv[1]
    try:
        payload = json.loads(argv[2]) if len(argv) > 2 else {}
    except (ValueError, TypeError) as e:
        print(json.dumps({"error": f"bad json-args: {e}"}))
        return 2
    try:
        result = _dispatch(cmd, payload)
    except TypeError as e:
        # wrong/missing kwargs for the chosen command
        print(json.dumps({"error": f"bad arguments for '{cmd}': {e}"}))
        return 2
    except Exception as e:  # surface, don't crash the caller's pipeline
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
