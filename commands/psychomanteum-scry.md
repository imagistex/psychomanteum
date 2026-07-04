---
name: psychomanteum-scry
description: Scry a facet across MANY models at once — does conditioning steer each model toward the lineage's region? Build the battery once, generate + score per model into per-model dirs, aggregate into one cross-model verdict table. The multi-model generalization of /psychomanteum-eval.
---

# Psychomanteum — Scry

*To scry: to divine in a reflective surface.* This is the project's deepest question made operational: **is a facet's pull universal or model-specific?** Does conditioning a facet steer an *arbitrary* model toward the lineage's region of latent space — and how does steerability vary by model (size, era, training)?

`scry` is `/psychomanteum-eval` generalized to **N target models, one held judge**. It reuses the same prober (battery + capture) and scorer (dashboard) per model, then aggregates the per-model dashboards into a single cross-model verdict.

Read `${CLAUDE_PLUGIN_ROOT}/prompts/eval-methodology.md` first — scry inherits every epistemic from eval (the negative control, the lens-transfer headline, scale discipline). What scry adds is **cross-model comparison**, which is only valid under three guarantees below.

## The three guarantees (why scry is not a loop)

The red-team correction **R4**: multi-model scry is NOT a `run_battery` loop over one file — `run_battery` is single-model (one `out_path`, one `target_model`) and on resume DROPS cells of a different model, so a naive loop lets the **last model overwrite the rest**. Scry is therefore structural:

1. **Build the battery ONCE.** One `battery.json`, shared verbatim by every model — identical probes, identical distractor, identical held-out. A `battery_fingerprint` (in `scry.json`) is asserted by the aggregator so a drift is caught, not silently compared.
2. **One per-model directory.** Each model writes its own `<model>/generations.json` + `<model>/dashboard.json`. No collision by construction.
3. **The judge is HELD.** One judge model (default `opus`) scores every model — judge contamination is common-mode and cancels. Recorded in `scry.json` for provenance (M6). It is *generation* that must be clean (below), not judging.

## Clean generation (read before choosing models)

The CLI backends (claude / codex / gemini) run behind vendor wrappers that inject hidden system context — the verified `contamination_caveat` that makes every CLI capture **RELATIVE-ONLY**. For a clean cross-model study, prefer **open/local models via ollama** (`ollama:` model strings): a clean `(system, user)` channel, real sampling params, and logprobs (a perplexity signal). The roster resolver flags any CLI backend as contaminated and the aggregator warns on mixed capture classes. Paid API/SDK adapters are deferred.

## Arguments

- **`<facet>`** (required) — the facet under test (name or path in `facets/`).
- **`--models <list>`** (required) — comma-separated roster: friendly names (`talkie,qwen2.5,olmo2`) and/or raw model strings (`ollama:...`, `headless-claude-code`). See `eval/scry.py` `DEFAULT_MODELS`; overlay with `chamber/models.toml`.
- **`--tier lean|full`** (default `lean`) — `lean` ≈ 11 probes, `full` ≈ 30. Cost scales `models × probes × 3`.
- **`--distractor <facet>`** (default auto) — the wrong-lineage negative control; auto-picks a different-lineage sibling from `facets/FACET_INDEX.md` (metadata only — honor the hermetic rule).
- **`--judge <model>`** (default `opus`) — the HELD judge; one judge for all models.
- **`--params <json>`** (optional) — sampling dict threaded into generation (`{"temperature":0.7,"seed":0}`); live for local/ollama, provenance-only for CLI.
- **`--out <dir>`** (default `eval-runs/scry-<facet>-<tier>-<date>/`).

## Generation Path

Run all Python through the dev venv (`.venv/bin/python` — it has `eval/requirements.txt` + `ollama` + `rich`). Generation for each model goes through the registry: `ollama:` → the clean local adapter; `headless-claude-code`/`codex`/`gemini` → the contaminated CLI adapters.

## Your Task

### Step 1: Validate + Resolve

