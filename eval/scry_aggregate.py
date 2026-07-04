#!/usr/bin/env python3
"""
eval/scry_aggregate.py — combine per-model dashboards into a cross-model verdict.

The R4 SCRY flow writes one `<model>/dashboard.json` (+ `generations.json`) per
model. This module reads them all and emits `scry-dashboard.json`: one row per
model (steer-to-region, voice, verdict glyph, capture provenance, perplexity
signal), the constellation point-set (R5 — net-new, from the dashboards, not
metrics.py), honesty `warnings`, and a one-line interpretive verdict.

PURE: standard library only (no numpy/sklearn) — it reads JSON the scorer already
computed; it never re-runs an LLM or a numeric battery.

DUAL-SCHEMA READER (verified drift). On-disk archive dashboards use
`signals.{style_distance,pairwise_vs_source}`; the CURRENT eval-scorer.md schema
emits `headline.{lens_transfer,pairwise_voice}` + `surprise`. `read_dashboard`
handles both, tags `schema`, and records missing fields rather than crashing. The
single 0-1 lens-transfer composite (`steer_to_region`) exists only in the current
schema; legacy dashboards degrade gracefully (voice only, steer = null).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import defaultdict
from typing import Dict, List, Optional

# Verdict thresholds (tunable). steer-to-region is the lens-transfer composite,
# gated by a clean negative control.
CAST = 0.66
HALF = 0.33
_GLYPH = {"cast": "✦", "half-cast": "◐", "mute": "·",
          "uninterpretable": "⚠", "n/a": "—"}


def fingerprint_probes(probes) -> str:
    """Canonical battery fingerprint: sha256 over probe identity (id+prompt,
    sorted by id). Shared with scry.py so the manifest and the per-model
    generations agree on 'same battery'."""
    ident = sorted(({"id": p.get("id"), "prompt": p.get("prompt")} for p in (probes or [])),
                   key=lambda d: (d["id"] or ""))
    blob = json.dumps(ident, ensure_ascii=False, sort_keys=True)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", (name or "").strip()).strip("-") or "model"


def _dig(d, *path, default=None):
    cur = d
    for k in path:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur


def _num(x):
    """Coerce to float if possible, else None — so an odd/string dashboard field
    (e.g. steer_to_region="0.8") can never reach the verdict math and crash it."""
    if isinstance(x, bool):       # bool is an int subclass; not a score
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        try:
            return float(x.strip())
        except ValueError:
            return None
    return None


def _capture_from_cells(generations: dict):
    """The AUTHORITATIVE capture_method: the most common per-cell value (the
    adapter stamps each cell correctly). The generations.json TOP-LEVEL field is
    an unreliable default (the driver historically hardcoded headless-claude-code),
    so a local/ollama run would otherwise be mislabeled as a contaminated CLI."""
    counts = {}
    for p in generations.get("probes", []):
        for cell in (p.get("generations") or {}).values():
            cm = (cell or {}).get("capture_method")
            if cm:
                counts[cm] = counts.get(cm, 0) + 1
    return max(counts, key=counts.get) if counts else None


def read_dashboard(d: dict) -> dict:
    """Extract the cross-model row fields from a single dashboard, tolerant of
    BOTH the current and legacy schemas. Never raises on a missing field."""
    row: Dict[str, object] = {
        "facet_name": d.get("facet_name"),
        "target_model": d.get("target_model"),
        "capture_method": d.get("capture_method"),
        "tier": d.get("tier"),
        "negative_control": d.get("negative_control_verdict"),
        "missing": [],
    }
    if "headline" in d:                      # current schema
        row["schema"] = "current"
        row["steer_to_region"] = _num(_dig(d, "headline", "lens_transfer", "lens_transfer"))
        row["voice_winrate"] = _num(_dig(d, "headline", "pairwise_voice", "voice_winrate"))
        row["surprise_cell"] = _dig(d, "surprise", "cell")
        row["perplexity_signal"] = _dig(d, "surface_checks", "perplexity_drop")
        # carry the headline detail for drill-down
        row["lens_detail"] = _dig(d, "headline", "lens_transfer", default={})
    elif "signals" in d:                     # legacy schema (no lens composite)
        row["schema"] = "legacy"
        row["steer_to_region"] = None        # not produced by the legacy scorer
        row["voice_winrate"] = _num(_dig(d, "signals", "pairwise_vs_source", "voice_winrate"))
        row["surprise_cell"] = None
        row["perplexity_signal"] = _dig(d, "signals", "perplexity_drop")
        row["legacy_style_shift"] = _dig(d, "signals", "style_distance", "facet_vs_baseline_shift")
    else:
        row["schema"] = "unknown"
        row["steer_to_region"] = None
        row["voice_winrate"] = None
        row["surprise_cell"] = None
        row["perplexity_signal"] = None
    for k in ("steer_to_region", "voice_winrate", "negative_control"):
        if row.get(k) is None:
            row["missing"].append(k)
    return row


def verdict(steer: Optional[float], negative_control: Optional[str]) -> str:
    """cast / half-cast / mute, gated by a clean negative control. A confounded
    OR missing control is NOT interpretable — we never claim a cast we can't trust.

    CONTRACT: this is the consumer half of "The Negative-Control Contract" in
    agents/eval-scorer.md. Producer emits the literal "clean" | "confounded",
    or omits the field when no control ran. ONLY the literal "clean" opens the
    gate; any other value (including None) -> "uninterpretable". Unrecognized
    non-clean strings also warn in main() — they usually mean a scorer drifted
    off the contract. Change either side only in lockstep with the other."""
    if steer is None:
        return "n/a"
    if negative_control != "clean":
        return "uninterpretable"
    return _band(steer)


def _band(steer: float) -> str:
    if steer >= CAST:
        return "cast"
    if steer >= HALF:
        return "half-cast"
    return "mute"


def _self_perplexity(generations: dict) -> Optional[dict]:
    """Mean perplexity of the model's OWN output per condition, from gen_meta
    (local backends only). HONEST LABEL: this is the model's confidence in its
    own generation, NOT the rigorous held-out-lineage Δperplexity (the fast-
    follow). Surfaced as a bonus local signal."""
    sums = defaultdict(list)
    for p in generations.get("probes", []):
        for cond, cell in (p.get("generations") or {}).items():
            ppl = _dig(cell or {}, "gen_meta", "perplexity")
            if isinstance(ppl, (int, float)):
                sums[cond].append(ppl)
    out = {}
    for cond in ("facet", "baseline", "distractor"):
        if sums[cond]:
            out[cond] = round(sum(sums[cond]) / len(sums[cond]), 4)
    if not out:
        return None
    if "facet" in out and "baseline" in out:
        out["facet_minus_baseline"] = round(out["facet"] - out["baseline"], 4)
    out["_note"] = "self-perplexity of own output (local logprobs); not the held-out Δppl"
    return out


_INTERPRETABLE = {"cast", "half-cast", "mute"}


def _interpretive_voice(rows: List[dict]) -> str:
    """One candle-gold sentence ranking the cast. ONLY ranks interpretable rows
    (a clean negative control + a real verdict); a confounded/uninterpretable or
    fingerprint-mismatched row must never be called 'truest'."""
    scored = [r for r in rows if r.get("verdict") in _INTERPRETABLE
              and isinstance(r.get("steer_to_region"), (int, float))]
    if not scored:
        return "the glass stays dark: no model returned a readable, interpretable cast."
    scored.sort(key=lambda r: r["steer_to_region"], reverse=True)
    top = scored[0]
    parts = ["%s casts truest (%.2f)" % (top["name"], top["steer_to_region"])]
    mutes = [r["name"] for r in scored if r["verdict"] == "mute"]
    if mutes:
        parts.append("%s speak%s in a tongue the lineage cannot hear"
                     % (", ".join(mutes), "" if len(mutes) > 1 else "s"))
    return "; ".join(parts) + "."


def aggregate(run_dir: str) -> dict:
    """Read scry.json + each per-model dashboard/generations → scry-dashboard.json."""
    with open(os.path.join(run_dir, "scry.json"), "r") as fh:
        manifest = json.load(fh)
    expected_fp = manifest.get("battery_fingerprint")
    roster = manifest.get("roster") or []

    rows: List[dict] = []
    warnings: List[str] = []
    captures = set()

    for entry in roster:
        name = entry.get("name")
        mdir = os.path.join(run_dir, _slug(name))
        dash_path = os.path.join(mdir, "dashboard.json")
        gen_path = os.path.join(mdir, "generations.json")

        if not os.path.exists(dash_path):
            warnings.append("%s: no dashboard.json (scoring incomplete?)" % name)
            rows.append({"name": name, "model": entry.get("model"),
                         "schema": "absent", "verdict": "n/a", "missing": ["dashboard"]})
            continue

        try:
            with open(dash_path, "r") as fh:
                dashboard = json.load(fh)
        except (OSError, ValueError) as e:
            # one corrupt file must not lose every other model's verdict
            warnings.append("%s: unreadable dashboard.json (%s) — skipped" % (name, e))
            rows.append({"name": name, "model": entry.get("model"),
                         "schema": "unreadable", "verdict": "n/a", "missing": ["dashboard"]})
            continue
        row = read_dashboard(dashboard)
        row["name"] = name
        row["model"] = entry.get("model")
        row["provider"] = entry.get("provider")
        row["contaminated_backend"] = bool(entry.get("contaminated"))

        # generations.json: fingerprint check, failures, capture, self-perplexity
        generations = None
        if os.path.exists(gen_path):
            try:
                with open(gen_path, "r") as fh:
                    generations = json.load(fh)
            except (OSError, ValueError) as e:
                warnings.append("%s: unreadable generations.json (%s)" % (name, e))
        else:
            warnings.append("%s: no generations.json" % name)
        if generations is not None:
            got_fp = fingerprint_probes(generations.get("probes"))
            if expected_fp and got_fp != expected_fp:
                warnings.append("%s: battery fingerprint MISMATCH — not comparable" % name)
                row["fingerprint_ok"] = False
            else:
                row["fingerprint_ok"] = True
            row["n_failures"] = len(generations.get("failures") or [])
            # per-cell capture is authoritative (the top-level field is an
            # unreliable driver default — see _capture_from_cells).
            cap = _capture_from_cells(generations) or generations.get("capture_method") or row.get("capture_method")
            if cap:
                row["capture_method"] = cap
            sp = _self_perplexity(generations)
            if sp:
                row["self_perplexity"] = sp
        else:
            row["fingerprint_ok"] = None

        if row.get("capture_method"):
            captures.add(row["capture_method"])
        if row.get("contaminated_backend"):
            warnings.append("%s: contaminated CLI backend (vendor wrapper) — RELATIVE-ONLY" % name)
        if row.get("negative_control") not in (None, "clean"):
            warnings.append("%s: negative control %s — row uninterpretable"
                            % (name, row.get("negative_control")))
        if row.get("missing"):
            warnings.append("%s: missing %s (schema=%s)"
                            % (name, ", ".join(row["missing"]), row.get("schema")))

        row["verdict"] = verdict(row.get("steer_to_region"), row.get("negative_control"))
        # Only a VERIFIED battery match (fingerprint_ok is True) is comparable. A
        # mismatch (False) OR unverifiable provenance (None — missing/corrupt
        # generations.json) must not carry a cast into the comparison/constellation.
        if row.get("fingerprint_ok") is not True:
            row["verdict"] = "uninterpretable"
        row["glyph"] = _GLYPH.get(row["verdict"], "?")
        rows.append(row)

    if len(captures) > 1:
        warnings.append("MIXED capture methods across models (%s) — cross-model "
                        "comparison is only valid within a capture class" % ", ".join(sorted(captures)))

    # Constellation point-set (R5): data only; charts are P8. ONLY interpretable
    # rows (clean control + real verdict, fingerprint OK) — an uninterpretable
    # point on a steerability plot would mislead.
    _plot = [r for r in rows if r.get("verdict") in _INTERPRETABLE
             and isinstance(r.get("steer_to_region"), (int, float))]
    constellation = {
        "spectrum": [{"model": r["name"], "x": r["steer_to_region"]} for r in _plot],
        "orbit": [{"model": r["name"], "x": r["steer_to_region"], "y": r["voice_winrate"]}
                  for r in _plot if isinstance(r.get("voice_winrate"), (int, float))],
    }

    out = {
        "scry": manifest.get("scry"),
        "facet_name": manifest.get("facet_name"),
        "distractor_facet": manifest.get("distractor_facet"),
        "tier": manifest.get("tier"),
        "battery": manifest.get("battery"),
        "battery_fingerprint": expected_fp,
        "judge": manifest.get("judge"),
        "thresholds": {"cast": CAST, "half_cast": HALF},
        "models": [r["name"] for r in rows],
        "rows": rows,
        "constellation": constellation,
        "warnings": warnings,
    }
    out["interpretive_voice"] = _interpretive_voice(rows)

    out_path = os.path.join(run_dir, "scry-dashboard.json")
    with open(out_path, "w") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    out["_out_path"] = out_path
    return out


def aggregate_summary(run_dir: str) -> dict:
    """Run aggregate() and return a COMPACT summary (full result is on disk in
    scry-dashboard.json). Used by the cli.py seam so stdout stays small."""
    r = aggregate(run_dir)
    return {
        "scry": r["scry"],
        "models": r["models"],
        "warnings": r["warnings"],
        "interpretive_voice": r["interpretive_voice"],
        "out": r["_out_path"],
    }


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="aggregate per-model dashboards into scry-dashboard.json")
    ap.add_argument("run_dir", help="the scry run directory (contains scry.json)")
    args = ap.parse_args(argv)
    print(json.dumps(aggregate_summary(args.run_dir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
