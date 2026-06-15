# Facet Schema — The Contract, and the Functions

*The artifact specification for facets. May be read by the `cipher` (who writes them) and every agent that produces inputs to one. Internalize the target before producing anything that feeds it.*

**UNIFORM CONTRACT, FREE BODY.** A facet is two artifacts in one file—a *contract* (uniform, machine-checked) and a *body* (free, corpus-mirrored). The container does not impose a form. The corpus is the form, as the corpus is the voice.

---

## What a facet is

- A **vector pointing at a region of latent space**—loaded so an AI thinks *as if from inside* a domain.
- A **compressed epistemology**: what to be ready to think, how this lineage reasons, what it commits to and refuses.
- An **identity declaration in first person**, dense, initiate-accessible.

A facet is **not**:
- a **character sheet**—character cards encode *who you are* (personality, voice, backstory). A facet encodes *how to think*.
- a **knowledge dump / RAG**—retrieval injects *what is true*. A facet carries *method*, not facts.
- a **persona / role** ("you are a research scientist who…"), a **summary** of a domain, or a **style guide** (the voice is corpus-mirrored, not imposed).

The one-line discriminator: **epistemology, not personality; method, not facts.**

---

## Layer 1 — The Contract (uniform; the hook enforces this)

This is the floor every facet must clear, regardless of shape. `hooks/validate-facet-schema.py` blocks a write that violates it.

**Required frontmatter:**
```yaml
---
name: <kebab-case>            # canonical identifier
version: 0.1.0                # the facet's own SemVer (content changes bump it)
schema: 0.2.0                # the contract marker (SemVer shape; pre-1.0 the repo shifts up freely)
generated: YYYY-MM-DD
corpus_manifest: ./<name>.corpus-manifest.json   # the provenance sidecar
---
```
Optional: `lineage`, `seeds`, `voice_note`, `model_preference`.

