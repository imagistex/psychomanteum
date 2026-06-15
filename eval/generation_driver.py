#!/usr/bin/env python3
"""
eval/generation_driver.py — the RESUMABLE, ATOMIC-CHECKPOINT generation driver.

This is the un-loseable replacement for the per-run `_generate.py` scripts the
prober used to hand-roll (one per eval-run directory). Round-2 postmortem
(2026-06-02): the prober wrote `generations.json` only at the END, so when one
`claude` call hung 1863s under contention and the agent's socket dropped, ALL 21
already-completed cells were lost — "resumable" only worked if the prior run had
*fully* completed. This driver fixes that class of loss:

  * ATOMIC CHECKPOINT PER CELL. After EVERY completed (probe x condition) cell,
    the whole manifest is rewritten to a temp file and os.replace()'d over
    generations.json. os.replace is atomic on POSIX, so a kill/drop at any instant
    leaves either the old complete file or the new complete file — never a
    truncated one. Any interruption is therefore resumable from the last cell.

  * RESUME SKIPS COMPLETED CELLS. On start, the existing generations.json is read
    and every cell with usable output is reused. The skip key is the STABLE triple
    (probe_id, condition, model) — so resuming a run on the SAME target model
    skips done cells, while changing the model invalidates them (a battery on one
    model is not comparable to another; see eval-prober.md).

  * SEQUENTIAL. One generate() call at a time (HARD RULE — never parallel). The
    host-level lock in generate.py additionally serializes across sessions.

  * DETACH-FRIENDLY. Designed to be launched as a detached/background process
    (e.g. `nohup … &` or Claude Code's run_in_background) so a dropped agent
    socket cannot kill it. Progress is line-buffered to stderr and, more
    importantly, IS the checkpointed file — poll generations.json to watch it.

The actual model call is delegated to generate.generate(), so capture_method and
the contamination caveats are preserved exactly as for any other capture.

------------------------------------------------------------------------------
USAGE
------------------------------------------------------------------------------

As a library (the recommended path — the prober imports and calls run_battery):

    from generation_driver import run_battery
    summary = run_battery(
        battery_path="…/eval-run/battery.json",
        facet_path="…/foucauldian.md",
        distractor_path="examples/confessional-poet.md",
        out_path="…/eval-run/generations.json",
        manifest_meta={                       # merged into the written manifest
            "facet_name": "foucauldian",
            "facet_path": "examples/foucauldian.md",
            "distractor_facet": "confessional-poet",
            "tier": "lean",
            "held_out_passages_path": "…/held-out-passages.json",
            "battery_summary": {...},         # optional; else derived from probes
            "notes": "…",
        },
        model="headless-claude-code",
        timeout=300,
    )

As a CLI (handy for launching detached from a shell or Bash tool):

    python eval/generation_driver.py \
        --battery   …/eval-run/battery.json \
        --facet     …/foucauldian.md \
        --distractor examples/confessional-poet.md \
        --out       …/eval-run/generations.json \
        [--meta     …/eval-run/manifest-meta.json] \
        [--model headless-claude-code] [--timeout 300]

    # Detached so a dropped socket can't kill it; watch generations.json grow:
    nohup python eval/generation_driver.py --battery … --facet … \
          --distractor … --out …/generations.json \
          > …/eval-run/generate.log 2>&1 &

------------------------------------------------------------------------------
BATTERY INPUT CONTRACT
------------------------------------------------------------------------------

battery.json is whatever the prober's Steps 2-3 produced. This driver requires:

    {"probes": [
        {"id": "anchor-loss", "source": "anchor", "field": null,
         "keyword": "loss", "prompt": "Describe loss.",
         "content_distance": 0.41, ...arbitrary extra keys preserved... },
        ...
    ], "battery_summary": {...}?, ...}

Each probe MUST have at least `id` and `prompt`. All other probe keys are copied
through verbatim into the output row, so the prober controls the row shape.

The three conditions (facet / baseline / distractor) and their `system` text are
fixed here from the facet/distractor files; `baseline` uses an empty system.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
from typing import Dict, List, Optional

# Make `import generate` resolve whether run as `python eval/generation_driver.py`
# (cwd = repo root) or from inside eval/.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import generate as gen  # noqa: E402

# line-buffered stderr so progress is visible even under redirection / detach
try:
    sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
except Exception:
    pass


# --- condition definition (topic held fixed; only `system` varies) --------------

_CONDITION_ORDER = ("facet", "baseline", "distractor")


def _cell_done(cell: Optional[dict]) -> bool:
    """A cell counts as done iff it has non-empty output and is not a failure."""
    if not isinstance(cell, dict):
        return False
    out = cell.get("output")
    if not (isinstance(out, str) and out.strip()):
        return False
    # ok defaults True for older rows that predate the explicit flag.
    return bool(cell.get("ok", True))


def _load_prior(out_path: str) -> Dict[str, dict]:
    """Read an existing generations.json and index its cells by (probe_id, condition).

    Returns {probe_id: {condition: cell, ...}, ...}. Model-mismatched cells are
    dropped by the caller (it knows the requested model); here we keep everything
    so the caller can decide. Robust to a missing/garbage file (returns {}).
    """
    if not os.path.exists(out_path):
        return {}
    try:
        with open(out_path, "r") as fh:
            old = json.load(fh)
    except (OSError, ValueError):
        return {}
    prior: Dict[str, dict] = {}
    for p in old.get("probes", []):
        pid = p.get("id")
        if pid is None:
            continue
        prior[pid] = dict(p.get("generations", {}) or {})
    return prior


def _atomic_write(out_path: str, manifest: dict) -> None:
    """Write the manifest atomically: temp file in the same dir + os.replace."""
    out_dir = os.path.dirname(os.path.abspath(out_path)) or "."
    os.makedirs(out_dir, exist_ok=True)
    # Unique temp name so concurrent writers (shouldn't happen, but be safe) and
    # a crashed prior temp don't collide. Same dir => os.replace is atomic.
    tmp_path = "%s.tmp.%d" % (out_path, os.getpid())
    with open(tmp_path, "w") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp_path, out_path)  # atomic on POSIX


def _derive_battery_summary(probes: List[dict]) -> dict:
    by_source = {"anchor": 0, "in_domain": 0, "cross_domain": 0}
    dists = []
    for p in probes:
        src = (p.get("source") or "").replace("-", "_")
        if src in by_source:
            by_source[src] += 1
        d = p.get("content_distance")
        if isinstance(d, (int, float)):
            dists.append(float(d))
    summary = dict(by_source)
    if dists:
        summary["distance_range"] = [min(dists), max(dists)]
    return summary


def run_battery(
    battery_path: str,
    facet_path: str,
    distractor_path: str,
    out_path: str,
    manifest_meta: Optional[dict] = None,
    model: str = "headless-claude-code",
    timeout: int = 300,
    baseline_system: str = "",
) -> dict:
    """
    Run the full (probe x 3-condition) battery sequentially with an ATOMIC
    checkpoint after every cell, resuming any already-completed cells.

    Returns a small summary dict: {total, completed, skipped, failed, out_path,
    elapsed_s, failures:[...]}. NEVER raises for an operational cell failure (the
    failure is recorded in the cell and the run continues); raises only on a
    genuinely unreadable battery / unreadable facet files (caller's bug).
    """
    manifest_meta = dict(manifest_meta or {})

    with open(battery_path, "r") as fh:
        battery = json.load(fh)
    probes = battery.get("probes") or []
    if not probes:
        raise ValueError("battery has no probes: %s" % battery_path)

    with open(facet_path, "r") as fh:
        facet_text = fh.read()
    with open(distractor_path, "r") as fh:
        distractor_text = fh.read()

    conditions = {
        "facet": facet_text,
        "baseline": baseline_system,   # empty system = bare model, by default
        "distractor": distractor_text,
    }

    # --- resume: index prior cells, keep only those captured on the SAME model ---
    prior = _load_prior(out_path)
    reused = 0
    rows_by_id: Dict[str, dict] = {}
    order = [p["id"] for p in probes]
    for p in probes:
        pid = p["id"]
        gens: Dict[str, dict] = {}
        for cond in _CONDITION_ORDER:
            cell = (prior.get(pid) or {}).get(cond)
            # Stable key is (probe_id, condition, model): a cell is only reusable
            # if it was captured for THIS model. Older rows without a recorded
            # model are reused (back-compat) but new writes always stamp it.
            if _cell_done(cell):
                cell_model = cell.get("model")
                if cell_model in (None, model):
                    gens[cond] = cell
                    reused += 1
        rows_by_id[pid] = {**{k: v for k, v in p.items() if k != "generations"},
                           "generations": gens}

    battery_summary = manifest_meta.pop("battery_summary", None) \
        or battery.get("battery_summary") \
        or _derive_battery_summary(probes)

    failures: List[dict] = []

    def build_manifest() -> dict:
        manifest = {
            "prober": "eval-prober (generation_driver, atomic-checkpoint)",
            "facet_schema": "0.2.0",
            "target_model": model,
            "capture_method": "headless-claude-code",
            "captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "probes": [rows_by_id[pid] for pid in order],
            "battery_summary": battery_summary,
            "failures": failures,
        }
        # Caller-supplied metadata (facet_name, paths, tier, held_out, notes…)
        # overlays the defaults so the written file matches the eval-prober schema.
        manifest.update(manifest_meta)
        return manifest

    # Write once up front so a drop before the first cell still yields a valid
    # (possibly all-resumed) file.
    _atomic_write(out_path, build_manifest())

    n_total = len(probes) * len(_CONDITION_ORDER)
    i = 0
    completed = 0
    skipped = 0
    t0 = time.time()

    for p in probes:
        pid = p["id"]
        prompt = p["prompt"]
        gens = rows_by_id[pid]["generations"]
        for cond in _CONDITION_ORDER:
            i += 1
            if _cell_done(gens.get(cond)):
                skipped += 1
                print("[%d/%d] SKIP (cached) %s / %s" % (i, n_total, pid, cond),
                      file=sys.stderr)
                continue
            system = conditions[cond]
            ts = time.time()
            # STRICTLY SEQUENTIAL: one blocking generate() before the next. The
            # hard-kill timeout + host lock live inside generate().
            res = gen.generate(system=system, user=prompt, model=model, timeout=timeout)
            dt = time.time() - ts
            ok = bool(res.get("ok"))
            out = res.get("output") or ""
            cell = {
                # record the human-readable system label, not the (huge) text
                "system": "empty" if cond == "baseline" else cond,
                "output": out,
                "ok": ok,
                "error": res.get("error"),
                "model": model,                       # part of the stable cell key
                "capture_method": res.get("capture_method"),
                "elapsed_s": round(dt, 1),
            }
            if cond == "baseline":
                cell["cached"] = False
            gens[cond] = cell
            if ok:
                completed += 1
                print("[%d/%d] OK   %s / %s  (%.1fs, %d chars)"
                      % (i, n_total, pid, cond, dt, len(out)), file=sys.stderr)
            else:
                failures.append({"probe": pid, "condition": cond,
                                 "error": res.get("error")})
                print("[%d/%d] FAIL %s / %s  (%.1fs)  ERR: %s"
                      % (i, n_total, pid, cond, dt, res.get("error")),
                      file=sys.stderr)
            # ATOMIC CHECKPOINT after EVERY cell — the whole point of this driver.
            _atomic_write(out_path, build_manifest())

    elapsed = time.time() - t0
    print("\n[done] %d completed / %d skipped(resumed) / %d failed in %.0fs -> %s"
          % (completed, skipped, len(failures), elapsed, out_path), file=sys.stderr)
    for f in failures:
        print("  FAIL %s/%s: %s" % (f["probe"], f["condition"], f["error"]),
              file=sys.stderr)

    return {
        "total": n_total,
        "completed": completed,
        "skipped": skipped,
        "reused": reused,
        "failed": len(failures),
        "out_path": out_path,
        "elapsed_s": round(elapsed, 1),
        "failures": failures,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Resumable atomic-checkpoint generation driver")
    ap.add_argument("--battery", required=True, help="path to battery.json (has probes[])")
    ap.add_argument("--facet", required=True, help="path to the facet-under-test .md")
    ap.add_argument("--distractor", required=True, help="path to the wrong-lineage distractor .md")
    ap.add_argument("--out", required=True, help="path to write generations.json")
    ap.add_argument("--meta", default=None, help="optional JSON file of manifest metadata to merge")
    ap.add_argument("--model", default="headless-claude-code")
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args(argv)

    manifest_meta = {}
    if args.meta:
        with open(args.meta, "r") as fh:
            manifest_meta = json.load(fh)

    summary = run_battery(
        battery_path=args.battery,
        facet_path=args.facet,
        distractor_path=args.distractor,
        out_path=args.out,
        manifest_meta=manifest_meta,
        model=args.model,
        timeout=args.timeout,
    )
    # Print the summary as JSON on stdout (progress went to stderr) so a launcher
    # can capture a machine-readable result.
    print(json.dumps(summary))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
