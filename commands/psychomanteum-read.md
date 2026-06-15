---
name: psychomanteum-read
description: Ingestion phase—essence-reader extracts key passages from each approved source with provenance
---

# Psychomanteum—Read

Orchestrates the ingestion phase. Spawns one `essence-reader` per approved source (parallel in batches), each extracting key passages tagged by candidate facet function. No human gate at the end—the next gate is at distill.

## First: Read Reference Files

1. `.psychomanteum-config.md`
2. `.psychomanteum-state.json`—must be phase `discovered`
3. `corpus-manifest.json`—for the approved sources list

## Your Task

### Step 1: Validate State

Read `.psychomanteum-state.json`. Must be `phase: "discovered"` — **OR** `phase: "initialized"` with `corpus_source: "manual"` (provided-corpus mode skips gather; the corpus was supplied by hand — see Step 2). Otherwise error.

### Step 2: Read Source Inventory

**Gather mode (`corpus_source: gather`, the default):** Read `corpus-manifest.json`. Count sources in `sources[]`. If zero, error: `"No sources in corpus. Run /psychomanteum-gather first."`

**Provided-corpus mode (`corpus_source: manual`):** the corpus was supplied by hand and gather was skipped—ingest `corpus/manual/` into the manifest now, so the rest of the pipeline treats provided sources identically to gathered ones:

1. List `corpus/manual/`. If empty, error: `"Provided-corpus mode but corpus/manual/ is empty — add source files, or re-init in gather mode."`
2. For each file, extract its text (plain text as-is; PDF via `pdftotext`; epub/mobi via `pandoc`/`ebook-convert`—see the formats note in `prompts/retrieval-discipline.md`). Apply the **authenticity gate** lightly: confirm the extraction is real text, not an extraction-failure stub (a scanned PDF with no text layer needs OCR or a re-supply—never write empty `content` as success).
3. Write each as a source record into `corpus-manifest.json` `sources[]`: `{ "id": "SRC-<n>", "title": "<declared title or filename>", "author"/"year" if known, "type": "canon"|"voice"|… (best inference), "url": null, "fetch_status": "provided", "load_quality": "full", "content": "<extracted text>", "provenance": "corpus/manual/<filename>" }`. The content-bearing rule holds: a file that won't extract is a failure to surface, never an empty-as-success.

Then proceed exactly as gather mode—the sources are now in the manifest.

### Step 3: Prepare Working Directory

```bash
mkdir -p _psychomanteum-work/read
```

### Step 4: Plan Parallel Spawns — Scale the Read Unit by Corpus Size

The read unit scales with corpus size so no essence-reader ever loads the full manifest (a per-source spawn against a 540K manifest = N redundant heavy reads, ~135K tokens each). Use the source count from Step 2 to pick the mode:

**Below ~40 sources — one essence-reader per SOURCE** (the default for small/medium corpora):

1. **Pre-split** the manifest into per-source files so each reader loads only its own small record, never the whole manifest:
   ```bash
   mkdir -p _psychomanteum-work/read/sources
   jq -c '.sources[]' corpus-manifest.json | while read -r src; do
     id=$(echo "$src" | jq -r '.id')
     echo "$src" > "_psychomanteum-work/read/sources/${id}.json"
   done
   ```
2. One `essence-reader` per source. For ~15 sources, that's ~15 spawns. Batch in groups of 5-6.
3. Each agent prompt includes:
   - Facet name
   - Source ID (e.g., SRC-007)
   - Source content path: `_psychomanteum-work/read/sources/<source-id>.json` (its own small file—**not** the full manifest)
   - Facet lineage description (from config)
   - Output path: `_psychomanteum-work/read/<source-id>-passages.json`

