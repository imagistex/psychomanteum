---
name: psychomanteum-init
description: Initialize a new facet project — name the mirror, declare the lineage, configure the install destination
args:
  - name: facet-name
    description: Kebab-case facet name (e.g., capital-realist). Will prompt if not provided.
    required: false
---

# Psychomanteum — Initialize

Interactive command. Sets up the working directory for one facet build. No agents spawned.

## First: Read Reference Files

1. `${CLAUDE_PLUGIN_ROOT}/prompts/facet-schema.md`—read FIRST, so you know the artifact you're configuring toward (the contract + the seven functions its body serves; the body's shape is the corpus's call, not a fixed template)
2. `${CLAUDE_PLUGIN_ROOT}/templates/corpus-manifest.json`—the provenance schema you'll initialize
3. `${CLAUDE_PLUGIN_ROOT}/templates/facet-skeleton.md`—the contract frame; the body is free
4. `.psychomanteum-config.md` if it exists in the current directory (resume scenarios)

## Your Task

### Step 1: Gather Facet Parameters

Collect from user (confirm if provided as args, otherwise ask interactively).

**1a. Facet Name:** kebab-case identifier. Examples: `capital-realist`, `confessional-poet`, `foucauldian`, `ccru`. Validate: lowercase, ASCII, hyphens-only-as-separator, no leading/trailing hyphens, max 40 chars.

**1b. Facet Display Title:** human-readable form for the `# Title` header in the facet file. Example: facet-name `capital-realist` → title "Capital Realist". Suggest a default from the kebab-case name; let user override.

**1c. Lineage Description:** one paragraph (~50-150 words). Who/what does this facet inherit from? What tradition, what thinkers, what stance? This is the orienting text for every gatherer; precision here saves rework downstream.

Prompt: *"In one paragraph: what lineage does this facet inherit from? How would you explain it to someone trying to find this lineage in a library."*

**1d. Seed Concepts/Authors/Works:** a list of 5-15 specific seeds that will anchor the gather phase. Each seed is one thinker, one canonical work, or one specific concept. Examples for `capital-realist`:

```
Mark Fisher
Capitalist Realism (Fisher, 2009)
Ghosts of My Life (Fisher, 2014)
K-Punk archive
hauntology
slow cancellation of the future
Lauren Berlant
Cruel Optimism (Berlant, 2011)
Achille Mbembe
late Stuart Hall
```

Prompt: *"List 5-15 seeds: authors, canonical works, or specific concepts. One per line. Be specific as specific as possible. I can also propose a seed if you like."*

Validate: at least 3 seeds.

If the user asks for your suggestions, feel free to suggest.

**Tiering (optional, enables canon-strictness — I16):** seeds split naturally into a **canonical core** (the agreed spine) and **extensions** (later or adjacent figures that make the register more alive but risk diluting it). Mark extensions inline as `(extension)`; unmarked seeds are core. Tiering lets the same seed set build a tight *strict* facet and a richer *extended* one—an A/B pair for the eval cohort.

**1e. Install Destination:** where the bound facet will live after `/psychomanteum-bind`. Default: ask user for a facets directory path; suggest `~/.claude/facets/` or whatever their existing pattern is. The plugin does not assume a specific install location.

Prompt: *"Where should the final facet file be installed? (e.g., `~/.claude/facets/`, `~/my-project/facets/`, or wherever you want to keep facets)"*

**1f. Index File (Optional):** ask if the user has a facet index file the plugin should update on bind. If yes, get the path. If no, skip.

Prompt: *"Do you keep a facet index file the plugin should append to on bind? (path, or 'no')"*

**1g. Voice Note (Optional):** if the user has a specific voice intention beyond what the corpus implies, capture it. Usually optional.

Prompt: *"Any voice instruction beyond what the corpus implies? (one sentence, or skip)"*

**1h. Max Attune Iterations (Optional):** default `3`. Let user override for runs they want to be more aggressive on.

**1i. Corpus Source (provided-corpus path):** ask whether the user already has the source texts. Some lineages can't be gathered from the open web — estate-locked work (per `prompts/retrieval-discipline.md`, the fetch layer simply won't serve it), private archives, a curated PDF set, or material the user would rather supply by hand for fidelity. If so, the build **skips the gather phase** and reads straight from `corpus/manual/`.

