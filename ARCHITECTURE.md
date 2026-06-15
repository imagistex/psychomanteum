# Architecture

*Developer-facing internals for the `psychomanteum` plugin. For the user-facing intro, see [`README.md`](./README.md).*

---

## Pipeline Topology

```
        ┌─ gatherer-encyclopedic ─┐
        ├─ gatherer-lexicon ──────┤
init ──▶├─ gatherer-canon ────────┤──▶ gleaner ──▶ [gather-gate] ──▶ essence-reader ──▶ distiller ──▶ [distill-gate]
        └─ gatherer-voices ───────┘     (sequential consolidation)        (per source)        (per section)
                                                                                                       │
                                                                                                       ▼
                                                                                                    cipher
                                                                                                       │
                                                                                                       ▼
                                                                                ┌──────────────── attune-loop ◀──┐
                                                                                │                                │
                                                                                ▼                                │
                                                          ┌─ verifier-density ───┐                              │
                                                          ├─ verifier-resonance ─┤── reports ──▶ attuner ───────┘
                                                          └─ verifier-strangeness┘   (revises draft, increments iter)
                                                                                                       │
                                                                                          (pass or max_iter)
                                                                                                       │
                                                                                                       ▼
                                                                                                    [final-gate] ──▶ bind
```

**Parallel where independent (gatherers, verifiers). Sequential where dependent (consolidation, distillation, attunement).**

## Components

### Commands (orchestrators)

All commands live in `commands/*.md`. They are slash-invocable, read configuration from `.psychomanteum-state.json` + `.psychomanteum-config.md`, and spawn agents via the `Task` tool. Commands themselves do not call WebFetch / WebSearch directly (agents do).

| Command | Phase | Spawns |
|---|---|---|
| `psychomanteum-init` | Setup | None (interactive) |
| `psychomanteum-gather` | Discovery | gatherer-* (parallel), gleaner (sequential) |
| `psychomanteum-read` | Ingestion | essence-reader (per source) |
| `psychomanteum-distill` | Compression | distiller (per section) |
| `psychomanteum-inscribe` | Voice | cipher |
| `psychomanteum-attune` | Refinement | verifier-* (parallel) + attuner (loop) |
| `psychomanteum-bind` | Install | None (file operations) |
| `psychomanteum-status` | Diagnostic | None (read state) |

### Agents (workers)

All agents live in `agents/*.md`. They follow the canonical template (frontmatter + `Read Shared Protocol` → `Model Configuration` → `Tools Available` → `How You Receive Parameters` → `Output Contract`). All agents read `prompts/agent-preamble.md` first.

**Gatherers** (parallel, web-facing):
- `gatherer-encyclopedic`—Wikipedia + general encyclopedic references
- `gatherer-lexicon`—community-of-practice jargon glossaries; lexical territory mapping
- `gatherer-canon`—canonical articles, posts, PDFs (WebSearch + WebFetch)
- `gatherer-voices`—primary voices: quotes, interviews, manifestos

**Consolidators** (sequential):
- `gleaner`—merges streams, dedups, fills gaps. Named for the gleaner (la glaneuse): the figure who walks the field after the harvest, gathering what was left.

**Processors** (sequential, corpus-aware):
- `essence-reader`—reads each approved source; extracts key passages with provenance tags
- `distiller`—compresses passages into dense distilled material; anchored by `prompts/esoteric-compression.md`
- `cipher`—assembles distilled material into the facet file *in the corpus's own voice and form*; anchored by `prompts/corpus-mirroring.md`

**Verifiers** (parallel, draft-facing):
- `verifier-density`—signal-per-token; flags filler, hedges, padding
- `verifier-resonance`—measures latent-space alignment with the source corpus (LLM probe + embedding similarity)
- `verifier-strangeness`—anti-corporate-flatness; checklist from `prompts/against-flatness.md`

**Revisers** (loop):
- `attuner`—reads verifier reports + current draft; produces revised draft; iterates until pass or max_iter

### Prompts (shared philosophy)

All prompts live in `prompts/*.md`. Agents reference them via `${CLAUDE_PLUGIN_ROOT}/prompts/<name>.md`.

