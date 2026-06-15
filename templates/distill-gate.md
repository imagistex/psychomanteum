# Distill Gate—Human Review

**Facet:** `{{FACET_NAME}}`
**Generated:** {{GATE_GENERATED_AT}}
**Phase:** `distill` complete; awaiting your approval to proceed to `inscribe`.

---

## What the Distiller Produced

The distiller worked function-by-function, compressing passages from the corpus into dense distilled material. Below are the distillations grouped by the function they serve. (The body is free-form—function, not form; the cipher decides the final shape. *point-at-the-region* is pervasive—its charged/activating material is folded into the others, not distilled as a standalone unit.)

### Situate
{{SITUATE_DISTILLATIONS}}

### Declare Stance (affirmative-first)
{{DECLARE_STANCE_DISTILLATIONS}}

### Mark the Territory
{{MARK_THE_TERRITORY_DISTILLATIONS}}

*Subsections varied by lineage; see provenance for each.*

### Name the Failure Modes
{{NAME_THE_FAILURE_MODES_DISTILLATIONS}}

### Locate Among Neighbors
{{LOCATE_AMONG_NEIGHBORS_DISTILLATIONS}}

### Closing Epigraph Candidate(s) (close on a corpus line)
{{EPIGRAPH_CANDIDATES}}

## Provenance Summary

| Function | Distillation IDs | Source Passages | Compression Ratio |
|---|---|---|---|
{{PROVENANCE_TABLE}}

*For each function: which distillations were produced, which passages they compressed, and how aggressively (output_words / input_words).*

## Density Check (Pre-Verify)

The distiller self-flagged distillations that may need revision:

{{SELF_FLAGGED_DISTILLATIONS}}

*The full verifier-density check runs during `attune`. This is just the distiller's own pre-flag.*

## Your Options

1. **Approve and proceed** to `/psychomanteum-inscribe`—accept these distillations as the cipher's input
2. **Revise a function**—identify a function that needs re-distillation (specify function + what's wrong)
3. **Expand a function**—corpus may have under-served this function; return to gather or read with additional emphasis
4. **Cut a function**—if a function's material is genuinely empty (no passages found that fit), it will be sparse in the final facet
5. **Discuss**—ask the orchestrator for analysis
6. **Pause**—save state and exit

## What Happens on Approve

- The distillations are committed to `corpus-manifest.json` as `distillations[]`
- The pipeline advances to phase `inscribe`
- `cipher` will assemble the distilled material into a facet file, in the corpus's own voice and form

## What to Watch For

- **Surveys, not distillations**: if a distillation reads like a Wikipedia survey of the lineage rather than as a position-within-it, the distillation has failed. Revise.
- **Missing jargon**: if the distillation lost the in-group vocabulary (the lexical territory markers), the distiller may have over-gloss-stripped. Revise.
- **Authorial summary phrases**: "Fisher argues that..." "Lowell shows us..."—these are flags that the distiller wrote *about* the corpus rather than *from inside* it. Revise.
- **Flat metaphors**: metaphors that feel like decoration rather than work. Cut or replace.
- **Distillation length wildly varies**: very short or very long distillations often signal that the corpus is unbalanced. Note for the cipher's awareness.
