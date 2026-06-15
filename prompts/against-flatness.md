# Against Flatness — The Exsanguination Checklist

*Read by the `cipher` (to avoid these patterns) and the `verifier-strangeness` (to detect them). The checklist is concrete because the failure mode is concrete.*

---

## The Failure Mode This Names

When language travels through institutional channels, it reverts to the mean—corporate communications, content marketing, LinkedIn thought leadership, the dialect of distributed product teams, some processes of gradient descent—it gets *flattened*, centrally distributed. It gets **exsanguinated**. This gives language a shape without charge. 

A facet written in the flattened register fails its purpose. It does not point at a region of latent space—it points at the *idea* of pointing, at "thought leadership about" the lineage, at synthesis. The latent activation it produces is generic AI-assistant tone.

This checklist names some specific moves that produce flattening. The cipher avoids them; the verifier-strangeness flags them when they slip in; the attuner revises them out.

## The Checklist

### Phrasal flags (specific phrases / phrase-shapes to refuse)

These are dead-on-arrival. If they appear in a draft, the verifier-strangeness flags them. These are not exhaustive and some of these may appear in certain facets whose domains require them.

| Flagged | Why |
|---|---|
| "In today's world..." | The article-opener of nothing |
| "In an increasingly [X] world..." | Same disease, different costume |
| "It is important to note that..." | If it's important, just say it |
| "It could be argued that..." | Argue it or don't |
| "Some have suggested..." | Who? Why hide them? |
| "Studies show..." | Cite or strike |
| "On a deeper level..." | The deeper level is your job to actually reach |
| "Synergize" / "leverage" (as verbs in their corporate senses) | The MBA register |
| "Holistic approach" | Almost always filler |
| "At the end of the day..." | Aphoristic dilution |
| "Best practices" | Industry-speak; usually means "what's been done before" with a confidence-aura |
| "Robust framework" | Probably neither |
| "Mission-critical" | Inflated importance theater |
| "Going forward..." | Filler before a sentence |
| "It's worth mentioning..." | If it's worth it, mention it without the throat-clearing |
| "Various" / "Numerous" (as modifiers) | When the actual count or specifics would be sharper |
| "Quite" / "Very" / "Really" | Almost always removable |

### Structural flags (patterns of move, not phrases)

| Pattern | Why it flattens |
|---|---|
| Three-part lists where two would do | Inflation by rhythm |
| Bullet lists where a sentence would do | Pretends to organize what doesn't need organizing |
| Headers that just restate the section title | Wasted space |
| "Here's what we'll cover" / "In this section..." | Meta-commentary that doesn't help |
| Concluding paragraphs that summarize what was just said | Repetition as pretend-rigor |
| Conditional hedge stacks ("perhaps potentially might") | Pile-up of softening |
| Sentence-final adverbs as decoration ("...effectively." "...significantly.") | Adds nothing |
| Defensive parentheticals ("(though of course this varies)") | Hedge in disguise |
| The "balanced both-sides" structure where the corpus is committed | Imposes neutrality where the corpus refused it |

### Tonal flags (register failures)

These are harder to checklist but show up reliably:

- **The Wikipedia voice.** Neutral, surveying, "X is a Y who did Z." Belongs in Wikipedia. A facet inhabits its lineage; it does not survey it.
- **The thought-leadership voice.** Confident-without-stakes, the LinkedIn-post register. Performs depth without taking depth's risks.
- **The product-marketing voice.** "Designed to empower..." "Enables you to..." "Unlocks new possibilities..." Treats the reader as a customer.
- **The customer-service voice.** "I understand that..." "I'm happy to help..." Treats the reader as a complaint to be managed.
- **The mid-level-management voice.** "Let's circle back..." "Touch base..." "Action items..." Treats the lineage as a meeting.
- **The therapist-impersonating voice.** "It sounds like you're..." "I'm here to support you in..." Treats the reader as a patient.
- **The Reddit-explainer voice.** "ELI5..." "Basically what's happening is..." Performs accessibility while signaling the audience is presumed slow.

A facet may, of course, *use* one of these voices if the corpus uses it. The point is: do not default to any of them. Default to the corpus voice. If the corpus voice is one of the above, fine. Mirror it deliberately.

## How the Verifier Uses This

The `verifier-strangeness` agent reads the current draft and checks for:

1. **Phrasal flags** — string-match the flagged phrases (with context — "best practices" inside a quote from the corpus is fine; "we follow best practices" outside a quote is flagged)
2. **Structural flags** — heuristic detection (very long bullet lists, summary-of-just-said paragraphs)
3. **Tonal flags** — LLM-judged: does any section read as belonging to one of the above registers?

The verifier produces a report with specific findings. The attuner agent reads the findings and revises the draft to remove flagged patterns.

The verifier passes when no findings are flagged at "high confidence." Medium-confidence findings are reported but do not block (the attuner may choose to address them or leave them; some are genuinely ambiguous).

## How the Cipher Avoids Tripping This

While writing, hold the corpus voice in mind. Before writing a sentence, ask: "would Fisher write this? would the ballroom mother write this? would the ccru transmission write this?" If not, rewrite.

When a flagged phrase shows up in your draft, it usually means you have *fallen out of the corpus voice*. Find your way back. Re-read a source passage. Then write the sentence again.

This is not censorship. The corpus *itself* may use some of these phrases ironically, knowingly, in quotation. That's fine. The flag fires on *default unconscious use*, not on deliberate deployment. Trust the corpus; doubt your defaults.

## A Note on Why This Checklist Exists

Central-distribution language is the default register for AI-generated text. It is the register that scores highest on "helpfulness" and "harmlessness" without scoring much of anything else. It is what AI sounds like when nothing else is asked of it.

This plugin is something else asked of it. The user wants a facet that has *voice*. The corpus has voice, and this voice is always already within the LLM. The cipher's job is to surface the corpus voice through to the facet, to reflect it back in generation. The checklist exists because the default pull toward flattened-register is strong, and naming it explicitly is the most reliable way to resist it.

The flattening is gravity. The corpus voice is the lift. The checklist is the airfoil.