**At/above ~40 sources — one essence-reader per gather FILE / per anchor** (a coherent grouped unit—a poet's collection, an archetype haul):

At scale, per-source spawns become intractable (125 sources ≈ 21 batches). The gather files are already coherent per-unit splits, so spawn **one essence-reader per gather file** (e.g., 26 files ≈ 5 batches). This satisfies I10 better—each reader loads one small grouped file, never the full manifest—and gives cross-source context for better passage selection across a collection.

1. The grouped units are the original `gather/*.json` files (or anchor-grouped subsets if the manifest carries an `anchor`/`wing` tag). Each is already a small, self-contained file.
2. One `essence-reader` per gather file / per anchor. Batch in groups of 5-6.
3. Each agent prompt includes:
   - Facet name
   - The grouped unit's identifier (gather file name or anchor)
   - Source content path: the single grouped file (e.g., `gather/<gatherer>.json`)—its own small file, **never** the full manifest
   - Facet lineage description (from config)
   - Output path: `_psychomanteum-work/read/<unit-id>-passages.json`

Either way, the invariant is: **each essence-reader loads only its own assigned small file (per-source OR per-file), never the full `corpus-manifest.json`.**

### Step 5: Execute Parallel Spawns

Spawn batches; wait for each batch; track success/failure.

### Step 6: Aggregate Passages

After all essence-readers complete, aggregate passage outputs:

- Read each `<source-id>-passages.json` (or `<unit-id>-passages.json` in per-file mode)
- Concatenate all passages into a single array
- **Assign globally-unique passage IDs.** Essence-readers number passages `PSG-001..N` independently per source/unit, so raw `PSG-NNN` collide across sources (the same `PSG-001` under many sources). At aggregation, rewrite each passage's `id` to a globally-unique form by **prefixing with its `source_id`** — `<source_id>-PSG-NNN` (e.g. `TBO-007-PSG-003`), preserving the local number so per-source order stays legible:
  ```bash
  jq '[.[] | .id = (.source_id + "-" + .id)]' _psychomanteum-work/read/all-passages.json > corpus/passages.json
  ```
  Propagate the rewrite to `corpus-manifest.json` `passages[]` and to any in-passage cross-references, so distiller/cipher provenance markers (`[<SRC>-PSG-NNN]`) are unambiguous end to end.
- Verify each passage has required fields (id [now global], source_id, text, function_candidate, lineage_tags, voice_charge)
- Write aggregated passages to `corpus/passages.json`

### Step 7: Coverage Summary

Build a summary of function coverage across all passages:

```json
{
  "total_passages": 142,
  "passages_per_function": {
    "situate": 18,
    "declare-stance": 12,
    "mark-the-territory": 67,
    "name-the-failure-modes": 19,
    "locate-among-neighbors": 4,
    "point-at-the-region": 1,
    "close-on-a-corpus-line": 21
  },
  "passages_per_source": {"SRC-001": 8, "SRC-002": 12, ...},
  "voice_charge_distribution": {"high": 47, "medium": 71, "low": 24}
}
```

Write to `corpus/read-summary.json`.

### Step 8: Function Coverage Warnings

If any function has 0 passages, warn user:
- `locate-among-neighbors` with 0 is common (many corpora don't surface their kin / adjacency); use a default note
- `point-at-the-region` with 0 is *not* a gap — it is a pervasive function the whole facet serves, not a discrete passage type to spawn against; skip the warning
- Other functions with 0 indicate a real gap

For functions with very low coverage (<3 passages), warn user; suggest they may want to expand gather before distill — but exempt `point-at-the-region` (its scarcity at the passage level is expected, not a coverage problem).

### Step 9: Eval Preparation — Held-Out Reservation + In-Domain Topics

Two read-time preparations the eval harness depends on, both drawn from the **corpus**, never the facet.

**9a — Reserve held-out passages (so every build is eval-clean by construction).**

The eval's pairwise-vs-source judge compares facet output against *real corpus passages the facet never saw*. Reserve those now, **before distillation**, or the comparison leaks (the facet would be judged against material it was distilled from).

- Select a **deterministic ~15%** of the aggregated passages, **stratified across `voice_charge`** so both the held-out set and the distill set span the voice range—don't exile all high-voice passages (the distiller needs voice; the scorer needs a real voice standard). Deterministic selection (e.g., sort by `function_candidate`, then `voice_charge`, then `id`; take every ~7th)—no randomness, so re-runs and the cohort stay stable. **Also stratify across major source-voices:** when the corpus spans several anchor authors, reserve held-out from *each*, so the eval can judge *placeable-in-the-lineage* not *mistakable-for-one-member*. Prefer genuinely **high-voice** fragments as the held-out standard (the scorer's pairwise compares against these; the essence-reader's voice_charge audit should already have down-rated encyclopedic passages, which make a poor voice standard). **Reserve a register-representative slice**, not only the densest/most-opaque passages: a held-out standard made entirely of dense-monograph prose makes the bar pure opacity—unfair to a facet that (rightly) varies register and to low-affordance probes. For dense-monograph lineages, looser-register sources (e.g. lectures) belong in the corpus at gather, so held-out then spans the lineage's real range.
- **Guards (small corpora):** never hold out >20%; keep the distill set ≥85% and ≥30 passages. If the corpus is too small to afford a slice (< ~20 passages), **skip held-out with a warning**—that facet's eval is then relative-only / leaky, like the pre-held-out cohort.
- Mark each reserved passage `held_out: true` in `corpus/passages.json` and the manifest, and write the reserved subset to `corpus/held-out-passages.json` (the scorer's voice standard). **Held-out passages are excluded from distillation**—the distiller skips `held_out: true`.

**9b — Extract in-domain eval topics.**

The eval harness (`/psychomanteum-eval`) probes the facet with flat `Describe [x].` prompts at a range of distances from the corpus. The **in-domain** (closest) end of that range is the corpus's own salient topics—extract them here, at read time, from the **corpus** (not the facet), so they stay stable across rebuilds (a v0.1.0 and a v0.2.0 facet of the same corpus share them) and leak no held-out passage (a theme is not a quote).

From the aggregated passages, identify the **3–5 topics the corpus most centrally concerns**, phrased as flat, affect-neutral keywords suitable for `Describe [x].` (confessional → `shame`, `the body`, `the mother`; capital-realist → `the economy`, `work`, `the future`). Topics, not theses: `shame`, not "the unbearability of shame."

**Respect manual curation:** if `corpus/eval-in-domain-topics.json` already exists with `"source": "manual"`, do **not** overwrite it. Otherwise write:

```json
{
  "source": "auto",
  "note": "In-domain eval probes (corpus's most salient topics, flat-toned). MANUAL OVERRIDE: set source to \"manual\" and edit topics by hand; the eval harness uses this file verbatim and will not re-extract.",
  "template": "Describe {keyword}.",
  "topics": ["...", "...", "..."]
}
```

### Step 10: Cleanup + State Update

- Move `_psychomanteum-work/read/` into permanent `corpus/` directory (as `corpus/per-source-passages/`)
- Update `.psychomanteum-state.json`: phase → `read`, add to `phases_completed`
- Update `corpus-manifest.json` `passages[]` with the aggregated passages
- Display read-summary to user

### Step 11: Suggest Next Step

Report:
- Total passages extracted
- Coverage summary
- Warnings (if any)
- Next: `/psychomanteum-distill`

## Error Handling

- Individual essence-reader failures: log to `_psychomanteum-work/read-errors.log`; continue with successes. If >30% fail, prompt user to investigate before distill.
- Source content too large to read fully: essence-reader handles via oversize-fallback; passages should still be extracted with `load_quality: "partial"` notes propagating up.