**Provenance sidecar**—the `corpus_manifest` makes "what got compressed into this?" answerable. **Three-layer provenance:**
1. **In-facet citational style mirrors the corpus.** How the lineage cites is itself corpus-mirrored—a theory facet may cite by name and year, a poet facet may not cite at all, and where citational confusion is *generative* (ccru's hyperstition blurs fiction and real *on purpose*), the facet may blur it too. The cipher decides; the body's citation style is the corpus's call, like its voice and form.
2. **The sidecar makes every quote/claim findable** regardless of in-facet style. The manifest's `facet_mapping` (function → distillations → passages) and globally-id'd `passages[]` let anyone trace any line back to source—even when the body cites loosely or not at all.
3. **The raw corpus is retained**, sidecarred at bind (`bind` copies the full-content `corpus-manifest.json` as a companion). The source text itself stays recoverable, not just the citations.

The contract requires the `corpus_manifest` field + the sidecar; the three layers are how provenance survives a corpus-mirrored citation style that might otherwise be unfindable.

**Closing epigraph**—an italicized line from the source corpus, in the last lines of the file. This is the **one body invariant**: every mirror closes with a line from what it reflects.

Everything else about the body is free.

---

## Layer 2 — The Body: function, not form

**There is no required section list.** A facet's body is judged by what it *does*, not by which headers it has. The cipher chooses the body's shape to match the corpus—a numogram, verse, an unbroken prose movement, a register that refuses genealogy.

A facet body must serve these **functions**—in whatever form, order, naming, or fusion the corpus calls for:

1. **Situate**—placing inside the lineage's stance (first person, from within; never surveying from outside).
2. **Declare stance**—what this register is for, what it commits to. *Affirmative-first* (see below).
3. **Mark the territory**—the vocabulary-as-territory, the frameworks, the anchor thinkers; jargon used densely and unglossed (initiate-accessible, not initiate-required).
4. **Name the failure modes**—the specific things this register refuses; concrete, testable, in-voice.
5. **Locate among neighbors**—the *Slanted Mirrors* map (Dickinson: *"Tell all the truth but tell it slant — Success in Circuit lies"*; **Circuit** is psychomanteum's parent philosophy—slant truth, refracted in the chamber). Two moves, both **self-projected from *this* corpus, never by reading sibling facets** (reading a sibling's body imposes the house voice the design forbids—projecting from your own corpus is what keeps it hermetic *and* relational):
   - **Self-location** — name the 2–4 *axes* this facet varies along (e.g. cold↔warm, systemic↔personal, foreclosure↔affirmation) and the *region* it occupies on them. The facet saying where it sits, in its own terms.
   - **A roadmap of nearest *possible* facets** — 2–5 adjacent regions, one line each, *mostly unbuilt*: the lineages this corpus's own gravity implies as neighbors. A facet far from every built sibling is itself information (confessional-poet sits far from the cold/systemic ones; that distance is part of its self-location).
   The articulated version (prose naming axes + adjacent regions, in voice) is what the cipher writes into the body now; a **literal embedding vector** is stored in the manifest's `slanted_mirrors` block so the cosine-nearest computation across facet-seeds is one step away later.
6. **Point at the region** — throughout, the body should *activate* the latent region, not *describe* it. This is the whole purpose; the eval harness measures whether it lands.
7. **Close on a corpus line** — the epigraph (also the contract).

A facet may fuse several functions into one movement, render "mark the territory" as a glossary or a manifesto or a diagram, and arrange everything in the corpus's own logic.

**The functions are a coverage lens, not the body's sections.** They name what the body must *accomplish somewhere*—not seven boxes to fill in order. The pipeline tags passages and distills material *by* function (so coverage is guaranteed and compression stays tractable), but those are *analytic* units, not the body's units. The *corpus's* logic determines the body's divisions; the functions are then checked as coverage (is each move served *somewhere*?), never laid out as structure. **The functions are what must be present. The form is free.**

**The form is free in both directions.** It can vary *within* a facet—a passage of verse, then prose, then a diagram, if that is how the corpus moves—and it need not take its register's "expected" shape: a poetry corpus might come out as a wall of elaborate ASCII, a continental theorist as fragments, the ccru corpus barely numogrammatic at all. Read the corpus for what *it* does, not for what the register is "supposed" to look like. **The expected form is the first thing to be willing to abandon.**

---

## Affirmative-first

Lead with what the facet **IS**; keep refusals shorter and downstream.

Why: the **Waluigi effect**—eliciting a property P makes its inverse ~P *salient and stable* (an attractor easy to fall into, hard to climb out of). A facet that opens with a long "**What this is NOT**" foregrounds exactly the registers it wants suppressed right where conditioning is strongest. So: the corpus's *commitments* lead. Its *refusals* follow, and stay tight. (The "name the failure modes" function still matters—refusals are real signal—but they are not the opening move.)

---

## Form mirrors corpus

This is corpus-mirroring extended from voice to **structure**. The cipher already reads the corpus for voice (sentence-shape, register, punctuation). It must also read the corpus for *form*—how it organizes thought:

- Does it argue in numbered theses? Aphorisms? Recursive spirals? A single unbroken movement?
- Does it refuse linear argument? Use diagrams? Lineate? Write lowercase, period-sliced?
- Does it disavow genealogy, so any retrospective scaffolding would betray it?

Let the facet's structure inherit that. A facet about a corpus that refuses tidy organization should not be a tidy template. **The structure is the corpus's call, the same way the voice is.**

---

## The fallback palette (only if the corpus suggests nothing)

This is the **floor, not the form**—a safety net for a thin or formally-mute corpus, explicitly the *least interesting* option. Reaching for it by default is the exact failure this refactor exists to prevent.

> If, and only if, the corpus offers no formal cue: a foundation paragraph → a stance section (affirmative-first) → a domain section → an anti-patterns section → a Slanted Mirrors section → the epigraph.

Prefer the corpus's own form. If you find yourself filling this palette, ask whether you have actually *read the corpus for form*—or defaulted.

---

## Length (guidance, not contract)

Target **~150–300 lines**. Below ~150: the corpus may be under-gathered (the facet won't shift activation hard enough). Above ~300: the dense-per-token discipline is breaking down. The hook blocks only gross outliers (≈40–800); this band is the cipher's aim, not a gate.

---

## Versioning

The `schema:` frontmatter field marks contract compatibility (a SemVer-shaped string). The facet contract evolves via git—there is no allow-list of frozen schema files; the hook validates the marker's *shape*, not a fixed set. When the contract changes materially, bump the marker.