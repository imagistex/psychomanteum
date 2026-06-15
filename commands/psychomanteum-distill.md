---
name: psychomanteum-distill
description: Compression phase—distiller compresses passages into dense distilled material; human review gate
---

# Psychomanteum—Distill

Orchestrates the compression phase. Spawns one `distiller` per facet function, each given an explicit section-boundary spec, **parallel in 2 waves** (substance sections first, then frame sections handed wave-1's commitments). Reads from the aggregated passages, produces distilled material with provenance, ends in a human review gate. Strict-sequential is reserved for small facets or when dedup proves hard.

## First: Read Reference Files

1. `.psychomanteum-config.md`
2. `.psychomanteum-state.json`—must be phase `read`
3. `corpus-manifest.json`—for passages and sources
4. `corpus/passages.json`—the aggregated passage file (passages marked `held_out: true` are eval-reserved at read time; distillers skip them—never distill held-out)
5. `${CLAUDE_PLUGIN_ROOT}/prompts/esoteric-compression.md`—reference for understanding what the distiller is doing
6. `${CLAUDE_PLUGIN_ROOT}/templates/distill-gate.md`—gate template

## Your Task

### Step 1: Validate State

Must be `phase: "read"`. Error otherwise.

### Step 2: Prepare Working Directory

```bash
mkdir -p _psychomanteum-work/distill
mkdir -p distilled
```

### Step 3: Plan Distiller Spawns

Distillation runs **parallel-with-boundary-specs, in 2 waves**—each distiller gets an explicit section-boundary spec (its lane) and the substance sections distill first so the frame sections can reference their commitments. The seven functions a facet body must serve:

1. situate
2. declare-stance
3. mark-the-territory (potentially multiple subsections)
4. name-the-failure-modes
5. locate-among-neighbors
6. point-at-the-region
7. close-on-a-corpus-line

**Note:** `point-at-the-region` is pervasive—the whole body's aim, not a discrete unit. Do NOT spawn a standalone distiller for it; its charged/activating material is folded into the others (the distiller selects the most activating passages while distilling the rest). Spawn distillers for the other six functions.

For `mark-the-territory`, decide whether to spawn one distiller for the whole function or multiple per subsection. The orchestrator's choice: if passages tagged `subsection_candidate` cluster around clear sub-themes (e.g., "epistemological_commitments", "foundational_vocabulary", "frameworks"), spawn one distiller per subsection. Otherwise, one for the whole function.

**Group the six functions into two waves:**

- **Wave 1 — substance sections (run in parallel):** `situate`, `declare-stance`, `mark-the-territory` (incl. its subsections), `name-the-failure-modes`. These establish *what the register is and what it commits to*; they don't depend on each other—a clean section-boundary spec keeps them in their lanes.
- **Wave 2 — frame sections (run in parallel, after wave 1):** `locate-among-neighbors`, `close-on-a-corpus-line`. These *frame and close on* the substance, so they're handed wave-1's commitments (the one-sentence `commitment` from each wave-1 distiller, plus the section-boundary map) and told to position/close against them, not restate them.

**Boundary spec (give every distiller its lane):** each distiller's prompt states explicitly *your lane is X; don't cross it; push out-of-scope material to the neighbor that owns it.* Sketch the whole map so each one knows the borders, e.g.: foundation/situate = who-I-am; declare-stance = what-this-is-for (affirmative-first); mark-the-territory = the commitments/frameworks/vocabulary; name-the-failure-modes = the refusals; locate-among-neighbors = the axes + nearest kin; close = the single corpus line. A distiller that finds material belonging to a neighbor flags it for that neighbor rather than absorbing it.

**When to fall back to strict-sequential:** reserve strict-sequential (each distiller sees all prior distillations before running) for **small facets**, or when **dedup proves hard**—if a first parallel wave comes back with heavy cross-section overlap that the boundary specs didn't prevent. In the default parallel-with-waves path, the attune loop is the backstop for any residual cross-section overlap.

### Step 4: Execute the Two Waves

**Wave 1 (parallel):** spawn the substance distillers together (`situate`, `declare-stance`, `mark-the-territory` + subsections, `name-the-failure-modes`). Wait for the whole wave to complete.

**Wave 2 (parallel):** spawn the frame distillers together (`locate-among-neighbors`, `close-on-a-corpus-line`), handing them wave-1's results. Wait for completion.

For each distiller, the agent prompt includes:
- Facet name
- Function (and subsection if applicable)
- **Section-boundary spec:** this distiller's lane + the whole section map, with the instruction "stay in your lane; push out-of-scope material to the neighbor that owns it" (see Step 3)
- Passages path: `corpus/passages.json`
- Lineage description (from config)
- **(Wave 2 only) Wave-1 commitments:** the one-sentence `commitment` from each wave-1 distiller, so frame sections position/close against the established substance without restating it
- Output path: `_psychomanteum-work/distill/<function>[-<subsection>].json`

The boundary specs (not turn-order) are what keep distillers from duplicating commitments across functions; the two-wave ordering exists only because the frame sections genuinely depend on the substance. If overlap survives both, fall back to strict-sequential per Step 3, with the attune loop as the final backstop.

For functions with 0 passages tagged:
- `locate-among-neighbors`: write a placeholder distillation: `_(no neighbors declared)_`
- Other functions: skip and warn user; the facet will be sparse for that function

### Step 5: Aggregate Distillations

Collect all distiller outputs into `distilled/sections.json`:

```json
{
  "facet_name": "{FACET_NAME}",
  "distilled_at": "ISO-8601",
  "sections": [
    { /* per distiller output */ }
  ]
}
```

### Step 6: Update Corpus Manifest

Add distillations to `corpus-manifest.json` `distillations[]` array, with full provenance (which passages each distillation compressed).

### Step 7: Generate Distill Gate

Read `${CLAUDE_PLUGIN_ROOT}/templates/distill-gate.md`. Fill in:
- Distillations per function
- Provenance table (function → distillation IDs → source passages → compression ratio)
- Self-flagged distillations from distiller `self_check` fields
- Epigraph candidates (may be multiple—let user choose)

Write to `_psychomanteum-work/distill-gate.md`.

### Step 8: Present Gate to User

Show the gate. **These options are a menu, not a form—accept a plain-language reply** (prose like "revise the stance section, it's too hedged" or "looks good, proceed"); never require a numbered pick, and honor *stepping away* as valid (silence = pause, not abandonment). Map the reply to one of:

1. **Approve**—advance to phase `distilled`; cleanup working dir; ready for inscribe
2. **Revise a function**—specify function + what's wrong; re-spawn that distiller with extra guidance
3. **Expand a function**—corpus may have under-served this function; suggest returning to gather/read with emphasis
4. **Cut a function**—if a function's material is genuinely empty, mark it as `(none)` and proceed (the cipher will leave it sparse)
5. **Discuss**—analysis
6. **Pause**—save state, exit (also the default when the user goes quiet)

### Step 9: On Approve

- Wipe `_psychomanteum-work/distill/`
- Update `.psychomanteum-state.json`: phase → `distilled`
- Suggest: `/psychomanteum-inscribe`

## Error Handling

- A distiller producing surface-summary output (signal-per-token estimate <0.5 in its self_check): warn user; suggest re-spawn with tighter guidance
- A distiller hallucinating compression that doesn't trace to passages: hard error; the provenance must be verifiable
- Very long distillations (>500 words for a single function): warn; the cipher will likely need to compress further