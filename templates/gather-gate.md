# Gather Gate — Human Review

**Facet:** `{{FACET_NAME}}`
**Generated:** {{GATE_GENERATED_AT}}
**Phase:** `gather` complete; awaiting your approval to proceed to `read`.

---

## What the Gatherers Found

| Gatherer | Sources Found | Status |
|---|---|---|
| `gatherer-encyclopedic` | {{ENC_COUNT}} | {{ENC_STATUS}} |
| `gatherer-lexicon` | {{LEX_COUNT}} | {{LEX_STATUS}} |
| `gatherer-canon` | {{CANON_COUNT}} | {{CANON_STATUS}} |
| `gatherer-voices` | {{VOICES_COUNT}} | {{VOICES_STATUS}} |
| **After gleaning (dedup)** | **{{FINAL_COUNT}}** | |

## Content Integrity (auto-checked)

| Check | Result |
|---|---|
| Content-bearing sources (non-empty `content`) | {{CONTENT_BEARING_COUNT}} / {{FINAL_COUNT}} |
| By type | encyclopedic {{ENC_TYPE_COUNT}} · lexicon {{LEX_TYPE_COUNT}} · canon {{CANON_TYPE_COUNT}} · **voice {{VOICE_COUNT}}** |
| Integrity assertion | {{INTEGRITY_VERDICT}} — content-bearing == total, voice > 0 |
| Canonical truncation (written vs reported bytes) | {{TRUNCATION_VERDICT}} — {{N_TRUNCATION_FLAGS}} flagged |

*You should see ✓ here. If content-bearing < total, or voice = 0, consolidation lost material — the orchestrator rebuilds from `gather/*.json` before this gate is shown. The voice layer is the one historically dropped; confirm it survived. **A truncation flag means a canonical work arrived suspiciously small (written ≪ reported bytes) — a silent `WebFetch` summary, not a thin source; see "What to Watch For."***

## Candidate Sources

{{SOURCES_TABLE}}

*Table format: `| # | Type | Title | Author | URL | Relevance | Notes |`*

## Coverage Assessment

The gleaner attempted to fill gaps. Coverage of declared seeds:

{{SEED_COVERAGE_TABLE}}

*For each seed: which gatherer caught it, how many sources, whether the seed is well-represented.*

**Coverage notes from gleaner:** {{COVERAGE_NOTES}}

## Lineage Tags Surfaced

The gatherers noted these recurring tags across sources:

{{LINEAGE_TAGS}}

*If unfamiliar tags appear, they may reveal sub-lineages you didn't seed. Consider whether to expand.*

## Your Options

1. **Approve and proceed** to `/psychomanteum-read` — accept this candidate set as the corpus
2. **Select** — accept a subset (specify by number)
3. **Exclude** — remove specific sources (specify by number)
4. **Expand** — return to `/psychomanteum-gather` with additional seeds (specify what to add)
5. **Discuss** — ask the orchestrator for analysis of what's here / what might be missing
6. **Pause** — save state and exit; resume later with `/psychomanteum-status` to see where you are

## What Happens on Approve

- The gleaner's `_psychomanteum-work/gather/` working directory is wiped
- The approved sources are written to `corpus-manifest.json` as `sources[]`
- The pipeline advances to phase `read`
- `essence-reader` will run per-source to extract key passages

## What to Watch For

- **Wrong-lineage drift**: if a source slipped in that belongs to a different lineage (e.g., a Mark Fisher facet picking up a contemporary cultural-studies survey that gestures at Fisher but is not in his line), exclude it now.
- **Voice-killing sources**: if a source is a *summary* of the lineage rather than *from* the lineage (e.g., a SparkNotes-style explainer), exclude it. The cipher needs voice-bearing material, not surveys.
- **Sufficient density**: 8-15 high-quality sources is typically sufficient for a facet. Fewer than 5 risks under-distillation. More than 25 risks distillation drowning.
- **Truncated canon (silent — passes every other check)**: a canonical work that should be book-length arriving at a few KB is a `WebFetch` summary, not a thin source — and it *passes* the content-bearing and anchor checks. If a source is flagged for truncation (written ≪ reported bytes), do **not** approve it as-is: re-gather it via the raw-download path (`Expand`/`Exclude`), or the facet is built on a fragment. The *Ethics* once arrived at 7,190 of 531,560 chars and "verified" on its opening and closing lines.
