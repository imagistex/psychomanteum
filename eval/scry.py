#!/usr/bin/env python3
"""
eval/scry.py — multi-model SCRY generation orchestrator.

SCRY asks the project's deepest question across MANY models at once: does
conditioning a facet steer an arbitrary model toward the lineage's region — is
the spell universal or Claude-specific? (HARNESS-PLAN.md.)

THE R4 FIX (dev-research/SPEC-V2-HARDENING). Multi-model SCRY is NOT a
`run_battery` loop over one file: run_battery is single-model (one out_path, a
single `target_model`), and on resume it DROPS cells whose model differs — loop
it over one file and the last model overwrites the rest ("last model wins"). The
fix is structural:

    build the battery ONCE  ->  run_battery per model into a PER-MODEL dir  ->  aggregate

This module owns the generation half: it resolves the model roster (friendly
names -> model strings, model-string-pure for the eval core, R1), writes the
scry-level manifest (`scry.json`) with a battery FINGERPRINT (determinism / C7)
and the HELD judge provenance (M6), estimates cost behind the serializing host
lock (M3), and runs each model's battery into its own directory. Scoring is the
existing eval-scorer agent (judge held = claude); aggregation is scry_aggregate.py.

Run dir layout:
    <out>/scry-<facet>-<tier>-<date>/
        scry.json                       # this manifest
        battery.json                    # built once, shared by all models
        <model-name>/generations.json   # one per model (no collision)
        <model-name>/dashboard.json     # written by eval-scorer
        scry-dashboard.json             # written by scry_aggregate.py
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # eval/ on path
import generate as gen  # noqa: E402
from generation_driver import run_battery  # noqa: E402
# ONE canonical slug + fingerprint, shared with the aggregator so the per-model
# dir name and the battery fingerprint can never drift between writer and reader.
from scry_aggregate import _slug, fingerprint_probes  # noqa: E402

# Friendly-name roster. OPEN/LOCAL first (clean (system,user), real params, logprobs);
# the CLI backends are reachable but flagged contaminated (vendor-wrapper system
# prompts -> RELATIVE-ONLY) so they are not the default for a clean cross-model study.
# Overlaid by an optional models.toml (see resolve_roster).
DEFAULT_MODELS = {
    # clean local (ollama)
    "talkie":  "ollama:hf.co/thomasgauthier/talkie-1930-13b-it-GGUF:Q4_K_M",
    "qwen2.5": "ollama:qwen2.5:7b-instruct",
    "qwen":    "ollama:qwen2.5:7b-instruct",
    "olmo2":   "ollama:olmo2:7b",
    "mistral": "ollama:mistral:7b",
    "llama3.1": "ollama:llama3.1:8b",
    # contaminated CLI backends (available, not default for clean studies)
    "opus":    "headless-claude-code",
    "claude":  "headless-claude-code",
    "codex":   "codex",
    "gemini":  "gemini",
}

# capture_method a provider WILL stamp — for cost/provenance display only; the
# real value is recorded per-cell by the adapter at generation time.
_CONTAMINATED = {"claude", "codex", "gemini"}


def _looks_like_model_string(s: str) -> bool:
    return ("/" in s) or (":" in s) or s.startswith("headless-")


def resolve_roster(names, models_toml=None):
    """names: list[str] of friendly names and/or raw model strings.
    Returns [{name, model, provider, contaminated}], model-string-pure for eval.
    """
    overlay = {}
    if models_toml and os.path.exists(models_toml):
        try:
            import tomllib  # py3.11+
            with open(models_toml, "rb") as fh:
                overlay = (tomllib.load(fh) or {}).get("models", {}) or {}
        except Exception:
            overlay = {}
    table = {**DEFAULT_MODELS, **overlay}
    roster = []
    seen = set()
    dirs = {}
    for raw in names:
        n = raw.strip()
        if not n or n in seen:
            continue
        seen.add(n)
        if n in table:
            model = table[n]
            disp = n
        elif _looks_like_model_string(n):
            model = n
            disp = n
        else:
            raise ValueError(
                "unknown model %r: not a friendly name (%s) and not a model string"
                % (n, ", ".join(sorted(table)))
            )
        # Each model gets its OWN per-model dir = _slug(name) (used identically by
        # generate_for_model AND the aggregator). Two distinct names that collapse
        # to the same slug would overwrite each other (the R4 collision, sideways),
        # so REJECT it — the names must be distinguishable on disk.
        d = _slug(disp)
        key = d.lower()   # APFS/Windows are case-insensitive: Qwen & qwen collide on disk
        if key in dirs:
            raise ValueError(
                "model names %r and %r both map to the per-model dir %r "
                "(case-insensitively) — use distinct names" % (dirs[key], disp, d))
        dirs[key] = disp
        provider = gen._resolve_provider(model)
        roster.append({
            "name": disp,
            "model": model,
            "provider": provider,
            "contaminated": provider in _CONTAMINATED,
        })
    if not roster:
        raise ValueError("empty model roster")
    return roster


def fingerprint_battery(battery_path):
    """Stable fingerprint over the probe IDENTITY so the aggregator can assert
    every model ran the IDENTICAL battery (determinism / C7). Delegates to the
    canonical `fingerprint_probes` in scry_aggregate so manifest + aggregator can
    never drift apart."""
    with open(battery_path, "r") as fh:
        battery = json.load(fh)
    probes = battery.get("probes") or []
    return fingerprint_probes(probes), len(probes)


def estimate_cost(n_models, n_probes, conditions=3, per_gen_s_lo=15, per_gen_s_hi=60):
    """M3 cost guard: a full multi-model battery is hundreds of serialized
    generations. Return a dry-run estimate for a confirmation gate."""
    total = int(n_models) * int(n_probes) * int(conditions)
    return {
        "models": int(n_models),
        "probes": int(n_probes),
        "conditions": int(conditions),
        "total_generations": total,
        "serialized": True,  # host CLI lock + sequential driver
        "per_gen_s_est": [per_gen_s_lo, per_gen_s_hi],
        "wall_min_est": [round(total * per_gen_s_lo / 60, 1),
                         round(total * per_gen_s_hi / 60, 1)],
        "note": "generation is serial (host lock + sequential driver); scoring (judge) is additional.",
    }


def write_manifest(run_dir, facet_name, facet_path, distractor_facet, distractor_path,
                   battery_path, tier, battery_spec, roster, judge_model, params):
    fp, n_probes = fingerprint_battery(battery_path)
    manifest = {
        "scry": os.path.basename(run_dir.rstrip("/")),
        "facet_name": facet_name,
        "facet_path": facet_path,
        "distractor_facet": distractor_facet,
        "distractor_path": distractor_path,
        "tier": tier,
        "battery": battery_spec,
        "battery_path": os.path.relpath(battery_path, run_dir),
        "battery_fingerprint": fp,
        "n_probes": n_probes,
        # M6: the judge is held constant; record WHICH model so cross-study numbers
        # are comparable. (Default claude/opus; swap only via an explicit study.)
        "judge": {"role": "held", "model": judge_model, "capture": "headless-claude-code"},
        "roster": roster,
        "params": params,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "cost_estimate": estimate_cost(len(roster), n_probes),
    }
    out = os.path.join(run_dir, "scry.json")
    os.makedirs(run_dir, exist_ok=True)
    with open(out, "w") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    return out, manifest


def generate_for_model(run_dir, model_entry, facet_path, distractor_path, battery_path,
                       tier, params=None, timeout=300, held_out_passages_path=None,
                       distractor_facet=None, facet_name=None):
    """Run ONE model's full battery into its own per-model dir. The shared
    battery.json is reused verbatim (build-once); run_battery checkpoints atomically
    and resumes, so a re-run skips completed cells for THIS model only."""
    model = model_entry["model"]
    model_dir = os.path.join(run_dir, _slug(model_entry["name"]))
    out_path = os.path.join(model_dir, "generations.json")
    manifest_meta = {
        "facet_name": facet_name,
        "facet_path": facet_path,
        "distractor_facet": distractor_facet,
        "tier": tier,
        "scry_model_name": model_entry["name"],
    }
    if held_out_passages_path:
        manifest_meta["held_out_passages_path"] = held_out_passages_path
    summary = run_battery(
        battery_path=battery_path,
        facet_path=facet_path,
        distractor_path=distractor_path,
        out_path=out_path,
        manifest_meta=manifest_meta,
        model=model,
        timeout=timeout,
        params=params,
    )
    summary["model_name"] = model_entry["name"]
    summary["model"] = model
    summary["generations_path"] = out_path
    return summary


# ---------------------------------------------------------------------------- CLI

def _cmd_estimate(args):
    _, n_probes = fingerprint_battery(args.battery)
    roster = resolve_roster(args.models.split(","), args.models_toml)
    print(json.dumps(estimate_cost(len(roster), n_probes)))
    return 0


def _cmd_manifest(args):
    roster = resolve_roster(args.models.split(","), args.models_toml)
    params = json.loads(args.params) if args.params else None
    out, manifest = write_manifest(
        run_dir=args.run_dir, facet_name=args.facet_name, facet_path=args.facet,
        distractor_facet=args.distractor_facet, distractor_path=args.distractor,
        battery_path=args.battery, tier=args.tier, battery_spec=args.battery_spec,
        roster=roster, judge_model=args.judge, params=params,
    )
    print(json.dumps({"manifest": out, "scry": manifest["scry"],
                      "fingerprint": manifest["battery_fingerprint"],
                      "cost_estimate": manifest["cost_estimate"]}))
    return 0


def _cmd_generate(args):
    roster = resolve_roster([args.model], args.models_toml)
    params = json.loads(args.params) if args.params else None
    summary = generate_for_model(
        run_dir=args.run_dir, model_entry=roster[0], facet_path=args.facet,
        distractor_path=args.distractor, battery_path=args.battery, tier=args.tier,
        params=params, timeout=args.timeout,
        held_out_passages_path=args.held_out, distractor_facet=args.distractor_facet,
        facet_name=args.facet_name,
    )
    print(json.dumps(summary))
    return 0 if summary.get("failed", 0) == 0 else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="multi-model SCRY generation orchestrator")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("estimate", help="dry-run cost estimate (M3 gate)")
    pe.add_argument("--battery", required=True)
    pe.add_argument("--models", required=True, help="comma-separated friendly names / model strings")
    pe.add_argument("--models-toml", default=None)
    pe.set_defaults(func=_cmd_estimate)

    pm = sub.add_parser("manifest", help="write scry.json (fingerprint + judge + roster)")
    pm.add_argument("--run-dir", required=True)
    pm.add_argument("--facet", required=True)
    pm.add_argument("--facet-name", required=True)
    pm.add_argument("--distractor", required=True)
    pm.add_argument("--distractor-facet", required=True)
    pm.add_argument("--battery", required=True)
    pm.add_argument("--tier", default="lean")
    pm.add_argument("--battery-spec", default="describe")
    pm.add_argument("--models", required=True)
    pm.add_argument("--models-toml", default=None)
    pm.add_argument("--judge", default="opus")
    pm.add_argument("--params", default=None)
    pm.set_defaults(func=_cmd_manifest)

    pg = sub.add_parser("generate", help="run ONE model's battery into its per-model dir")
    pg.add_argument("--run-dir", required=True)
    pg.add_argument("--model", required=True, help="one friendly name / model string")
    pg.add_argument("--facet", required=True)
    pg.add_argument("--facet-name", default=None)
    pg.add_argument("--distractor", required=True)
    pg.add_argument("--distractor-facet", default=None)
    pg.add_argument("--battery", required=True)
    pg.add_argument("--tier", default="lean")
    pg.add_argument("--held-out", default=None)
    pg.add_argument("--models-toml", default=None)
    pg.add_argument("--params", default=None)
    pg.add_argument("--timeout", type=int, default=300)
    pg.set_defaults(func=_cmd_generate)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
