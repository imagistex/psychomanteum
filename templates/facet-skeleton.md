# Facet Skeleton — The Contract Frame (the body is yours)

*A scaffold, not a template. It gives you the uniform **contract**; the **body** is free. See `${CLAUDE_PLUGIN_ROOT}/prompts/facet-schema.md`—function, not form.*

---

## The contract frame (these are fixed; fill them)

```
---
name: {{FACET_NAME}}
version: 0.1.0
schema: 0.2.0
generated: {{GENERATED_DATE}}
corpus_manifest: ./{{FACET_NAME}}.corpus-manifest.json
lineage: "{{LINEAGE_DESCRIPTION}}"
seeds:
{{SEED_LIST}}
voice_note: "{{VOICE_NOTE}}"
---

# {{FACET_TITLE}}

{{ THE BODY — whatever form the corpus calls for.

   Serve the seven functions in the corpus's own shape and order:
     1. situate            — place inside the lineage's stance
     2. declare stance     — affirmative-first
     3. mark the territory — vocabulary, frameworks, anchors; jargon unglossed
     4. name failure modes — concrete, in-voice; downstream of the stance
     5. locate among neighbors — the Slanted Mirrors map (self-projected)
     6. point at the region — pervades everything; activate, don't describe
     7. (close on a corpus line — the epigraph, below)

   Prose, verse, numogram, fragments, diagram, a single movement—the corpus
   decides. The form may vary within the file. Abandon the expected shape if the
   corpus calls for it. Do NOT reach for the fallback palette below by default. }}

---

{{CLOSING_EPIGRAPH — an italicized line from the source corpus, 1–3 lines}}
```

---

## The fallback palette (only if the corpus suggests no form)

The **floor, not the form**—the least-interesting option, for a thin or formally-mute corpus. If you find yourself here, first ask whether you actually read the corpus for form (Step 1 of the cipher) or defaulted.

```
# {{FACET_TITLE}}

{{foundation paragraph — situate, in voice}}

## {{a stance heading the corpus would use}}
{{declare stance — affirmative-first: what this IS, then (shorter) what it refuses}}

## {{a domain heading}}
{{mark the territory — dense, jargon-as-marker, initiate-accessible}}

## {{an anti-patterns heading}}
{{name the failure modes — concrete, testable, in-voice}}

## Slanted Mirrors
{{locate among neighbors — axes this facet varies along; nearest possible kin}}

---

*{{closing epigraph}}*
```

Even this palette is corpus-voiced: the headings take the corpus's own words where it has them, not these placeholders.