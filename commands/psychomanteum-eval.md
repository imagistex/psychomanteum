---
name: psychomanteum-eval
description: Measure whether a facet points at its corpus—assemble the probe battery, capture real conditioned generations, score the dashboard + transfer curve against a wrong-lineage control. Supports before/after cohort comparison.
---

# Psychomanteum — Eval

Tests the plugin's central claim for one facet: *does conditioning a model on this facet move its output toward the corpus's region—in style, not just topic—and not toward a wrong lineage?* Orchestrates `eval-prober` (captures real generations) then `eval-scorer` (the dashboard). The output is never one number; it is a dashboard a human adjudicates.

Read `${CLAUDE_PLUGIN_ROOT}/prompts/eval-methodology.md` first—it is the epistemics this command operationalizes.

## Arguments

- **`<facet>`** (required) — the facet under test (name or path in `facets/`).
- **`--tier lean|full`** (default `lean`) — `lean`: ~11 probes, binned curve, released-user default. `full`: ~30 probes, dense cross-domain sampling, fitted curve with CIs (for deep/research runs).
- **`--distractor <facet>`** (default: auto) — the wrong-lineage negative control. Auto-picks a cross-lineage sibling from `facets/`; **must** be a different lineage.
- **`--target <model>`** (default: headless Claude Code) — the model being steered. See Generation Path.
- **`--compare <git-ref>`** (optional) — cohort mode: run the same battery on the facet at `<git-ref>` (e.g. `v0.1.0`) and on the current facet, and diff. This is the "stronger" proof.
- **`--out <dir>`** (default `eval-runs/<facet>-<tier>/`) — where the run artifacts land.

## Generation Path (today vs later)

- **Today — headless Claude Code.** Each generation is a headless `claude` invocation with the facet supplied as system-level conditioning and the flat `Describe [x].` as the user prompt. This is a fresher context than spawning in-plugin (less harness leakage). **Known limitation:** the host Claude Code wrapper injects its own system context even headless—these runs are *preliminary*, validating that the harness mechanism is clean and testable, not producing publication-grade numbers. The prober records `capture_method` so the scorer carries the caveat.
- **Multi-model — headless Codex / Gemini** are available as `--target` for the cross-model research question (does the cipher write a resonance differently across weights?).
- **Later — raw API + local open-weight models.** Deferred to a future open-weight / raw-API harness, when clean raw `(system, user)` calls (no wrapper) and logprob access (perplexity signal) and white-box activation reads become possible.

## Your Task

### Step 1: Validate + Resolve the Control

Resolve `<facet>`. Resolve `--distractor`: if not given, pick a sibling facet from a **different lineage** (read `facets/FACET_INDEX.md` for lineages; never read sibling *bodies* — index metadata only, honoring the hermetic rule). If the only facet present shares the target's lineage, error: a same-lineage distractor invalidates the control; ask the user to supply one or build one.

### Step 2: Ensure Eval Inputs

Confirm: `corpus/eval-in-domain-topics.json` exists (written at read time; if absent, tell the user to run `/psychomanteum-read` or hand-author it); the anchor set and domain pool resolve from `${CLAUDE_PLUGIN_ROOT}/templates/`; a **held-out** slice of source passages is reserved (eval-only, never distilled). The held-out passages are the scorer's voice standard—without them, stop.

### Step 3: Capture (spawn eval-prober)

Spawn `eval-prober` with: facet, corpus manifest + held-out passages, the three probe sources, the resolved distractor, target model, tier, and output path. It returns `generations.json` — the deterministic battery × three conditions, real generations, each with a measured content-distance.

### Step 4: Score (spawn eval-scorer)

Spawn `eval-scorer` with `generations.json`, held-out passages, tier, output path. It returns the dashboard: style-distance (paired, CI, *d*), pairwise-vs-source (order-swapped, voice/accuracy split), perplexity (if available), the transfer curve, the collapse-rate, and the **negative-control verdict**.

### Step 5: Present

Surface the dashboard. Lead with the **negative-control verdict**—if `confounded`, say plainly that the rest is uninterpretable and stop. Otherwise present the curve shape, the headline style-shift with its CI, the pairwise voice win-rate, and the **human-adjudication queue** (the implicit-style calls the metrics can't make). Never collapse to a single score.

### Step 6: Cohort Mode (if `--compare <ref>`)

The "stronger" proof—does the refactor measurably move the facet toward its corpus?

1. Extract the old facet non-destructively: `git show <ref>:facets/<name>.md > <tmp>` (do **not** checkout / disturb the tree).
2. Run Steps 3–4 on **both** the old and current facet, **same battery, same target, same distractor**. The battery is identical by construction (shared corpus → shared in-domain topics; static anchor + pool), so the comparison is fair.
3. Diff the dashboards: Δ style-shift (toward corpus centroid), Δ pairwise voice win-rate, change in curve shape (did it flatten?). Confirm **neither** moved toward the wrong-lineage corpus.
4. Report the delta as the verdict on "stronger." A null or negative delta is a real finding—report it honestly, not around.

## Cost

`lean` is the default precisely because the full battery × three conditions × generations is real spend. Baseline (unconditioned) generations are cacheable and shared across facets on the same target—reuse them. `full` is opt-in for deep runs.

## Notes

- Determinism is load-bearing: same facet + corpus + tier ⇒ identical battery, so cohort comparisons compare facets, not rulers.
- This command measures *proximity to the corpus*, not literary merit. A facet can resonate hard and still be the wrong facet to have built—that judgment stays human.