| Prompt | Purpose |
|---|---|
| `agent-preamble.md` | Shared protocol: parameter receipt, return format, oversized-payload fallback, untrusted-content security, URL discipline, graceful degradation |
| `facet-schema.md` | The facet contract + the functions its body must serve (function, not form) |
| `esoteric-compression.md` | The philosophy of compression: dense-per-token, jargon-as-marker, initiate-accessible, no surface summary |
| `corpus-mirroring.md` | The cipher's anchor: voice extracted from + amplified by source corpus, not imposed by plugin |
| `against-flatness.md` | The checklist of corporate exsanguination patterns: filler phrases, dead hedges, distribution-speak, deflated metaphors |
| `toward-strangeness.md` | The positive companion to against-flatness: the live moves a draft should reach for (the lift), not just the dead ones to avoid (the floor) |
| `attune-loop.md` | The iterative refinement protocol: how the attuner reads reports, what counts as convergence, when to halt |
| `retrieval-discipline.md` | The source ladder + authenticity gate for the gatherers: get real primary text in; a failed fetch never falls through to invented text |
| `eval-methodology.md` | The epistemics of the eval: what to measure, what to refuse, and the traps that make a naïve eval reward the flatness a facet exists to defeat |

### Templates (artifact shapes)

All templates live in `templates/*`. They are filled by agents and consumed by other agents or by humans.

| Template | Consumed by | Filled by |
|---|---|---|
| `facet-skeleton.md` | cipher | the contract frame; the body is free |
| `corpus-manifest.json` | essence-reader, distiller, cipher | gather (sources), read (passages), distill (mappings) |
| `gather-gate.md` | human | gather command after gleaner |
| `distill-gate.md` | human | distill command after distiller |
| `attune-report.json` | attuner | verifier-* (one entry each per iteration) |

### Hooks (validation)

`hooks/validate-facet-schema.py` is a PreToolUse hook on `Write|Edit`. It runs whenever an agent writes a facet file (matched by path pattern) and enforces the facet contract (frontmatter, schema marker, closing epigraph, gross length)—not a fixed structure. Fails-closed: blocks the write if the contract is violated.

### Skill (routing)

`skills/psychomanteum/SKILL.md` declares the positive and negative triggers for the plugin—when the user says "build me a facet for X" or "I want a Fisher-mode for my AI", the skill activates and surfaces the `/psychomanteum-init` workflow.

## State Files

The plugin operates on **per-project state** in the working directory:

- `.psychomanteum-config.md`—human-readable config: facet name, lineage description, seed corpus, install destination, schema version target
- `.psychomanteum-state.json`—machine-readable state: current phase, iteration counter, last action, error log
- `_psychomanteum-work/`—ephemeral working directory; cleaned at phase boundaries
- `corpus/`—extracted passages with provenance (kept after pipeline ends)
- `distilled/`—section drafts with source mappings
- `drafts/`—facet drafts at each major version
- `attune/iter-N/`—per-iteration verifier reports + draft snapshot

## Versioning

Each generated facet declares its schema version in YAML frontmatter:

```yaml
---
name: capital-realist
version: 0.1.0
schema: 0.2.0
generated: 2026-06-10
corpus_manifest: ./capital-realist.corpus-manifest.json
---
```

- **`version`**—the facet's own SemVer; bumps on content change
- **`schema`**—the contract this facet conforms to; bumps when the contract changes materially. The body is free-form (function, not form)—the contract governs the frontmatter + closing epigraph, not a fixed set of sections.

The plugin reads `schema` on update. The contract evolves via git—the hook validates the marker's *shape*, not a fixed set. If a facet's `schema` marker lags the current contract, surface the drift so the facet can be re-bound under the current contract.

## Extending the Plugin

To add a new gatherer:
1. Write `agents/gatherer-<source-type>.md` following the canonical template
2. Add it to `plugin.json`'s `agents` array
3. Update `commands/psychomanteum-gather.md` to spawn it

To add a new verifier:
1. Write `agents/verifier-<dimension>.md` following the canonical template; its output contract must conform to `attune-report.json`
2. Add it to `plugin.json`'s `agents` array
3. Update `commands/psychomanteum-attune.md` to spawn it in parallel with the existing verifiers

To change the facet contract:
1. Update `prompts/facet-schema.md` in place with the new contract (no version-suffixed files—the repo shifts the contract up via git)
2. Update `templates/facet-skeleton.md` in place to match
3. Bump the `schema` marker (the SemVer-shaped string facets and the hook check) and the plugin's package `version` in `plugin.json`
4. Re-bind affected facets under the new contract; surface any that lag the current `schema` marker

## Generic Substrates Only

This plugin uses only generic Claude Code tools: `WebFetch`, `WebSearch`, `Read`, `Write`, `Bash`, `Glob`. It runs on any Claude Code instance.

Cross-harness adaptation (Codex CLI, Gemini CLI, Aider, etc.) is a future port path; each will need a thin tool-binding shim. The agent and prompt files should be portable as-is once the tool-binding layer is adapted.