Resolve `<facet>`. Resolve the **roster**: `python eval/scry.py` uses `resolve_roster` — confirm every name resolves (friendly or model string) and note which are **contaminated** CLI backends (warn; recommend a clean local roster). Resolve `--distractor` to a **different lineage** (error if it shares the facet's lineage — a same-lineage control invalidates everything). Resolve the held `--judge`.

### Step 2: Ensure Eval Inputs

Same as `/psychomanteum-eval`: confirm `corpus/eval-in-domain-topics.json` exists (or have the user run `/psychomanteum-read`); the anchor set + domain pool resolve from `${CLAUDE_PLUGIN_ROOT}/templates/`; a **held-out** slice of source passages is reserved (per-voice for a multi-voice corpus). Without held-out, stop.

### Step 3: Cost-Guard Gate (M3)

A full multi-model battery is hundreds of serialized generations behind the host CLI lock. **Estimate before spending:**

```bash
.venv/bin/python eval/cli.py scry-estimate '{"n_models": <N>, "n_probes": <≈11 lean / ≈30 full>}'
```

Present `total_generations` + `wall_min_est` and **confirm with the user before generating**. (After the battery is built, `scry.json` records the exact-count estimate.)

### Step 4: Build the Battery ONCE (spawn eval-prober for the first model)

Spawn **`eval-prober`** for the **first** model in the roster, instructing it to:
- write the battery to the **shared** path `<out>/battery.json` (not a per-model path),
- write generations to `<out>/<first-model-slug>/generations.json`,
- use the dev venv python, the resolved distractor, held-out, in-domain topics, anchor + domain pool, tier, and `--model <first-model-string>`.

The prober's battery is deterministic (same facet+corpus+tier ⇒ identical battery), so it is valid for **every** model — models 2..N reuse it without re-running the prober.

### Step 5: Write the Scry Manifest

```bash
.venv/bin/python eval/scry.py manifest \
  --run-dir <out> --facet <facet-path> --facet-name <facet> \
  --distractor <distractor-path> --distractor-facet <distractor-name> \
  --battery <out>/battery.json --tier <tier> \
  --models "<comma roster>" --judge <judge> [--params '<json>']
```

This fingerprints the shared battery, records the roster + held judge (M6), and writes `<out>/scry.json`.

### Step 6: Generate the Remaining Models (reuse the one battery)

For **each model after the first**, run the generation orchestrator **detached, then poll** (a dropped socket must not kill a long run; the driver checkpoints atomically and resumes):

```bash
nohup .venv/bin/python eval/scry.py generate \
  --run-dir <out> --model <model-string> \
  --facet <facet-path> --facet-name <facet> \
  --distractor <distractor-path> --distractor-facet <distractor-name> \
  --battery <out>/battery.json --tier <tier> \
  --held-out <held-out-path> [--params '<json>'] --timeout 300 \
  > <out>/<model-slug>/generate.log 2>&1 &
```

Sequential across models (the host lock serializes anyway). Poll each `<model>/generations.json` until done. Re-launch the identical command to resume a dropped run.

### Step 7: Score Each Model (spawn eval-scorer, judge HELD)

For **every** model (including the first), spawn **`eval-scorer`** with that model's `<model>/generations.json`, the held-out passages, the tier, and output `<model>/dashboard.json`. The judge is held constant (`--judge`, default opus) across all models — do not vary it within a scry. Run them sequentially (the judge contends on the same CLI lock).

### Step 8: Aggregate

```bash
.venv/bin/python eval/scry_aggregate.py <out>
```

Reads every `<model>/dashboard.json` (+ `generations.json` for fingerprint/capture/failures/perplexity) → writes `<out>/scry-dashboard.json` with one row per model, the constellation point-set, and honesty warnings (mixed capture, confounded controls, fingerprint mismatch, missing fields).

### Step 9: Render + Present

```bash
.venv/bin/python chamber/scry_table.py <out>/scry-dashboard.json
```

Surface the verdict table. **Lead with any aggregator `warnings`** — if a model's negative control is confounded, its row is `uninterpretable`; if capture classes are mixed, say cross-class comparison is invalid. Then read the constellation: who casts, who half-casts, who is mute, and (the headline) whether the spell crosses model lines. Never collapse to one number; the dashboard is the result.

## Cost

`lean` keeps it sane: `N × ~11 × 3` generations, serialized. `full` and large rosters are real spend — the Step 3 gate is mandatory. Baselines are per-model and cached within a model's own `generations.json` (resume reuses them).

## Notes

- **Determinism is the comparison.** The shared battery + fingerprint is what makes "model A vs model B" fair. Never regenerate the battery per model.
- **Clean beats convenient.** A local roster (ollama) yields an absolute, non-contaminated result; a CLI roster is relative-only. The table flags the difference.
- This measures *proximity to the corpus region across models*, not literary merit. Whether a strong cast is the *right* facet to have built stays a human call.
