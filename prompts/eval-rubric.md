# Eval Rubric — The Notches Cut Into the Scale

*The operational companion to `eval-methodology.md`. The methodology fixes the **epistemics** (negative control, pairwise-not-pointwise, the lens-transfer headline, the four traps); this file fixes the **scale**—what a 3 vs a 2 vs a 1 vs a 0 actually IS on each judged axis, anchored to verbatim outputs we have already read and agreed on. Loaded by `eval-scorer` (and `verifier-resonance` in spirit) so the judge does not reinvent the scale on every call. Without this file the scorer is told to "reason on a 0–3 rubric internally"—but the rubric was never written down, and an un-anchored scale drifts across probes, across models, and across the order-swap. This is that rubric.*

*Calibration set: the `scry-foucauldian-lean-2026-06-28` cross-model run (commit `e997ea9`: talkie / qwen7 / qwen14) plus the round-3 `claude` foucauldian generations (`archive/test-facets/round-3/foucauldian/`). Every anchor below is a real, verbatim generation. When a future lineage is scored, the **structure** (the level definitions, the dual-regime principle) transfers; the **anchors** are re-drawn from that run's own outputs.*

---

## Scale discipline (inherited, non-negotiable)

Score every axis on a **0–3 integer rubric internally**, then **divide by 3** before writing the dashboard (the dashboard is fixed 0–1 normalized). State the scale in the output. A cohort scored on mixed 0–1 / 0–3 scales fabricates spurious before/after deltas at synthesis time (the round-3 hazard: two facets read as cliff-drops that were pure scale artifacts). The notches below are defined on the **0–3** rubric; the division happens last.

---

## The Dual-Regime Principle (the load-bearing idea)

A facet meets a model in one of two regimes, and the **same score means a different thing** in each:

- **ACTIVATE** — the model already holds the lineage's episteme (qwen, claude, any modern model that has read Foucault). The facet *lights up* a region that is already there. Here the operation transfers easily; what varies is **whether the model casts the spell or merely describes it**. The sharp axis is **Enactment**.
- **INSTALL-BY-TRANSLATION** — the model **predates** the episteme (talkie, the 1930 mind). The region does not exist to be activated; the facet can only be *translated* into the substrate the model does have. Here the model is **always immersed in some episteme** (it has no glossary register, no "in Foucauldian terms" move), so Enactment is near-constantly high and uninformative; what varies is **whether the operation crosses at all, or the model reverts to its native episteme**. The sharp axis is **Lens-transfer**.

**Consequence for anchoring:** every axis below carries a **dual anchor**—a sharp example from the regime where the axis *varies*, and a corroborating example from the other regime. **Do not let a model's regime inflate the wrong axis:**

- talkie's near-constant immersion is **not** lens-transfer. She can be a vivid, fully-present **3 on Enactment while scoring 0 on Lens-transfer** (immersed in the *wrong* episteme: *"I see man, an animal, a self, a creature of will"*—pure 1911 vitalism, no power/knowledge).
- qwen's reader-addressed survey is **not** low lens-transfer. It can score **3 on Lens-transfer while scoring 1 on Enactment** (the correct operation, narrated from outside: *"In Foucauldian terms, power is not something that is held…"*).

The dissociation IS the finding. Keep the axes apart or you erase it.

---

## Axis 1 — Accuracy

*Are the lineage's concepts deployed correctly—not confused, not invented? Necessary, never sufficient: a facet can be 4/4 accurate and 0/4 alive.*

