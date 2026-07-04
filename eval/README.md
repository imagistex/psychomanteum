# `eval/` — the psychomanteum eval harness (compute layer)

The numbers behind "does a facet point at its region?" This directory is the
**delegated compute** the eval agents call; the *judgment* lives in the agents and in `prompts/eval-methodology.md` (read that first — it is the epistemics this code serves). Here we only measure.

## Status

**Preliminary.** Generation runs today on **headless Claude Code** (see the
contamination caveat below), so absolute numbers are wrapper-contaminated and the cohort claim is **relative-only** (the contamination is common-mode and cancels in facet−baseline / facet−distractor deltas). Clean absolute numbers await the future raw-API `harnesses/` direction.

## Layout

| file | role |
|---|---|
| `metrics.py` | numeric core: `style_distance` (content-masked, y-axis), `content_distance` (topic, x-axis), `paired_stats` (bootstrap CI + Cohen's *d*), `fit_transfer` (the curve), `collapse_rate`; round-3 diagnostics: `centroid_confound_check` (genre-vs-voice tripwire), `verbatim_echo` (the hollow-tell) |
| `generate.py` | the generation primitive: a real, fresh, facet-conditioned generation (`system`=facet, `user`=probe) via headless Claude Code (+ Codex/Gemini) |
| `cli.py` | the single Bash entry point the agents call (JSON in / JSON out) |
| `requirements.txt` | core deps (numpy, scikit-learn, scipy); neural tier lives in `requirements-neural.txt` |
| `requirements-neural.txt` | OPTIONAL neural tier (sentence-transformers; StyleDistance + MiniLM weights). Opt-in; not installed by the core. |
| `scry.py` | multi-model SCRY generation orchestrator: roster resolution (model-string-pure), `scry.json` manifest + battery fingerprint + cost estimate (M3), per-model `run_battery` into per-model dirs (the R4 no-collision fix) |
| `scry_aggregate.py` | combine per-model dashboards → `scry-dashboard.json` (dual-schema reader: current `headline.*` + legacy `signals.*`); verdict gate, constellation point-set, honesty warnings |
| `harnesses/` | optional out-of-tree generation adapters (registered via import side-effect); `ollama.py` = clean local backend (real params + logprobs) |
| `test_metrics.py` | offline self-test (**102 checks** with core deps only / **103** when the neural tier is also installed — the neural tier runs one additional check; runs with no network) |
| `test_generate.py` | 22 offline unit tests + a guarded smoke test (one real generation iff the `claude` CLI is present; else SKIP) |
| `test_scry.py` | offline self-test for multi-model SCRY (**33 checks**: R4 no-collision plumbing, dual-schema aggregator, verdict-gate + interpretive-gate, roster collision guard, corrupt-file robustness, resume params back-compat, ollama adapter via a mocked client; no live model or agent) |

## Setup

System Python may lack the deps; use a venv:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r eval/requirements.txt        # core: numpy, scikit-learn, scipy
python eval/test_metrics.py                  # expect: 102/102 checks passed (core deps only; 103/103 if the neural tier is also installed — one additional check)
python eval/test_generate.py                 # 22 unit tests + a real pirate generation if `claude` is on PATH, else SKIP
python eval/test_scry.py                      # expect: 33/33 passed (offline; no model or agent)

# OPTIONAL neural tier (auto-detected at runtime; not needed for the core/tests):
pip install -r eval/requirements-neural.txt  # sentence-transformers (+ torch); model weights download on first use
```

The eval **agents** must invoke the CLI with a Python that has these deps (point them at the venv's interpreter).

## Entry point

```bash
python eval/cli.py <command> '<json-args>'
```

| command | json-args | returns |
|---|---|---|
| `generate` | `{"system","user","model"?}` | `{output, model, capture_method, ok, error}` |
| `style-distance` | `{"texts","corpus_passages","corpus_weights"?}` | `{distances, method}` |
| `content-distance` | `{"texts","corpus_passages","corpus_weights"?}` | `{distances, method}` |
| `paired-stats` | `{"facet_vals","baseline_vals"}` | `{mean_shift, ci_low, ci_high, cohens_d, n, n_boot}` — **`mean_shift` = mean(baseline − facet); POSITIVE = toward corpus** |
| `fit-transfer` | `{"distance","style_shift","tier"}` | `{shape, slope, breakdown_distance, points, fit}` — `style_shift` y is toward-corpus (same sign as `mean_shift`) |
| `collapse-rate` | `{"facet_path"}` | `{blocks, functions, ratio}` |
| `confound-check` † | `{"corpus_held_out_high_voice","distractor_outputs","corpus_passages","corpus_weights"?}` | `{confounded, held_out_mean_dist, distractor_mean_dist, margin, n_held_out, n_distractor, method, recommendation}` — **`confounded=true` ⇒ centroid measures genre not voice ⇒ fall back to pairwise** |
| `verbatim-echo` † | `{"texts","corpus_passages","n_lo"?,"n_hi"?}` | `[{echo_fraction, per_n, longest_verbatim_span_tokens, n_tokens}, …]` — the hollow-tell; **only measures, scorer owns the threshold** |

† Round-3 diagnostics. The functions exist in `metrics.py` (and in its own `__main__` dispatch); the `eval/cli.py` rows above are how the CLI wires these.

## Generation contamination caveat (read before trusting absolute numbers)

`generate.py` uses `claude --bare -p --system-prompt <facet> --output-format json`.
`--system-prompt` *does* steer the output (verified: a "you are a pirate" system prompt yields sustained pirate voice). **But** the host CLI wrapper injects its own system prompt even in `--bare`: a 2-token user + ~45-char system measured **~2444 cache-creation input tokens**, i.e. a large hidden system prompt we did not author. So this is `(wrapper_system + facet, user)`, not a clean `(facet, user)`.

- **Recorded:** every generation carries `capture_method="headless-claude-code"` so it is never mistaken for a clean capture.
- **Why it's OK for now:** the wrapper term is **common-mode** — identical across facet / baseline / distractor — so *relative* deltas reject it. Absolute numbers do not; that's why this round is relative-only.
- **Codex / Gemini** have no clean system channel; the facet is folded into the prompt (weaker, recorded as `headless-codex` / `headless-gemini`). Use for the cross-model question, not for clean absolutes.

## Sign convention (ONE defined direction: toward-corpus is POSITIVE)

Distances are *lower = closer to the corpus centroid*. Every facet-vs-baseline shift in this module is therefore computed as **`baseline_dist − facet_dist`**, so:
- **`paired_stats.mean_shift` POSITIVE ⇒ the facet moved CLOSER to the corpus than the baseline ⇒ toward corpus.** Negative ⇒ away. `cohens_d` carries the same sign.
- **`fit_transfer`'s y-axis (`style_shift`) uses the same convention** — the per-probe toward-corpus shift is exactly `baseline_dist − facet_dist`, so a *positive-and-flat* curve is robust transfer and a curve that *decays toward zero* as content-distance grows is home-turf-only. The headline number and the transfer curve never disagree in sign.

## Voice-stratified centroid (`corpus_weights`)

The corpus mixes voice-bearing source with encyclopedic scaffolding; a uniform centroid is diluted by the scaffolding and drifts toward TOPIC rather than VOICE. `style_distance` / `content_distance` accept an optional **`corpus_weights`** list parallel to `corpus_passages` that weights each passage's contribution to the centroid (the corpus column **scale/ruler stays unweighted** — only the centroid moves). Convention: `voice_charge` high → `1.0`, medium → `0.5`, low → `0.0`, but weights are taken **as given**. Convenience: pass corpus entries as dicts with a `voice_charge` field (and optional `text`/`weight`) and the weights are derived; an explicit `corpus_weights` argument overrides per-entry weights. Default `None` = uniform (original behavior). `method.centroid_weighting` reports `uniform` vs `voice_stratified`.

> **⚠️ `corpus_weights` is NEAR-INERT on the content-masked STYLE axis**. It moves the masked-style centroid only **~1e-04 cosine**, because `voice_charge` varies along **content**, and the style axis masks content by construction (function words + punctuation + length; content words length-preserved as `x`). Down-weighting "low-voice" encyclopedic passages barely moves a centroid that never encoded their topic. **The param is kept** (the scorer and the test-suite pass it, and it is *effective on the content axis*) but on the style axis it is effectively a no-op. **The right lever on the style axis is a curated / genre-matched corpus SUBSET** passed as `corpus_passages` (e.g. verse-only for a poetry lineage), which reshapes the ruler itself. When weights are supplied to `style-distance`, the returned `method` carries a **`style_weighting_warning`** flag so the no-op is visible. (No such flag on `content-distance` — weighting belongs there.)

## Dependency tiers

- **Core (required):** `numpy`, `scikit-learn`, `scipy` (`requirements.txt`).Stylometry (style axis, `method="classical_stylometry"`) + TF-IDF (content axis, `method="tfidf_cosine"`) run with *only* these — no downloads, no network.
- **Optional / neural (guarded):** `sentence-transformers` (`requirements-neural.txt`) pulling `StyleDistance/styledistance` (neural style) and `all-MiniLM-L6-v2` (neural content). When importable and the weights load, the functions upgrade automatically and record the path in `method` (`"classical_stylometry+neural_style"` for style—the neural block is *concatenated onto* the classical floor; `"neural_content_embedding"` for content). When absent, they fall back and say so. A missing signal is reported, never hidden.

## Determinism

The only randomness is the seeded bootstrap in `paired_stats` (`default_rng(0)`). Same inputs → same numbers, so cohort before/after comparisons compare facets, not noise. (The probe battery is likewise deterministic — see `agents/eval-prober.md`.)

## How the agents use it

- **`eval-prober`** → `generate` (per probe × condition) + `content-distance` (to stratify cross-domain) → writes `generations.json`.
- **`eval-scorer`** → `style-distance`, `paired-stats`, `fit-transfer`, `collapse-rate` (+ its own LLM pairwise judging) → the dashboard.
- **`verifier-resonance`** → `generate` (one real probe per attune iteration).

Full eval runs are token-heavy and meant to run in a dedicated/parallel session.