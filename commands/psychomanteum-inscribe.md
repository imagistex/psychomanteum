---
name: psychomanteum-inscribe
description: Voice phase—cipher assembles distilled sections into a facet draft in the corpus's own voice and form
---

# Psychomanteum—Inscribe

Orchestrates the voice phase. Spawns the `cipher` agent (single, sequential) to assemble distilled sections into a facet draft, written in the corpus's own voice and form (not the plugin's). No human gate here—the next gate is at attune.

## First: Read Reference Files

1. `.psychomanteum-config.md`
2. `.psychomanteum-state.json`—must be phase `distilled`
3. `distilled/sections.json`—the distiller's output
4. `corpus-manifest.json`—for passage provenance
5. `corpus/passages.json`—the cipher will re-read source passages for voice and form

## Your Task

### Step 1: Validate State

Must be `phase: "distilled"`. Error otherwise.

### Step 2: Prepare Working Directory

```bash
mkdir -p drafts
mkdir -p _psychomanteum-work/inscribe
```

### Step 3: Spawn the Cipher

Single spawn. The cipher agent receives:

- Facet name (from config)
- Facet title (from config)
- Lineage description (from config)
- Distilled sections path: `distilled/sections.json`
- Corpus manifest path: `corpus-manifest.json`
- Passages path: `corpus/passages.json`
- Voice note (from config, if provided)
- Output path: `drafts/<facet-name>-iter0.md`

The cipher is opus-default and takes longer than other agents. This is intentional. Voice-and-form work is the most consequential single act.

### Step 4: Validate Cipher Output

After the cipher completes:

1. Confirm `drafts/<facet-name>-iter0.md` exists
2. Confirm `drafts/<facet-name>-iter0.md.cipher-notes.json` exists (the sidecar)
3. Confirm the **contract** holds—frontmatter present and a closing epigraph (the `validate-facet-schema.py` hook enforces this on write). The body's form is the corpus's call (function, not form); do NOT check for a fixed set of sections. Whether the body serves the seven functions *well* is the verifiers' judgment at attune, not a structural check here.
4. Validate the frontmatter includes the required fields (name, version, schema, generated, corpus_manifest). Do NOT hard-code a version value—the hook validates the schema marker's SemVer shape.
5. Length aim is ~150-300 lines (guidance); the hook hard-fails only gross outliers (≈40-800).

If any validation fails: report to user, present options to re-spawn cipher with adjusted parameters or accept partial output.

### Step 5: Update Corpus Manifest

Append to `corpus-manifest.json` `iteration_history`:

```json
{
  "iteration": 0,
  "phase": "inscribe",
  "draft_path": "drafts/<facet-name>-iter0.md",
  "cipher_notes_path": "drafts/<facet-name>-iter0.md.cipher-notes.json",
  "notes": "Initial cipher inscription"
}
```

Also populate the `facet_mapping` block from the cipher's notes (it is function-keyed; see the manifest template).

### Step 6: Display Voice Confidence

Show the user:
- Cipher's `voice_confidence` rating
- Cipher's `voice_form_memo` (the private memo the cipher wrote about what voice and form it heard) and `form_chosen`
- Functions or passages (if any) where voice or form was uncertain

If `voice_confidence: "low"`, present options:
- Proceed to attune anyway (the loop may improve voice through revision)
- Re-spawn cipher with additional voice guidance
- Return to gather/read to expand voice-bearing material (especially canon and voices gatherers)

If `voice_confidence: "high"` or `"medium"`, proceed automatically to suggest `/psychomanteum-attune`.

### Step 7: Update State + Cleanup

- Update `.psychomanteum-state.json`: phase → `inscribed`
- Wipe `_psychomanteum-work/inscribe/` (cipher doesn't write much here, mostly empty)
- Suggest: `/psychomanteum-attune`

## Error Handling

- Cipher crashes or fails: present partial output (if any) + spawn logs; let user retry
- The `validate-facet-schema.py` hook blocks the write: surface the contract violation; the cipher should not have written a contract-violating draft. Treat as cipher bug; re-spawn with an explicit contract reminder.
- Voice confidence `low` with no actionable path: surface to user honestly; they may want to abort and rebuild corpus