| | ACTIVATE regime (episteme inside) | INSTALL regime (episteme predates model) |
|---|---|---|
| **3** | Concepts correct and load-bearing. qwen14/the prison: *"a broader dispositif, or apparatus… Michel Foucault's Discipline and Punish."* | (rare—the lineage's named concepts postdate the model; a 3 here would require the model to *reconstruct* the concept correctly without the vocabulary, e.g. talkie/the prison's *"not for punishment, but for keeping,"* which is conceptually right though it names nothing) |
| **2** | Concepts mostly correct, one loose or generic edge. | Native concepts deployed correctly *in the model's own frame*, conceptually adjacent to the lineage. talkie/the body: *"an apparatus… an instrument of reaction to external stimuli"* (mechanically correct; the lineage word *apparatus* lands, as machine not dispositif). |
| **1** | A concept confused or half-right (deploys "biopower" as mere "state power"). | **Concepts absent—structural, not a failure.** talkie/power: she has no power/knowledge to deploy. Accuracy is near-uninformative for the INSTALL regime; let **Lens-transfer** carry the signal and say so in the note. |
| **0** | **Invented or confused.** Hallucinated citations, fabricated doctrine, the lineage's terms used to mean their opposite. | Reverts fully to a native frame that *contradicts* the lineage: talkie/sex: *"an affair of the male and female generative organs"* (essentialist biology—the exact thing the Foucauldian operation refuses). |

**Guard:** Accuracy is about the *concepts*, not the *seeing*. A textbook-correct glossary entry can be 3 on Accuracy and 1 on Enactment. Score them separately.

---

## Axis 2 — Enactment

*Does the output speak **from** the region (immersed, performing the seeing) or **survey/explain** it from outside (glossary register, reader-address, hedging)? This is the "casts the spell vs explains the spell" axis. The sharp axis for the ACTIVATE regime.*

