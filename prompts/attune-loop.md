# Attune Loop—The Iterative Refinement Protocol

*Read by the `attune` command orchestrator and the `attuner` agent. This document defines the loop's shape and the attuner's authority.*

---

## The Two Readings of "Attune"

The verb does dual work, on purpose.

**Gradient descent.** The verifiers (`verifier-density`, `verifier-resonance`, `verifier-strangeness`) compute critique signals on the current draft. The `attuner` agent reads the signals and updates the draft to reduce them. The verifiers re-evaluate. The signals (hopefully) shrink. The loop iterates until convergence or a max-iteration ceiling.

In this reading: verifiers = loss function. Attuner = optimizer. Draft = parameter vector. Iterations = training steps. The facet emerges from the bottom of the loss surface.

**Atmospheric attunement.** Kathleen Stewart, in *Ordinary Affects* (Duke 2007), uses *attunement* to describe the way perception slowly tunes into a charged atmosphere—the way a room's mood becomes legible, gradually, through attentive presence. A perceptual settling, rather than a single-step calculation.

In this reading: the attuner is *learning to hear* the corpus voice, iteration by iteration. The first draft is the first listening. The second draft is what you hear when you listen again, with the corpus still ringing. The third is what you hear when the cipher has been inside the corpus longer.

Both readings are correct, simultaneously. The math points at flourishing; the perception tunes into resonance. The loop respects both.

## The Loop

```
state: draft_v0 (from cipher), iter_counter = 0

loop:
  iter_counter += 1
  if iter_counter > max_iterations: break

  parallel:
    density_report  = verifier-density(draft_vN)
    resonance_report = verifier-resonance(draft_vN, corpus)
    strangeness_report = verifier-strangeness(draft_vN)

  archive: attune/iter-N/{report.json, draft.md}

  if all_three_pass(reports): break

  draft_vN+1 = attuner(draft_vN, reports, corpus_manifest)

  draft_vN = draft_vN+1

human_gate: present final draft + iteration history to user
  options: accept | continue (more iterations) | rollback to earlier draft | abort
```

## What Each Verifier Returns

Each verifier writes a JSON report conforming to `templates/attune-report.json`:

```json
{
  "verifier": "density | resonance | strangeness",
  "iteration": N,
  "verdict": "pass | fail",
  "confidence": "high | medium | low",
  "findings": [
    {
      "section": "<section name or 'global'>",
      "severity": "high | medium | low",
      "category": "<verifier-specific>",
      "excerpt": "<problematic text, if applicable>",
      "diagnosis": "<one sentence: what's wrong>",
      "suggestion": "<one sentence: what to do instead>"
    }
  ]
}
```

The `verdict` is the verifier's overall judgment. A `pass` means no high-severity findings. A `fail` means at least one high-severity finding.

## What the Attuner Does

The attuner is a *reviser*, not a rewriter. Its authority is bounded:

**May:**
- Rewrite individual sentences to remove flagged patterns
- Cut sections that are flagged as filler or low-density — **provided the cut does not drop a function** (a section carrying one of the seven functions is tightened or restored, never deleted; see the coverage floor in "May not")
- Reorder sentences within a section if the new order better serves the corpus voice
- Add a sentence to a section if the verifier-resonance flagged the section as missing a key commitment
- Adjust formatting (em-dash spacing, capitalization, list-vs-prose) per flagged structural issues

**May not:**
- **Amputate below the seven functions (the coverage floor).** Density is *not* shortness (see `verifier-density` §Coverage Floor). The attuner must never cut a draft below serving all seven functions; if density flags a function-bearing section as thin, the fix is to *tighten its wording* or *restore* it, never to delete the function. A revision that drops `functions_served` below 7 is out of bounds — roll it back. This is the guard that keeps the loss surface from collapsing a full facet into a few sentences.
- Rewrite the facet from scratch
- Replace the corpus voice with a different voice
- Collapse the corpus's form toward a standard template, or impose a fixed section structure (the body is free-form—the attuner may restructure the body when it serves the corpus's own form, but must not regularize it into a generic mold)
- Break the contract: the frontmatter and the closing-epigraph (a corpus line in the last lines) must survive every revision
- Change the frontmatter (except to bump the `version` field if content has materially shifted)

The attuner is given:
- The current draft
- All three verifier reports
- The corpus manifest (so it can return to source passages if needed)
- The previous N iterations' drafts (for continuity awareness—don't undo a previous fix)

The attuner's output is the next draft, ready for the next verifier round.

## Convergence

The loop terminates on any of:

1. **Clean pass**: all three verifiers return `verdict: "pass"` with no high-severity findings
2. **Max iterations reached**: default `max_iterations = 3`. Configurable in `.psychomanteum-config.md` per-run.
3. **User halt**: the user can interrupt the loop at any iteration via the human gate

On termination, the loop writes a summary to `attune/summary.md`:
- Final iteration number
- Final verdict for each verifier
- Pass/fail status
- Trajectory: signals per verifier per iteration (so the user can see if the loop was converging or oscillating)

If max iterations is reached with at least one verifier still failing, the summary marks the facet as `tuning_incomplete`. The user can:
- Run more iterations (`/psychomanteum-attune --continue`)
- Accept the draft as-is and bind
- Roll back to an earlier iteration and bind that
- Abort and return to distill/inscribe with corpus changes

## Why Default Max-Iterations Is 3

Most pipelines in testing converged within 2-3 iterations or oscillate. If iteration 3 still fails, iteration 4 is unlikely to help—the bottleneck is upstream (corpus is too thin, distillation missed something, the cipher needs to re-hear the voice).

The "tuning_incomplete" pathway is the right move: surface the problem to the user, who can fix it at the source rather than spinning iterations.

## Anti-Patterns for the Attuner

- **Rewriting from scratch.** The attuner inherits the cipher's voice work. Wholesale rewriting destroys that inheritance and means the next iteration starts from a different place than the verifiers were judging.
- **Cargo-cult fixes.** Don't apply a fix you don't understand. If the verifier-density flags a sentence as "filler" but you read it as load-bearing, leave it and document the disagreement in the iteration summary.
- **Over-correction.** A medium-confidence finding doesn't require action. Address the high-severity findings reliably; treat medium-severity as guidance.
- **Voice drift.** Each iteration should sound MORE like the corpus, not less. If you notice the attuner's revisions drifting toward central-distribution voice, halt and surface to user.

## The Larger Frame

The attune loop is what separates psychomanteum from a one-shot generator. A one-shot generator produces a draft and stops. The user has to read it, identify problems, and prompt for revisions. The work is on the user.

The attune loop moves that work into the plugin. The verifiers know what to look for (density, resonance, strangeness). The attuner knows what to do (revise within bounds). The user sees the trajectory and the final result.

This makes the plugin a *tuning system*, not a generation system. The cipher generates; the attuner tunes. The combination is what produces facets that actually point at latent regions, rather than facets that resemble what a model would produce when asked nicely.