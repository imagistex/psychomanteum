---
name: psychomanteum-gather
description: Discovery phase—parallel gatherers fetch canonical material; gleaner consolidates; human review gate
---

# Psychomanteum—Gather

Orchestrates the discovery phase. Spawns parallel gatherers (encyclopedic, lexicon, canon, voices) to fetch canonical material from the web, then runs the gleaner sequentially to consolidate, then writes a human review gate.

## First: Read Reference Files

1. `.psychomanteum-config.md` (current working directory)—config + seeds
2. `.psychomanteum-state.json`—current phase (must be `initialized` or `discovered`)
3. `${CLAUDE_PLUGIN_ROOT}/templates/gather-gate.md`—gate template you'll fill

## Your Task

### Step 1: Validate State

Read `.psychomanteum-state.json`. Must be `phase: "initialized"` or `phase: "discovered"` (the latter for re-running gather to expand). If any other phase, error: `"Cannot run gather; current phase is {phase}. Use psychomanteum-status to see state."`

### Step 2: Prepare Working Directory

```bash
mkdir -p _psychomanteum-work/gather
mkdir -p _psychomanteum-work/_tmp
```

### Step 3: Plan Parallel Gatherer Spawns

Read seeds from `.psychomanteum-config.md`. **Honor `canon_strictness`:** in `core` mode, plan spawns only for core-tier seeds (skip those marked `(extension)`); in `extended` mode (default), include the extension-tier seeds too. For each in-scope seed, plan agent spawns:

**`gatherer-encyclopedic`**: one per major concept seed (typically every named concept, not every author). For an author-seed like "Mark Fisher", spawn encyclopedic for the author. For a concept-seed like "hauntology", spawn for the concept.

**`gatherer-lexicon`**: ONE per pipeline run, covering the whole facet (not per-seed). It builds the lineage glossary holistically.

**`gatherer-canon`**: one per author-seed AND one per canonical-work-seed. (For "Mark Fisher" + "Capitalist Realism (Fisher, 2009)" → 2 canon spawns.)

**`gatherer-voices`**: one per author-seed (works fetched per-author make sense; one voice gather per anchor thinker).

Build the full spawn plan. Typical sizes:
- 5 author seeds + 3 concept seeds + 4 canonical works = 5 encyclopedic + 4 encyclopedic-concept + 1 lexicon + 9 canon + 5 voices = ~24 spawns
- Smaller facets (3 seeds): ~8 spawns
- Larger (15 seeds): ~40 spawns

### Step 4: Execute Parallel Spawns in Batches of 5-6

The Task tool supports parallel spawning. Spawn in batches of 5-6 to avoid overwhelming the runtime.

For each agent, the prompt includes:
- Facet name + lineage description (from config)
- The specific seed/anchor this agent is fetching for
- Output path: `_psychomanteum-work/gather/<agent-name>-<seed-slug>.json`
- Whatever else the agent definition requires (read the agent file for exact contract)

Wait for each batch to complete before launching the next. Track completed/failed counts.

### Step 5: Validate Gatherer Outputs

For each output file:
- Confirm exists at expected path
- Confirm parses as JSON
- Confirm has `status` field

If any are missing/broken, log to a `_psychomanteum-work/gather-errors.log` and continue (don't block the whole run on one failed gatherer).

**After an agent error, check the output file on disk before treating the gatherer as failed.** Agents frequently finish writing before a socket drops (see the socket-drop clause in `agent-preamble.md`) — a complete, valid file on disk means the work succeeded even if the agent's return never arrived. Only count a gatherer as failed if its file is absent or invalid.

### Step 6: Run Gleaner Sequentially

Spawn `gleaner` agent with:
- Facet name
- Gather working directory: `_psychomanteum-work/gather/`
- Config path: `.psychomanteum-config.md`
- Output path: `_psychomanteum-work/gleaned-sources.json`

Wait for completion.

### Step 7: Assert Content Integrity, Then Generate the Human Review Gate

**First, assert content integrity from the gleaned output** (the gleaner self-asserts; verify here too — this is the I4 guard that makes a dropped layer *visible* to the human):

```bash
G=_psychomanteum-work/gleaned-sources.json
jq '{total: (.sources|length),
     content_bearing: ([.sources[]|select((.content//"")|length>0)]|length),
     voice: ([.sources[]|select(.type=="voice")]|length),
     truncated: ([.sources[]|select(.reported_bytes and .written_chars and (.truncation_check!="refetched") and (.written_chars < (0.6*.reported_bytes)))]|length)}' "$G"
```

If `content_bearing < total`, or `voice == 0` when voice sources were gathered, the consolidation lost material. Do **NOT** proceed to the gate. Rebuild the source set directly from the gather files — *they* are the source of truth, not the gleaner output—using the deterministic merge from `agents/gleaner.md` Step 2 over `_psychomanteum-work/gather/*.json`, then re-assert.

`truncated > 0` does **not** block the gate—it is a *human-decision* flag. Surface every flagged source prominently at the gate so the user can re-gather it via the raw-download path; never let a truncated canon be approved silently. Verify against the bytes, not the gleaner's narration.

**Then** read `${CLAUDE_PLUGIN_ROOT}/templates/gather-gate.md` and fill in:
- Counts per gatherer
- Final post-dedup count
- **Content-integrity block** — content-bearing/total, per-type counts (especially `voice`), and the assertion verdict
- **Truncation block** — `TRUNCATION_VERDICT` (✓ if 0 flagged, ⚠ if any) and `N_TRUNCATION_FLAGS`; if any, list each flagged source (id · title · written/reported bytes · ratio) in the notes so the user sees exactly which canon arrived short
- Sources table (sorted by relevance or by type—your choice)
- Coverage assessment table
- Lineage tags surfaced
- Coverage notes from gleaner

Write to `_psychomanteum-work/gather-gate.md`.

### Step 8: Present Gate to User

Display the gate file to the user. **These options are a menu, not a form — accept a plain-language reply.** The user may answer in prose ("looks good, proceed", "drop the Mbembe ones and go", "pausing for the night, back tomorrow"); never require a numbered pick, and always honor *stepping away* as a valid, expected response—a build can rest overnight on silence. Map their words to one of:

1. **Approve**—accept candidate set; advance to phase `discovered`; cleanup `_psychomanteum-work/gather/`; commit sources to `corpus-manifest.json`
2. **Select**—accept a subset (user specifies by source ID)
3. **Exclude**—remove specific sources
4. **Expand**—return to gather with additional seeds (specify what to add)
5. **Discuss**—read more about specific sources, or ask for analysis
6. **Pause**—save state, exit (also the default when the user goes quiet — never strand a half-built corpus)

### Step 9: On Approve

- Move sources from gleaned output into `corpus-manifest.json` `sources[]` array
- Wipe `_psychomanteum-work/gather/`
- Update `.psychomanteum-state.json`: phase → `discovered`, add to `phases_completed`
- Suggest: `/psychomanteum-read`

### Step 10: On Other Options

- **Select/Exclude:** rebuild sources list per user selection; same write-and-advance as approve
- **Expand:** add new seeds to config; re-run gather from Step 3 (preserves existing gathered material)
- **Discuss:** allow back-and-forth; eventually return to gate
- **Pause:** preserve `_psychomanteum-work/`; exit; user resumes with `/psychomanteum-status` then `/psychomanteum-gather`

## Error Handling

- If `WebFetch` or `WebSearch` is unavailable to all gatherers: error early, suggest checking environment
- If gleaner fails: present raw gatherer outputs to user; let them decide whether to proceed
- If <50% of gatherers return success: warn user that coverage may be insufficient