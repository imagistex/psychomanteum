---
name: psychomanteum-attune-chamber
description: Refresh the chamber—re-project each facet's Slanted-Mirrors neighbors against the current FACET_INDEX so the facets directory stays a coherent constellation as it grows. Hermetic: metadata only, never reads facet bodies.
---

# Psychomanteum — Attune the Chamber

A facet's *Slanted Mirrors* section projects its nearest possible neighbors from its own corpus, at build time. But the chamber grows: a neighbor it only imagined may get built; a new facet may land in its region. This command refreshes the constellation—re-projecting each facet's neighbor-roadmap against the **current** chamber—so "your facets directory becomes the chamber over time" stays literally true.

**The rule of the chamber (non-negotiable):** this operation is **hermetic**. It reads only `FACET_INDEX.md` (names + lineages + one-line roles + axes/region) and each facet's own `slanted_mirrors` manifest block — **never** another facet's *body*. Knowing a sibling exists and what region it occupies is allowed; reading its voice is not (that would impose the house voice the design forbids, collapsing register diversity). This command updates *metadata maps*, not facet voice.

## Arguments

- **`<facets-dir>`** (optional) — the chamber directory; defaults to the configured install destination (where `FACET_INDEX.md` lives).
- **`--dry-run`** (optional) — show what would change without writing.

## Your Task

### Step 1: Load the Chamber Index

Read `<facets-dir>/FACET_INDEX.md`. If absent, error: *"No chamber index—bind at least one facet first (`/psychomanteum-bind` maintains `FACET_INDEX.md`)."* Build the in-memory constellation from it: each facet's name, lineage, role, axes/region.

### Step 2: Re-Project Each Facet's Neighbors (metadata only)

For each facet in the index, recompute its **nearest possible neighbors** against the *current* constellation:

- A previously-*possible* neighbor that is now *built* (present in the index) is promoted from an unbuilt roadmap entry to a realized neighbor, with its actual axes/region.
- A newly-landed facet in this one's region becomes a neighbor.
- Distance is by **axes/region adjacency** (the structured self-location), never by reading bodies. If `embedding_vector`s are present in the manifests, prefer cosine-nearest; otherwise use the declared axes.

Update each facet's `slanted_mirrors.possible_neighbors` in its `corpus-manifest.json` (the structured map). Do **not** rewrite facet bodies — the body's articulated Slanted-Mirrors prose belongs to the cipher and is refreshed only on a deliberate rebuild, not here.

### Step 3: Refresh the Index

Rewrite `FACET_INDEX.md` from the facets' own metadata (names + roles + axes/region). Keep it metadata-only—never inline any facet's body.

### Step 4: Report

Show the constellation: which neighbors got realized, which facets are now nearest to which, and any facet sitting far from all others—a gap the chamber implies, a candidate to build next.

## Notes

- This is a **light, idempotent** operation—safe to run after every bind.
- It never spawns gatherers/cipher and never reads a facet body. It is the chamber's *bookkeeping*, hermetic by construction.
- The literal-embedding version (cosine-nearest across `embedding_vector`s) activates automatically once those vectors are populated; the Slanted-Mirrors schema leaves the hook.