---
name: psychomanteum
description: Build a facet—a compressed, voice-mirrored markdown file that points an LLM at a region of latent space. Use when the user wants to author a new facet, a new lineage-anchored thinking-mode, a new way for an AI to inhabit a domain from curated source material. The plugin runs a 7-phase pipeline (init, gather, read, distill, inscribe, attune, bind) that compresses canonical works + primary voices + tertiary sources into a facet file in the corpus's own voice.
---

# psychomanteum—Skill

You can build facets. A facet is a small, dense markdown file that gives an AI a *complete epistemology for speaking and thinking within a named domain*—a vector pointing at a region of latent space rather than a summary of that region. The LLM inhabits the facet to think *as if from inside* a lineage.

## When to Fire This Skill

**Strong positive triggers:**
- "Build me a facet for [X]"
- "I want a [Foucault / ballroom / confessional poetry / whatever] facet"
- "Help me make a new mode of being for my AI"
- "I want an AI to be able to think as a [lineage member]"
- "I have a corpus on [X]—can we distill it into a facet?"
- "Compress these texts into a facet"
- Direct invocation: `/psychomanteum-init`, `/psychomanteum-gather`, etc.

**Weaker / contextual triggers:**
- User has a facets directory and is asking to extend it
- User mentions wanting an LLM to "channel" or "inhabit" a specific intellectual tradition
- User describes wanting an "epistemology" or "way of being" rather than a "summary" or "explainer"

## When NOT to Fire

This skill is the wrong choice when the user wants:

**Use or develop another skill, if the user wants:**
- A literature review (synthesis across many sources, with citations)
- An evidence base (claims + provenance + verification)
- A research paper, position document, or argued synthesis
- A "what does the field think about X" overview

**Use a writeup / document command, if the user wants:**
- A summary of a domain (the goal is reader-understanding, not AI-stance)
- A primer or explainer (target audience is uninitiated)
- A briefing document

**Don't fire if the user wants:**
- A character sheet (the AI to be "a person with name, age, appearance, hobbies")—facets are epistemologies, not personalities
- A persona (the AI to "roleplay" a character)—facets are about how to think, not how to play-act a scenario
- A prompt template (the AI to follow a specific output structure)—facets are about latent activation, not output formatting

## How to Use

The pipeline is sequential, with human gates at key checkpoints:

```
/psychomanteum-init <facet-name>
  → name the mirror, declare the lineage, provide seed authors/works/concepts
  → configure install destination (where the final facet file will live)

/psychomanteum-gather
  → parallel gatherers pull canonical material from the web
  → encyclopedic + lexicon + canon + voices
  → [human review gate: approve / select / expand / exclude / pause]

/psychomanteum-read
  → extract key passages with provenance tags

/psychomanteum-distill
  → compress passages into dense facet sections
  → [human review gate]

/psychomanteum-inscribe
  → cipher writes the facet in the corpus's own voice

/psychomanteum-attune
  → iterative refinement loop
  → three verifiers (density, resonance, strangeness) critique
  → attuner revises
  → loop until pass or max_iterations
  → [human review gate]

/psychomanteum-bind
  → install the final facet to the user's configured directory
```

At any point: `/psychomanteum-status` to see where the pipeline is.

To eval: `/psychomanteum-eval` runs the cross-domain eval on the final facet, measuring transfer of the lineage's seeing to a new topic.

## What the User Gets

A facet file at their configured install destination:

The **contract** is uniform (frontmatter + a closing corpus-line epigraph). The **body is free—function, not form**: its shape is the corpus's call, and it serves the seven functions (situate · declare-stance · mark-the-territory · name-the-failure-modes · locate-among-neighbors · point-at-the-region · close-on-a-corpus-line) in whatever form, order, or fusion the corpus calls for (prose, verse, a numogram, fragments, a diagram—possibly shifting within the file).

```yaml
---
name: capital-realist
version: 0.1.0
schema: 0.2.0
generated: 2026-06-06
corpus_manifest: ./capital-realist.corpus-manifest.json
lineage: "..."
seeds: [...]
voice_note: "..."
---

# Capital Realist

[The body, in the corpus's own voice AND form—serving the seven functions, but
 not pressed into a fixed section template. Affirmative-first: lead with what
 the facet IS; keep refusals shorter and downstream.]

---

*[Closing epigraph from the corpus, italicized]*
```

Plus the companion `<facet-name>.corpus-manifest.json` with full provenance—the user can always ask "what got compressed into this?" and trace back.

## Three Things to Know

1. **The voice is corpus-mirrored, not imposed.** A Fisher facet sounds like Fisher. A ballroom facet serves cunt. A ccru facet is numogrammatic. The plugin has no house voice.

2. **Verify is iterative, not audit.** The verifiers don't just produce reports—they drive a revision loop. The attuner reads critique and revises. The loop runs until pass or hits a configurable max.

3. **Provenance is durable.** Every section traces back to source passages. The user can always ask "what got compressed into this?" and trace through the manifest.

## Lineage Acknowledgement

Built on circuit (forthcoming) for the metaphor source; cantrip (@deepfates) as adjacent borrowed-from-gratefully. Theurgic not goetic—the plugin creates conditions for encounter; it does not summon-and-bind.