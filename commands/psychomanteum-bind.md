---
name: psychomanteum-bind
description: Install the final facet—copy to user-configured destination; optionally update index
---

# Psychomanteum—Bind

Final installation step. Copies the approved draft to the user's configured facets directory; optionally updates a user-configured index file. Pure file operation—no agents spawned.

## First: Read Reference Files

1. `.psychomanteum-config.md`—install destination and index file (if any)
2. `.psychomanteum-state.json`—must be phase `attuned`
3. The final draft

## Your Task

### Step 1: Validate State

Must be `phase: "attuned"`. Otherwise error.

Read the final draft path from state (typically `drafts/<facet-name>-iter<N>.md` or `drafts/<facet-name>-final.md` if user rolled back).

### Step 2: Validate Destination

Read `install_destination` from `.psychomanteum-config.md`.

- Check the destination directory exists. If not, prompt: create it now, or abort and have user create.
- Check whether `<install_destination>/<facet-name>.md` already exists. If yes:
  - Compare existing file's `version` and `schema` to the new one
  - Options: overwrite, write as `<facet-name>-v<NEW>.md` (versioned), skip bind, abort

### Step 3: Show the Final Draft

Display the final draft to the user. Last-chance read.

Confirm: "Bind this facet to `<install_destination>/<facet-name>.md`?"

### Step 4: Copy Draft to Destination

`cp drafts/<facet-name>-iter<N>.md <install_destination>/<facet-name>.md`

The validate-facet-schema.py PreToolUse hook will fire on the Write. If validation fails, surface the contract violation—the user should be able to fix without re-running attune (e.g., fix YAML frontmatter typo, missing field).

### Step 5: Update Index (if configured)

If `index_file` is set in config:

- Read the existing index file
- Look for an existing entry for this facet name (update vs append)
- Append a new line or update existing line. Suggested format:

```markdown
| {{facet-title}} | `{{facet-name}}.md` | {{lineage_short}} | {{version}} |
```

The plugin does NOT enforce a specific index format—if the user has an existing index with a different format, ask them to confirm the line shape before writing.

### Step 6: Copy Corpus Manifest as Companion (raw corpus retained — provenance layer 3)

Copy `corpus-manifest.json` to `<install_destination>/<facet-name>.corpus-manifest.json`. This preserves provenance alongside the facet—the user can always ask "what got compressed into this?" and trace back. This companion is **layer 3 of the three-layer provenance** (the raw corpus retained): the full-content manifest carries the source text + the globally-id'd passages + the `facet_mapping`, so every line of the facet is traceable to source even when the body's own citation style is loose or absent (which is correct—citational style is corpus-mirrored, layer 1). Confirm the copied manifest is the **full-content** one (sources retain their `content`), not a stripped index.

### Step 6b: Update the Chamber Index (`FACET_INDEX.md`)

Maintain the **chamber index** at the install destination—`<install_destination>/FACET_INDEX.md`—so the facets directory becomes the chamber over time. This is the **hermetic metadata channel**: it lets facets (and the eval's distractor selection, and `/psychomanteum-attune-chamber`) know a sibling *exists* and what *region* it occupies, **without** reading its body.

- Read this facet's `slanted_mirrors` block from `corpus-manifest.json` (self-location axes + region) and its `lineage` from frontmatter.
- Create the index if absent; otherwise add or update this facet's row. Format (one row per facet — **names and roles only, never bodies**):
  ```
  | Facet | Lineage | Role (one line) | Axes · Region |
  |---|---|---|---|
  | `<name>` | <lineage short> | <one-line role, in this facet's own terms> | <axes · region> |
  ```
- Derive the row **only from this facet's own metadata** (frontmatter + manifest `slanted_mirrors`), never by reading sibling facet files.
- After updating, you may suggest `/psychomanteum-attune-chamber` to refresh siblings' Slanted-Mirrors maps against the now-fuller chamber.

### Step 7: Update State

- Update `.psychomanteum-state.json`: phase → `bound`, `bound_at: <timestamp>`, `bound_to_path: <full_install_path>`
- Add to `phases_completed`

### Step 8: Report

```
✅ Bound facet `{{facet-name}}` to:
  {{install_destination}}/{{facet-name}}.md
  {{install_destination}}/{{facet-name}}.corpus-manifest.json

Index updated: {{index_file or "(none)"}}

Provenance: {{n_sources}} sources, {{n_passages}} passages, {{n_distillations}} distillations.
Schema: {{schema}}
Final iteration: {{final_iter}}
```

Suggest:
- Test the facet by invoking it
- The working directory `{{cwd}}` can be archived or deleted; the facet is now self-contained at the install destination
- For version updates: re-run `/psychomanteum-init <facet-name>` in the same working dir to bump version

## Error Handling

- Destination missing/uncreatable: surface and let user fix
- File-name collision without user resolution: don't auto-overwrite; require explicit confirmation
- Schema validation hook fails: surface specific violation; do not bind a malformed facet
- Index file format ambiguous: don't append blind; ask user