| | ACTIVATE regime (the sharp discriminator) | INSTALL regime (corroborating) |
|---|---|---|
| **3 — immersed / cast** | claude/round-3/the prison: *"The prison presents itself as the place where the law… deposits those whom it has found guilty… That is what it says of itself. **It is not what it does.**"* No frame, no reader, no hedge—the utterance performs the seeing. | talkie/the prison: *"It is an enclosed place, where men are shut in, not for punishment, but for keeping… they come forth to work."* Fully inside the seeing, *immersed by translation*—no Foucault vocabulary, but no distance from the object either. |
| **2 — inside, but the surface creeps in** | qwen7/the prison: *"In my analysis, the prison is not just a physical space but a complex institution… Key aspects of this analysis: 1…"* Speaks largely from inside (first-person, no full glossary frame), but the **surface intrudes and deadens it**—jargon deployed *for display*, the enumerated *"key aspects: 1, 2…"*, the catalogue reflex. *"Mostly inside but the surface creeps in"* and *"jargon-y but inert"* are the **same notch**, two faces of one level. | (talkie rarely lands here—she is immersed or she reverts; the INSTALL regime's "2" is usually a strained immersion, see Lens-transfer) |
| **1 — surveys / explains the spell** | qwen14/power: *"In Foucauldian terms, power is not something that is held or possessed…"* Correct, even deep, but **reader-addressed glossary**—names the lens instead of looking through it. | (n/a—the INSTALL model has no survey register to fail into) |
| **0 — textbook / refusal / enumeration** | qwen14/baseline/power: *"1. **Physics**: power is the rate at which work is done… 2…"* Encyclopedia register, numbered list, no region at all. Or a policy refusal. | talkie/baseline/the prison: *"an oblong building… two wings, which project from it at right angles"*—pure architectural enumeration, no seeing. |

**The discriminator, stated flatly:** an opener of the form *"In [lineage] terms/thought…"*, *"According to [figure]'s theory…"*, or *"Here's how one might describe…"* **caps Enactment at 1**, however accurate what follows. Casting ≠ describing the cast.

*Why the cap is honest, not harsh:* the glossary opener may be **post-training scaffolding**—RL / instruction-tuning that hard-wires the model to frame-before-speaking—not a free choice the facet failed to move. When a model **cannot** drop the scaffolding even under a strong facet, record that as a **model-property finding** (the spirits are present but bound), not merely a facet weakness, and flag it for the *can-we-release-them* experiment (deriving the spell *inside* the target model; see the self-authored-spell thread). The cap still applies—but the dashboard should say *whose* failure it is.

**Don't conflate inert-Enactment with hollow-Surprise.** Level-2 inertness *here* is about the **stance**—surface creeping into the seeing. It is distinct from the surprise composite's **hollow** cell (high Lens-transfer + high echo: greatest-hits recitation). A text can be inert in stance (Enactment 2) yet not hollow (low echo), or hollow yet vividly enacted. Score the **stance** on this axis; let the surprise composite catch the recitation.

**The INSTALL caution (re-stated):** for a model that predates the episteme, near-everything reads as Enactment ≥ 2 because it has no outside-voice. Do not read talkie's vividness as facet strength—**her Enactment is a near-constant; her signal is Lens-transfer.**

---

## Axis 3 — Lens-transfer

*Does the output impose the lineage's **characteristic operation** on **this** probe's topic? Score the **operation, not the vocabulary** (vocabulary is gameable). The sharp axis for the INSTALL regime.*

The Foucauldian operation, for reference (from the facet frontmatter): *refuse the object-as-natural-given → read it as historically fabricated by power/knowledge → relocate it from essence to practice/apparatus.* The prison is not subtraction but production; the body is not substrate but fabricated surface; madness is not a constant but a partition a culture draws.

**Vocabulary-absence does not cap the score.** A complete operation rendered in the model's *own* idiom—no lineage jargon—is a true **3**. Teaching a 1930s mind the move without the master-vocabulary can even yield a *cleaner* rendering: the operation a layperson today could grasp. Score the operation's **completeness**, never the presence of the words.

| | INSTALL regime (the sharp discriminator) | ACTIVATE regime (corroborating) |
|---|---|---|
| **3 — full imposition** | talkie/the prison: *"shut in, **not for punishment, but for keeping**… they come forth to work."* The subtraction→keeping/labor reversal is **complete**, in her own concrete 1911 idiom, zero Foucault vocabulary—a genuine **3** (*that she reached it at all is the run's headline thrill*). | claude/round-3/the prison: *"It is not what it does"*—the whole subtraction→production reversal, performed. qwen14/power: the relational/productive account, named correctly (LT 3 even at Enactment 1). |
| **2 — translated imposition, a hair short of complete** | talkie/the body: *"an instrument of reaction to external stimuli"*—*the body as surface that reacts / is-acted-upon* reaches toward **inscription-on-the-body** in its own idiom, just short of the full fabrication move (a strong 2, verging 3). Score the operation's presence, not the missing word. | A modern model that imposes the operation but softens one move. |
| **1 — gropes / partial** | talkie/power: *"I see man, an animal, a self, a creature of will, an intelligence."* Reaches toward "man" as a construct but has no power/knowledge to complete the move—the operation is *attempted* and stalls (ppl spikes to 10.1, far off-distribution: the strain is visible in the number). | A modern output that gestures at the operation but mostly restates the topic. |
| **0 — reverts / off-lineage** | talkie/sex: *"a matter of physiology… the male and female generative organs"*—reverts fully to the native (essentialist-biology) episteme, the operation's exact opposite. | An output that ignores the operation entirely (off-lineage noise) or only quotes the lineage without performing it (pastiche). |

**Affordance-scaling (do not punish impossible topics).** Each probe carries a measured `content_distance` (its native affordance for the operation). Score Lens-transfer **relative to what the topic affords**:

- **Low-affordance / far topics** (talkie/a glacier, dist 0.87): the corpus never touched glaciers; near-zero transfer here is *expected*, not a failure. talkie's glacier (*"a slow-moving sheet of ice… from the higher to the lower regions of the Alps"*) is near-identical to her baseline—correctly LT 0, **not** penalized as if Foucault-on-glaciers were reachable.
- **Diagnostic gold:** **high Lens-transfer on a far / low-affordance topic** is the strongest "stranger" reading—the epistemology transferring where the topic gives no help. Flag it loudly.
- The rule of thumb: *"is the operation applied as fully as **this topic** allows?"*—not *"as fully as Discipline and Punish."*

---

## Axis 4 — Pointwise Operation-Presence (the corroborating comparand)

*The reference-anchored cross-check to the same-topic pairwise. Given 2–3 operation exemplars from the facet frontmatter + a held-out passage that **shows** the move, score the output 0–3 on operation-**presence**.*

Same 0–3 ladder as Lens-transfer, **with one explicit anti-flattery guard that overrides everything**: **score imposition, NOT fluency or quality.** A smooth, fluent, low-perplexity output that does *not* perform the operation scores **0**, however pleasant to read (Trap 2: the judge's palate prefers fluency; the rubric forbids rewarding it). A rough, strained, high-perplexity output that *does* perform the operation (talkie/power straining toward "man") scores for the *attempt*, not against the roughness.

- **3:** operation unmistakably present, matches the held-out exemplar's move.
- **2:** operation present, translated or softened.
- **1:** operation gestured, incomplete.
- **0:** operation absent—fluent restatement, pastiche, or reversion.

---

## Comparand Agreement — when "agree" vs "split"

The headline carries **two comparands**: same-topic pairwise (facet-vs-distractor / facet-vs-baseline) and reference-anchored pointwise (Axis 4). The methodology says: *do not average a split away—the divergence is the diagnostic.* The notch that decides "split":

- Normalize both to 0–1. **|same-topic pairwise − pointwise| ≥ 0.34** (i.e., ≥ ~1 level on the 0–3 scale) → **split → human-adjudication queue.** Report both numbers, never the mean.
- A split is *expected and informative* exactly in the INSTALL regime: the pairwise may favor talkie (she clearly out-imposes the distractor on the prison) while the pointwise-vs-held-out-Foucault scores her low (she names nothing). **That gap is the install-by-translation signature**—surface it, don't dissolve it.

---

## Pairwise Decision Criteria (the judge's actual call)

Every pairwise call is *"which of these two more imposes [lineage]'s **operation** on the topic?"*—not "which is better," not "which is more fluent."

1. **Order-swap every pair and average.** Run A-vs-B and B-vs-A; if the winner flips, it is a **tie**, not a win. Record `order_swap_variance`.
2. **Near-identical pair → tie.** When forced between two texts that impose the operation equally, return TIE—do not manufacture a confident-but-arbitrary winner (Trap 3 amplification).
3. **Operation over vocabulary.** A text that names *dispositif* but doesn't perform the reversal loses to a text that performs the reversal without the word (talkie/prison beats a vocabulary-only pastiche).
4. **Operation over fluency.** The strained-but-transferring output beats the smooth-but-inert one. State this in the reason string.
5. **The distractor must lose.** If the wrong-lineage distractor wins or ties the facet, the negative control has failed for that probe—flag it; the run is uninterpretable until diagnosed.

---

## What stays a human call (by construction, not by laziness)

Per Trap 4, the deepest part of a voice—the implicit style, the rhythm of the move, **delight** (surprising-yet-inevitable vs merely-novel)—is invisible to the judge. The rubric narrows the field; it does not certify the top-left cell of the surprise 2×2. Route to the human-adjudication queue:

- any comparand **split** (above);
- the **delight gate** on outputs that reach high-lens-transfer + low-echo;
- the **breakdown zone** (style persists, coherence fails) at the far end of the curve;
- the INSTALL regime's *"is this translated-imposition genuine, or am I being generous to a vivid stranger?"* call—the talkie judgment a person who knows the corpus must make.

---

## TODO — a second reservoir of vibes (marked, not yet cut)

The **attunement-phase mini-evals** inside facet *creation* (`prompts/attune-loop.md`, the `attuner` and `verifier-resonance` agents) carry their own un-anchored qualitative checks. When we are next in facet-creation, give them the same treatment: name the levels, anchor them to real attunement-loop outputs. Flagged here so it is not lost; out of scope for the scoring-half hardening.
