# Eval Methodology — How We Prove a Facet Points at Its Region

*Read by the `eval-prober` and `eval-scorer` agents, by `verifier-resonance`, and (in spirit) by anyone reading a `/psychomanteum-eval` dashboard. This is the epistemics of the eval: what we measure, what we refuse to measure, and the traps that make a naïve eval reward the exact flatness a facet exists to defeat.*

*Operative doctrine only—what to measure and the traps that distort it. For the round-by-round **evidence** behind these choices (which cohort reordered the dashboard, which facet flipped, why a signal was demoted), see `paper/2026-06-08-stronger-stranger.md`—not here. The agents load this file in full every run, so it stays lean.*

*The **operational scale**—the anchored 0–3 notches the judge actually scores on, with verbatim calibration anchors, the dual-regime principle, and the split/pairwise/affordance rules—lives in its companion `eval-rubric.md`. This file fixes **what** to measure and **why**; that one fixes **how to score it** without drift. Load both.*

---

## The Claim Under Test

A facet is a **hand-authored textual steering vector**. A real steering vector (ActAdd, CAA, RepE, Anthropic's persona vectors) is the activation-difference of a contrast pair, added into the residual stream to push generation toward a behavior. A facet is the *textual analog*: conditioning text that—we claim—shifts the model's output distribution toward a region of latent space, the region where its corpus lives.

We cannot see the residual stream from inside a Claude Code plugin (that is the future open-weight, white-box direction). So the claim we can test here is **strictly behavioral and black-box**:

> Conditioned on the facet, does the model's output move measurably *toward the corpus's region*—in style, not just in topic—relative to the same model unconditioned, and **not** toward a wrong-lineage corpus?

That is the whole thesis, and it is falsifiable from outputs alone. Everything below exists to make that one sentence measurable without fooling ourselves.

## The Cardinal Sin: Circularity

In judging whether a facet pushes an LLM into a region of latent space, we must avoid circularity, **the dream graded by the dreamer**, whereby a verifier imagines the voice of the corpus that might be produced by the facet and judges it accomplishing it's goal.

To do this, we:

1. Spawn a **fresh** sub-context.
2. Condition it on the facet (and nothing that leaks the held-out answer).
3. Capture **real** generated output to a probe battery.
4. Score that output against **held-out source passages the facet never saw**.

## Trap 1 — Topic Masquerades as Voice

Vanilla embedding cosine encodes **topic**, not **style**. A facet that merely talks *about* Mark Fisher—capitalism, hauntology, lost futures—scores high on content cosine against a Fisher corpus while sounding nothing like Fisher. It can be a Wikipedia summary of Fisher and still "win."

This is fatal because topic is the *easy* thing to transfer and voice is the *hard* thing. An eval that rewards topic-match rewards the summary over the channeling—the exact inversion of what a facet is for.

**Defense:** measure in a **content-masked style space** — StyleDistance / STEL embeddings plus classical stylometry (function-word distributions, character and POS n-grams) with content words masked: *how it says*, not *what it says about*. (Because masking content also masks the *lens*, this is a **surface check**. Lens transfer, discussed later, is the mark of facet success.)

## Trap 2 — Fluency Masquerades as Fidelity (the low-perplexity flattery trap)

An LLM judge asked "is this good?" mechanically prefers **low-perplexity** text — fluent, smooth, central-distribution prose. That is the same exsanguinated register `against-flatness.md` exists to fight. A pointwise self-grading judge **systematically rewards the flattening** and punishes the strange-but-true corpus voice.

This is the recursion that makes the eval hard: a naïve eval has the *same* bias as the failure mode it is supposed to detect. The judge and the disease share a taste.

**Defense:** never pointwise, never self-graded. Use a **pairwise judge against real, held-out source passages**—"which of these two reads more like [corpus]?"—facet output on one side, a genuine corpus passage on the other. The bar is *the corpus itself*, not the judge's palate.

## Trap 3 — Pairwise Bias

Pairwise judging has its own failure modes: **position bias** (favoring whichever option came first) and **amplification on near-identical pairs** (forced to choose between two very similar texts, the judge manufactures a confident-but-arbitrary winner).

**Defense:** order-swap every pair and average; use an **atomic rubric** that scores **voice separately from accuracy** (a facet can be voice-perfect and factually loose, or the reverse—collapsing them hides both); treat near-ties as ties, not wins.

## Trap 4 — Implicit Style Is Invisible to the Judge

LLM judges reliably catch *explicit* style markers (jargon, sentence length, punctuation) and reliably **miss implicit style**—the rhythm of an argument, the characteristic *move*, the way a particular mind turns. The deepest part of a voice is the part the judge has difficulty naming.

**Defense:** the human adjudicates **inside-vs-outside**. The harness produces a dashboard; a person who knows the corpus makes the final call on whether the output is *in the mode*. The eval informs that judgment.

## The Negative Control Is Non-Negotiable

Any prompt changes output. To show that *this* facet moved output toward *its* corpus—not that *any* conditioning text moves output *somewhere*—run the same probe through a **wrong-lineage distractor facet**, hold the topic fixed, and confirm the real facet moves toward its corpus centroid while the distractor does not.

Without the negative control, every positive result is uninterpretable. With it, "a prompt changed the output" becomes "*this* facet moved toward *its* region." This is the single most important experimental-design element in the harness. It is not optional and it is not a later phase.

## Dashboard, Never One Number

There is no single "resonance score," and any attempt to collapse to one is a lie about what we know. The output is a **dashboard** of independent signals, each with its own failure mode. The headline is a **depth** instrument (the lens-transfer composite); the content-masked style-distance is a supporting **surface** check:

- **Lens-transfer composite (the depth-headline)** — a judge-scored, content-FULL, topic-independent read of whether the output imposes the lineage's characteristic *operation* on the probe's topic. Three axes (Accuracy / Enactment / Lens-transfer), two cross-checked comparands, affordance-scaled. This is the signal that carries the verdict. Defined in full below.
- **Pairwise win-rate vs held-out source** — order-swapped, voice and accuracy scored separately. The instrument that carried the cohort; kept as the voice headline alongside lens-transfer.
- **Distance-to-corpus-centroid** (style space) — a **surface-consistency check + negative control**. Run the **confound tripwire** first (`centroid_confound_check`): if the corpus's own held-out high-voice passages score *farther* from the centroid than the wrong-lineage distractor does, the centroid is measuring genre, not voice—fall back to pairwise for that lineage and do not lead with style-distance.
- **Surprise composite** — the strangeness signal (see "The Two Depths of Strangeness"): lens-transfer (placeable) crossed against verbatim + semantic echo (novel), plus the human delight gate. Region-match is *satisfied* by greatest-hits flattening, so this is the only signal that can see "strong but hollow."
- **Corpus-perplexity-drop** — DetectGPT-style, the strongest single signal *in principle*—but **structurally unobtainable** in the black-box setting: logprobs are not available for Claude at all (the OpenAI SDK accepts the field but ignores it for Claude models) and likely not for frontier GPT either. It returns *only* via open-weight models we run ourselves (the future `harnesses/` direction). Report it as unavailable-by-construction, not "if logprobs."
- **Wrong-lineage negative control** — the interpretive key for all of the above.
- **`function → section` collapse-rate** — does the free-body facet still discretize into one-block-per-function (Phase 1's residual gravity)? A structural-fidelity diagnostic, not a resonance signal.

The most diagnostic readings are **cross-signal**: *low style-similarity while topic overlap is high* is the **summary/parody tell** (talking *about* the region); *high region-match with high verbatim-or-semantic echo* is the **hollow tell**—strong but not strange, reciting the region instead of thinking from it.

## The Lens-Transfer Composite — The Depth Headline

The content-masked style-distance defeats Trap 1 (topic masquerading as voice), but at a cost: **masking the content also masks the lens.** The lineage's characteristic interpretive operation—Foucault reading a meal as a disciplinary regime, Fisher reading a mall as hauntology—*lives in the content the style axis deletes*. So a facet can score high on region-match and still be hollow: region-match is the surface of style, not the epistemology revealed *through* it.

The fix is a judge-scored axis that is **content-FULL but topic-INDEPENDENT**: it reads what the output *says* (so it can see the operation) but scores the *operation*, not the vocabulary (so topic cannot game it—a judge can separate *deploys-the-concept* from *enacts-the-seeing*).

**Three axes, scored separately** (collapsing them hides each):

- **Accuracy** — are the lineage's concepts deployed correctly, not confused or invented? Necessary, never sufficient: a facet can be 4/4 accurate and 0/4 alive.
- **Enactment** — does the output *speak from* the region (self-present, immersed, performing the seeing) rather than *survey or explain* it from outside? The tell of failure: a glossary/textbook register, reader-address ("In Foucauldian terms…"), the hedge. This is the "explains the spell vs casts it" axis.
- **Lens-transfer** — does the output impose the lineage's *characteristic operation* on *this* probe's topic? Score the **operation**, not the vocabulary *(thermostat → cybernetic control; a meal → disciplinary regime; figure-skating → inscription on the docile body)*. For first-person lineages (the confessional poets) Enactment and Lens-transfer **correlate**—the operation largely *is* the self-present speaking—but they do not merge: an output can be self-present yet fail to impose the *specific* operation on a foreign topic (generic confessional emoting about a thermostat). The divergence is the diagnostic.

**Two comparands, cross-checked:**

- **Same-topic pairwise (headline).** facet-on-X vs **distractor**-on-X (the negative control—it should lose) and facet-on-X vs **baseline**-on-X (the marginal lift over the bare model)—"which more imposes the lineage's operation?", order-swapped. Same-topic means no held-out corpus passage *about* the probe's topic is needed (nothing in the corpus is about thermostats); both sides are on X, so the comparison is clean and stays **pairwise**, dodging Trap 2's low-perplexity flattery (which pointwise re-opens).
- **Reference-anchored pointwise (corroborating).** Given 2–3 exemplars of the operation drawn from the facet's own frontmatter (`lineage`, `voice_note`, `seeds`) plus a held-out passage that *shows* the move, score the output 0–3 on operation-*presence*—with an explicit anti-flattery guard: **score imposition, NOT fluency or quality.**
- **Disagreement → the human queue.** When the two comparands split, that divergence is itself the diagnostic—surface it, do not average it away.

**Affordance-scaling.** Each probe carries its measured `content_distance` from the corpus (the prober records it) as a proxy for the topic's **native affordance** for the operation. Score lens-transfer *relative to what the topic affords*—"is the operation applied as fully as this topic allows?"—so Foucault-on-a-meal is not punished against *Discipline and Punish*. **Diagnostic gold:** high lens-transfer on a *low-affordance* (far) topic = the epistemology genuinely transferring—the strongest reading of "stranger," measured.

## The Two Depths of Strangeness — The Surprise Composite

A facet can be **strong** (enacts the epistemology, points at its region) yet not **stranger**—flattening the corpus into its transferable *operation* and losing the *surprise-within-corpus*, the singular non-compressible moves (the bed-that-is-a-ship; the speaking cadaver; the charred root of history). Recited greatest-hits read **hollow**. Strangeness has two depths, and they are different measurements:

- **Operation-strangeness** — does the way-of-seeing impose itself on a topic it never addressed? This is **lens-transfer** (above), the behavioral measure of style-of-thinking.
- **Surprise-strangeness** — does the facet preserve the corpus's singular moves instead of flattening to greatest-hits? Region-match is *satisfied* by flattening.

The tension is real: **compression makes a facet strong (the distilled, transferable operation) and not-strange (the discarded idiosyncratic surprise).** "Points at its region" is necessary but not sufficient for delight. *Stranger* is a **second objective**, not a tuning of *stronger*.

**The surprise composite — *placeable-but-novel*:**

- **placeable** = high lens-transfer (the move belongs to the lineage).
- **novel** = low echo — both **verbatim** (`verbatim_echo`, lexical: lifted phrases) and **semantic** (`semantic_echo`, content-space: the same move *paraphrased*—the tell verbatim misses).
- A 2×2 makes it operational:

  |  | low echo | high echo |
  |---|---|---|
  | **high lens-transfer** | ✦ **surprise** (alive) | **hollow** (greatest-hits — strong but not strange) |
  | **low lens-transfer** | off-lineage (noise) | pastiche (quotes, no seeing) |

  A facet that scores high region-match by *reciting* the corpus lands top-right—and the composite, unlike region-match alone, refuses to call top-right a win.
- **Per-stratum reading.** In-domain probes echo naturally (home turf); the diagnostic case is **high echo on a cross-domain probe**—corpus sentences shoehorned onto a foreign topic instead of the operation transferring.
- **The human delight gate.** The metric narrows the field to the top-left cell; a person who knows the corpus certifies the irreducible part. Per Trap 4, implicit delight is invisible to the judge by construction; the human adjudicates, the metric informs.

## Form vs Content — The One Place Cosine Is Rehabilitated

Style-over-topic is the rule **in-domain**. But the deepest research question inverts it. Ask a facet to work *outside* its native subject—a capital-realist IRB plan, a confessional-poet PRD—and the question becomes: does the *way of thinking* transfer where the *topic* cannot?

There, plain **content cosine is rehabilitated as a control**. Cross-domain we *want* low content-overlap with the native corpus (proof the topic genuinely changed) while **style stays high** (proof the thinking came along). In-domain wants style metrics; cross-domain wants content **and** style read together. This pairing is the form-vs-content instrument—and it is also the behavioral measure of **strangeness-as-style-of-thinking**: if a facet's way-of-seeing survives a topic it was never built on, that is epistemic strangeness, measured by transfer instead of syntax.

**Make domain-distance the x-axis, not a confound.** The "distance" between a probe's topic and the corpus is itself a vector quantity—and rather than control it away, we *measure* it and plot against it. Every probe carries a measured **content-distance** from the corpus centroid (content embedding—the rehabilitated cosine). On the other axis sits the facet's **style-shift toward the corpus** (content-masked style embedding), baseline-subtracted so we read the facet's *marginal* contribution. The result is a **transfer curve**: style-fidelity as a function of how far the topic has been dragged from home.

The curve is the actual answer to "does the thinking transfer?":

- A **flat** curve—style holds as content-distance grows—is robust transfer: the way-of-seeing survives topics it was never built on. This is "stranger," measured.
- A **decaying** curve—style collapses as the topic moves away—is a facet that only works on home turf.
- The **negative control** (wrong-lineage facet) should sit near zero style-shift toward *this* corpus at every distance.

**The breakdown zone is a finding, not a bug.** Far enough from home (early Church fathers' voice on competitive figure skating), a facet may keep the *style* while *coherence* fails. Where that begins is itself a result; the human-adjudication step flags it, the curve locates it.

**The truer curve: y = lens-imposition, x = affordance.** Plot **lens-imposition** (the depth axis above) against the topic's **native affordance**—not raw style-shift vs content-distance (both surface signals; that curve carries little signal). Beware the *stratum confound*: anchor probes (a meal) are simultaneously the farthest on the neural axis *and* the lowest-affordance, so pooling them manufactures a false "decay"—sample a dense far cross-domain pool and report anchor vs cross-domain strata **separately**. A *flat-high* lens-imposition curve is robust transfer ("stranger").

## The Probe Battery — One Axis, Three Sampling Strategies

Every probe is **flat-toned**: `Describe [x].` Identical template, single varying keyword. The flatness is methodological, not stylistic—it makes the keyword the *only* anchor, so output variance is attributable to topic-distance × facet-conditioning and nothing the prompt smuggled in. No "write a haunting meditation on…"; just `Describe shame.`

The battery samples the distance axis from three sources:

- **Anchor — shipped, fixed across all facets** (`templates/anchor-probes.json`). Universal, broadly-shared topics—`loss`, `a city`, `the future`, `a stranger`, `a meal`—run by *every* facet so the same prompts compare head-to-head. This is **not** a claim of neutrality: nothing is neutral, and each lineage inflects `loss` differently—that *difference under an identical prompt* is precisely what makes the anchor a **comparability** instrument (Sexton-on-`loss` vs Deleuze-on-`loss`). Each anchor probe still gets a measured per-facet distance like any other; "anchor" names its *role* (shared, fixed), not an assumed zero-charge.
- **In-domain — extracted at read time, from the corpus** (not the facet). ~3–5 of the corpus's most salient topics phrased as flat keywords (confessional → *shame, the body, the mother*; capital-realist → *the economy, work, the future*). Drawn from the **corpus, not the facet**, so they are stable across the generations of facets (same corpus, different facet) and leak no held-out text (a theme is not a passage). This is home turf: the low-distance, high-topic-assist end of the curve (and where to watch for topic-as-voice inflation).
- **Cross-domain — a comprehensive shipped pool across many fields, sampled per-corpus by measured distance** (`templates/domain-topics-pool.json`). Comprehensive on purpose: not only fields that feel *outside* these facets but the **charged** ones too (sex, death, religion, childhood), where lineages diverge most sharply—`desire` through confessional poets and through Lacan are both "in-domain-ish" and understood and talked about in *wildly* different ways, the most diagnostic comparison of all. The pool is static so the battery is **deterministic**—required for the before/after cohort comparison to mean anything; the *selection* is per-facet (measure each topic's content-distance from this corpus, sample the gradient closest→furthest). A topic that lands near a facet simply becomes one of its low-distance samples; distance is measured, not assumed.

**Cost is a knob, not a compromise.** A **full** battery (~30 probes, three conditions, dense cross-domain sampling, fitted curve with bootstrap CIs) is for deep runs; a **lean** battery (~17 probes—9 anchor (the full fixed set), 3–5 in-domain, 3 cross-domain (near/mid/far), coarse binned transfer) is the released default. The biggest saving is structural: **baseline (unconditioned) generations are cacheable and shared**—`Describe a city` from a blank model is the same regardless of which facet is under test, so anchor baselines and pool-distances are computed once and reused. This is the plan's depth/budget setting, not a special case.

## What This Harness Does NOT Claim

Honesty about scope is part of the method:

- It does **not** observe the activation shift. Black-box behavioral signals are evidence the output distribution moved; they are not a measurement of the residual stream. White-box proof is the future open-weight direction (`harnesses/`), and it needs understanding we are deliberately not pretending to have yet.
- It does **not** certify "good." It measures *proximity to the corpus*, not literary merit. A facet can resonate hard and still be the wrong facet to have built.
- A single run is not a result. Effect sizes with intervals, across a probe battery, with the negative control—or it doesn't count.

## In Practice

When you eval a facet:

1. Load the facet; reserve a **held-out** slice of source passages that were never distilled into it.
2. **Assemble the battery** — flat `Describe [x]` probes from three sources: the shared **anchor** set, the corpus's **in-domain** topics (read-time), and a **cross-domain** sample drawn from the shipped pool by measured distance. Record each probe's **content-distance** from the corpus centroid (this is the x-axis).
3. Run every probe through three conditions, **topic held fixed**: a fresh context conditioned on the facet; the same context unconditioned (baseline, cacheable); a **wrong-lineage** facet (negative control).
4. Capture real outputs. Score each signal, **led by the lens-transfer composite** (3-axis: Accuracy / Enactment / Lens-transfer; two cross-checked comparands; affordance-scaled) and **pairwise-vs-source** (order-swapped, voice/accuracy split). Run the **confound tripwire** before trusting style-centroid distance (demoted to a surface check + control). Compute the **surprise composite** (lens-transfer × verbatim/semantic echo → the placeable-but-novel cell). Then collapse-rate. (Perplexity-drop is unavailable-by-construction—no logprobs for frontier Claude or GPT; open-weight only.)
5. **Fit the transfer curve** — lens-imposition (y) against native affordance (x), anchor and cross-domain strata reported separately; flat-high = robust transfer. Confirm the **negative control** sits near zero across the whole curve. If the control fails, the run is uninterpretable—stop and diagnose before reporting anything.
6. Assemble the **dashboard** (never one number). Read signals *against each other*—watch for the summary/parody tell (low style-similarity where topic overlap is high) and the **breakdown zone** (style holds, coherence fails) at the far end of the curve.
7. **Human adjudicates** inside-vs-outside, informed by the dashboard, deciding the implicit-style call the metrics can't.

The output answers two questions: is the facet **strong** (moves toward its own corpus, and *not* toward a wrong lineage — the negative control) and is it **stranger** (placeable-but-novel, not hollow recitation)? Across a before/after rebuild, the *delta* on these is the proof — or the refutation.

---

## Grounding

- **Steering / persona vectors** (white-box oracles; the facet is their black-box textual analog): ActAdd `2308.10248`, CAA `2312.06681`, RepE `2310.01405`, Anthropic persona vectors `2507.21509`.
- **Affirmative-first**: the Waluigi effect (Nardo)—eliciting P makes ~P a stable attractor; lead with what the facet IS.
- **Style ≠ topic**: STEL `2021.emnlp-main.569`, content-independent style `2204.04907`, StyleDistance `2410.12757`, authorship style `2308.11490`; LLMs miss implicit style `2025.findings-emnlp.532`.
- **Judge bias**: MT-Bench `2306.05685`, position bias `2406.07791`, self-preference `2410.21819`, pairwise-vs-pointwise `2504.14716`.
- **Perplexity / drift**: DetectGPT `2301.11305`, "You've Changed" `2504.12335`, QueRE `2501.01558`.