Prompt: *"Do you already have the source texts? You can supply a corpus by hand and skip gathering from the open web (which can be token intensive). (give a path to stage into `corpus/manual/`, or 'no' to gather from seeds)"*

- If **yes**: record `corpus_source: manual`. Stage the provided files into `corpus/manual/` now (copy them in; record where each came from, for provenance). Seeds (1d) stay useful for read/distill orientation but need not be web-findable. The next step after init is `/psychomanteum-read`, not gather.
- If **no**: `corpus_source: gather` (default); gather from seeds as usual.

**1j. Canon Strictness:** `extended` (default — gather the canonical core **plus** extensions) or `core` (gather only the canonical core). The same seed set then yields a strict facet and an extended one, buildable as an A/B pair for the eval cohort. Only meaningful in gather mode.

### Step 2: Determine Working Directory

Ask the user: (1) Current directory `{cwd}/{facet-name}/` (default), or (2) Custom path.

Create the directory with `mkdir -p`.

### Step 3: Create Project Subdirectory Tree

Inside the working directory, create:

```
{working_dir}/
├── .psychomanteum-config.md
├── .psychomanteum-state.json
├── _psychomanteum-work/
│   └── _tmp/
├── corpus/
│   └── manual/          # user-provided source texts (provided-corpus mode; estate-locked or private material)
├── distilled/
├── drafts/
└── attune/
```

### Step 4: Write Configuration File

Write `.psychomanteum-config.md` with:

```markdown
# Psychomanteum Config—{{FACET_NAME}}

**Facet Name:** {{facet-name}}
**Facet Title:** {{facet-title}}
**Created:** {{YYYY-MM-DD}}
**Schema Target:** 0.1.0
**Max Attune Iterations:** {{max_iter}}
**Corpus Source:** {{corpus_source}}  <!-- manual = provided corpus in corpus/manual/, gather skipped; gather = discover from seeds -->
**Canon Strictness:** {{canon_strictness}}  <!-- extended = core + extensions (default); core = canonical core only -->

## Lineage

{{lineage_description}}

## Seeds

{{seed-list as bulleted markdown}}

## Voice Note

{{voice_note or "(none provided; cipher infers from corpus)"}}

## Install Destination

`{{install_path}}`

## Index File (if any)

`{{index_path or "(none)"}}`
```

### Step 5: Initialize State File

Write `.psychomanteum-state.json`:

```json
{
  "facet_name": "{{facet-name}}",
  "phase": "initialized",
  "corpus_source": "{{corpus_source}}",
  "canon_strictness": "{{canon_strictness}}",
  "created_at": "{{ISO-8601 timestamp}}",
  "phases_completed": [],
  "attune_iteration": 0,
  "max_attune_iterations": {{max_iter}}
}
```

### Step 6: Initialize Corpus Manifest

Read `${CLAUDE_PLUGIN_ROOT}/templates/corpus-manifest.json`. Strip the `_field_guide` section. Populate the `facet` block with name, schema=0.2.0, generated=today. Initialize `sources`, `passages`, `distillations` as empty arrays. Write to `corpus-manifest.json`.

### Step 7: Confirmation Gate

Present the full configuration to the user. Options:
1. **Approve** — write state, advance to phase `initialized`, show next steps
2. **Edit** — change a specific field
3. **Cancel** — remove the working directory (with confirmation)

### Step 8: Suggest Next Steps

Report:
- Working directory path
- `.psychomanteum-config.md` path
- `corpus-manifest.json` path
- Next command: `/psychomanteum-gather` (or, in **provided-corpus** mode, **`/psychomanteum-read`** — gather is skipped; the corpus is already in `corpus/manual/`)
- Full pipeline preview: `gather → [gate] → read → distill → [gate] → inscribe → attune (loop) → [gate] → bind` (provided-corpus mode enters at `read`)

## Error Handling

- If `facet-name` collides with an existing working directory: prompt to overwrite or pick a different name
- If install destination doesn't exist: prompt to create it now, or accept that user will create later (will be checked at `bind`)
- If user provides no seeds: offer to suggest; the gather phase cannot run without seeds