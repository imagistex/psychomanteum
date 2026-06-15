---
name: psychomanteum-status
description: Display the current state of the in-progress facet build—phase, counts, next steps
---

# Psychomanteum—Status

Read-only diagnostic command. Shows where the in-progress facet build is, what's been done, and what to do next. No agents spawned, no state mutated.

## First: Read Reference Files

1. `.psychomanteum-config.md` (if exists; otherwise the working dir is not a psychomanteum project)
2. `.psychomanteum-state.json`
3. `corpus-manifest.json` (if exists)

## Your Task

### Step 1: Detect Project

If `.psychomanteum-config.md` and `.psychomanteum-state.json` are not present in the current working directory: report that this is not a psychomanteum project; suggest `/psychomanteum-init`.

### Step 2: Read State

Read all three reference files. Determine:
- Facet name
- Current phase
- Phases completed
- Counts (sources, passages, distillations, drafts, iterations)
- Last action timestamp (from most recent iteration_history entry or phase transition)

### Step 3: Display Status

Format and display:

```
═══════════════════════════════════════════════════════════════
 PSYCHOMANTEUM STATUS—{{facet-name}}
═══════════════════════════════════════════════════════════════

Facet:        {{facet-name}}
Title:        {{facet-title}}
Lineage:      {{first 100 chars of lineage_description}}...
Phase:        {{current_phase}}
Started:      {{created_at}}
Last action:  {{last_action_timestamp}}

─── Pipeline ────────────────────────────────────────────────

  init ──── ✓ ──── (initialized {{created_at}})
  gather ── {{✓ or □}} ── ({{n_sources}} sources, gathered {{when_or_pending}})
  read ──── {{✓ or □}} ── ({{n_passages}} passages from {{n_sources_read}} sources)
  distill ─ {{✓ or □}} ── ({{n_distillations}} functions distilled)
  inscribe  {{✓ or □}} ── (cipher confidence: {{voice_confidence_or_pending}})
  attune ── {{✓ or □}} ── (iteration {{current_iter}}/{{max_iter}})
  bind ──── {{✓ or □}} ── ({{bound_path_or_pending}})

─── Detail ──────────────────────────────────────────────────

{{phase-specific detail based on current phase—see below}}

─── Next ────────────────────────────────────────────────────

Recommended next command: {{next_command}}
```

### Step 4: Phase-Specific Detail

**If phase == `initialized`:**
```
Seeds declared: {{seed_count}}
Install destination: {{install_path}}
Ready to gather. No work products yet.
```

**If phase == `discovered`:**
```
Sources approved: {{n_sources}}
By type: encyclopedic={{n_enc}}, lexicon={{n_lex}}, canon={{n_canon}}, voices={{n_voices}}
Coverage: {{n_well_served}}/{{n_seeds}} seeds well-served
Ready to read.
```

**If phase == `read`:**
```
Passages extracted: {{n_passages}}
Function coverage:
  situate:                {{n_situate}}
  declare-stance:         {{n_declare_stance}}
  mark-the-territory:     {{n_mark_territory}}
  name-the-failure-modes: {{n_failure_modes}}
  locate-among-neighbors: {{n_locate_neighbors}}
  point-at-the-region:    {{n_point_region}}
  close-on-a-corpus-line: {{n_close_corpus_line}}
Voice charge: high={{n_high}}, medium={{n_med}}, low={{n_low}}
Ready to distill.
```

**If phase == `distilled`:**
```
Functions distilled: {{n_functions}}
Compression ratios per function:
  ...
Ready to inscribe.
```

**If phase == `inscribed`:**
```
Cipher draft: drafts/<facet-name>-iter0.md
Voice confidence: {{voice_confidence}}
Voice memo: "{{voice_memo}}"
Lines: {{line_count}}
Ready to attune.
```

**If phase == `attuning`:**
```
Current iteration: {{N}}/{{max}}
Latest verifier verdicts:
  density:     {{verdict}} (signal: {{signal}})
  resonance:   {{verdict}} (score: {{score}})
  strangeness: {{verdict}} ({{n_high_sev}} high-severity)
Convergence signal: {{convergence}}

Trajectory: {{summary across iterations}}

Either continue iterating or accept the latest draft.
```

**If phase == `attuned`:**
```
Final iteration: {{N}}
Final verdicts: density={{pass/fail}} resonance={{pass/fail}} strangeness={{pass/fail}}
Final draft: drafts/<facet-name>-iter<N>.md or drafts/<facet-name>-final.md
Lines: {{line_count}}
Ready to bind.
```

**If phase == `bound`:**
```
✅ Facet installed at: {{bound_path}}
Bound at: {{bound_at}}
Companion manifest: {{bound_path}}.corpus-manifest.json
Index updated: {{index_file or "(none configured)"}}

Pipeline complete for this run.

To rebuild this facet (new version): /psychomanteum-init {{facet-name}} in this dir, or new dir.
To start a fresh facet: cd to a new working directory.
```

### Step 5: Warnings (if any)

If state shows incomplete things:
- Stale `_psychomanteum-work/` left over from a previous run that didn't complete: warn
- Drafts that didn't make it to bind: warn
- Mismatch between state phase and actual file presence: warn

## What to Return

The formatted status block (above). No agents, no state changes, no side effects.