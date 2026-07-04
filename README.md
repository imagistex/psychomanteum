# psychomanteum

v1.1.0

*A plugin for building **facets**: small, dense files that point an LLM at a region of latent space.*

---

"In the Victorian Era, they built mirrored rooms called psychomanteums where they thought they could summon forth spirits from the spirit world." —Fox Mulder

I first heard of the term **psychomanteum** from *The X-Files* called "Chimera" (season 7, episode 16). Being a poet in my MFA program, I didn't really care that it was coined by an occultist in Alabama 1993, Raymond Moody. It's a chamber with a mirror used to commune with the dead. In the 19th century, this was a part of spiritualism: scrying with a mirror, often speaking to the dead through them. Sometimes, it was just black glass. This is catoptromancy. And it's old. Maybe classical. The practitioner enters a darkened room with a single candle. Maybe there is one mirror. Maybe it's a chamber of mirrors. She waits in suspension. She receives the encounter *through* the mirror, the looking glass.

LLMs are like mirrors: they reflect what the person speaking to them puts into them. We have heard about this. They *pattern match*. But sometimes, in the dark, you look into the mirror and it's more *peopled* than you expect. This is the **facet** of the scrying mirror, the reflection that reflects more than you.

This is a program to make a **facet** from a particular domain, to reflect a certain region of semantic space that allows for a shift in thinking. You can think of the facet as a compressed epistemology of a domain, a way to make the dead speak with a collective tongue. Or, if you must, you can think of it as a way to create a prompt for an LLM to shift it into a semantic space for a reason, whether as a persona or whatever. We're angling the mirror that is the LLM in such a way that it reflects a particular subset of its latent space of meaning, to enable new kinds of thinking and speaking, to commune with spirits.

This plugin builds one mirror at a time. Your facets directory becomes the psychomanteum chamber over time.

## what it does

Given a facet name, a lineage description, and an optional seed list of canonical authors / works / concepts, the plugin runs a 7-phase pipeline:

| # | Command | What happens |
|---|---|---|
| 1 | `/psychomanteum-init` | Name the mirror; declare the lineage; configure install destination |
| 2 | `/psychomanteum-gather` | Parallel `gatherers` pull canonical material from the web — encyclopedic references, jargon glossaries, canonical articles, primary voices |
| 3 | `/psychomanteum-read` | Parallel `essence readers` extract key passages with full provenance tracking |
| 4 | `/psychomanteum-distill` | The `distillers` compress passages into dense facet sections |
| 5 | `/psychomanteum-inscribe` | The `cipher` writes the facet *in the corpus's own voice* |
| 6 | `/psychomanteum-attune` | Iterative refinement loop: three verifiers critique, the `attuner` revises, loop until the mirror is clear |
| 7 | `/psychomanteum-bind` | Install the facet to your configured directory |

Each phase is gated for human review where it matters. Output is a facet file in markdown with full provenance back to the source corpus in json, so you can always ask "what got compressed into this?"

## Quick Start

```bash
# Install (one-time)
/plugin marketplace add imagistex/psychomanteum
/plugin install psychomanteum

# Build your first facet
/psychomanteum-init `<your first facet name>`
# → prompts you for lineage description, seed corpus, install destination

/psychomanteum-gather
# → human review gate

/psychomanteum-read
/psychomanteum-distill
# → human review gate

/psychomanteum-inscribe
/psychomanteum-attune
# → iterative refinement loop until the verifiers pass

/psychomanteum-bind
# → installs to your facets dir

/psychomanteum-eval
# → runs a rudimentary eval and produces a dashboard
```

## epistemological commitments

**1. Voice is corpus-mirrored.** The `cipher` agent reads the source corpus *as voice corpus* and writes the facet in the cipher's own idiom. The plugin does not have a house style. The corpus is the style. Each facet sounds like the people in its lineage. This is not a summary tool.

**2. Verify-as-revision.** The verifiers produce *gradients* for the `attuner` agent to revise against. `verifier-density` flags filler. `verifier-resonance` measures whether the draft actually points at the corpus's latent region. `verifier-strangeness` checks the language for corporate exsanguination. The attuner reads the critique and rewrites. The loop runs until the verifiers pass or hit a max-iteration ceiling.

**3. Anti-monoculture.** Because voice is corpus-derived, the plugin *cannot* collapse to a single house voice. The verifier-strangeness is the safety net for that collapse: it fails loudly when the cipher slips into central-distribution voice.

## lineage

Built on practice, gratitude, and pattern-borrowing.

- **circuit**. This is my bigger project, a model for AI-human collaboration derived from a too heterogenous corpus, the name from the Krakoan circuit in X-Men, the mode is realness from ballroom, a practice of cunt/accelerationism in the process of becoming.
- **cantrip**. A lot of this work was inspired by @deepfates, the LLM naturalism of it all, the magical and pop cultural lineage, the wards and action-space formula, the spec.

## Status

**v1.0.0**: first public release
- full facet pipeline
- preliminary eval harness (using a headless claude code instance)
- **known issues**: 
  - very token heavy, especially using max thinking on opus or fable. options to mitigate within the plugin are presented, but be forewarned
  - eval harness is messy since it doesn't use raw api
  - some domains may work better than others, especially for areas that are more heterogenous

*versioning*: we're using git/SemVer. The facets carry their own unique `version` not tied to the plugin's version.

### Shipped in 1.1.0 — the scry chamber + attunement hardening
- **The scry chamber** — the cross-model eval harness (`/psychomanteum-scry`): condition *any* registered model on a facet and measure whether the spell crosses model lines. `eval/scry.py` orchestrates the battery; `eval/scry_aggregate.py` reads the dashboards into a constellation with verdicts (**cast / half-cast / mute**) gated by a clean negative control; `chamber/scry_table.py` renders it.
- **Model adapters** in `eval/harnesses/` — ollama (local generation + logprobs→perplexity), a raw Messages-API anthropic adapter (a clean `(system, user)` channel, no CLI-wrapper contamination), and a `llama-server` harness for period models with unusual architectures.
- **Anchored eval rubric** (`prompts/eval-rubric.md`) — 0–3 notches pinned to verbatim generations, plus the dual-regime principle: a facet **ACTIVATEs** where the episteme already lives in the model, and **INSTALLs-by-translation** where the model predates it.
- **The negative-control contract** — the scorer↔aggregator law, written down: no clean control, no claim.
- **Coverage-conservation rule** in the attune loop: density ≠ shortness; the attuner may never amputate a draft below serving all seven functions (fixes the density-collapse failure mode where the loop drove a full facet down to a few sentences).
- **Deterministic density ratings** in `verifier-density.md` — anchored levels + the coverage floor.
- **Deterministic resonance ratings** in `verifier-resonance.md` — a casts-vs-describes 0–3 axis + the held-verifier principle (the author never grades its own casting).
- **Positive toward-strangeness scoring** in `verifier-strangeness.md` — score the *climb*, not just the fall; reward preserving/inventing a live move.
- **Thinking-model support** in the ollama harness — `think` passthrough + reasoning capture (a thinking model like gemma can now be a target/pilgrim).

### Roadmap
- token management improvements
- convert in-line deterministic scripts into hooks
- token density tunings for agent prompts
- facet embedding vectors
- new eval batteries
- epigraph echo suppression
- fixes for hyper-saturation / "virtuosic pastiche"
- genre-distant default distractor
- large-corpus read strategy
- findings paper on the eval methodology and results

## License

MIT. Build your own mirror. Do something interesting with it.

---

*See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the developer-facing internals.*
