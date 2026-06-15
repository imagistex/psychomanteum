---
name: psychomanteum-attune
description: Iterative refinement loop—three verifiers critique in parallel, attuner revises, loop until pass or max iterations
args:
  - name: continue
    description: Continue iterating past max_iterations (use after manual halt)
    required: false
---

# Psychomanteum—Attune

Orchestrates the iterative refinement loop. Each iteration: three verifiers (`verifier-density`, `verifier-resonance`, `verifier-strangeness`) run in parallel; `attuner` reads their reports and produces the next draft. Loop until all verifiers pass, or `max_iterations` reached, or user halts.

The verb does dual work: **gradient descent** (verifiers as loss function, attuner as optimizer) AND **atmospheric attunement** (Kathleen Stewart—the perceptual settling into a charged register, iteration by iteration). Both readings drive the loop.

## First: Read Reference Files

1. `.psychomanteum-config.md`
2. `.psychomanteum-state.json`—must be phase `inscribed` (or `attuning` if continuing)
3. `${CLAUDE_PLUGIN_ROOT}/prompts/attune-loop.md`—the loop protocol
4. `${CLAUDE_PLUGIN_ROOT}/templates/attune-report.json`—schema for verifier reports

## Your Task

### Step 1: Validate State and Iteration Counter

Read `.psychomanteum-state.json`. Valid starting phases:
- `inscribed` (first run; iteration 0 draft is from cipher)
- `attuning` (resuming an in-flight loop)

If `--continue` flag is provided and current phase is `attuning_paused`, advance past the prior halt.

Read `attune_iteration` and `max_attune_iterations` from state.

### Step 2: Prepare Working Directory

```bash
mkdir -p attune
```

For each new iteration: `mkdir -p attune/iter-<N>`.

### Step 3: The Loop

```
while attune_iteration < max_attune_iterations:
  attune_iteration += 1
  mkdir attune/iter-<attune_iteration>

  current_draft = drafts/<facet-name>-iter<attune_iteration - 1>.md

  # Step 3a: Run three verifiers in parallel
  parallel spawn:
    verifier-density   → attune/iter-<N>/density-report.json
    verifier-resonance → attune/iter-<N>/resonance-report.json
    verifier-strangeness → attune/iter-<N>/strangeness-report.json

  wait for all three

  # Step 3b: Snapshot draft for trajectory inspection
  cp current_draft → attune/iter-<N>/draft-snapshot.md

  # Step 3c: Check verdicts
  if all three verifiers verdict == "pass":
    break  # converged

  # Step 3d: Check for halt recommendations
  if any verifier has halt_recommended == true:
    log halt reason; present to user at gate; break

  # Step 3e: Run attuner to produce next draft
  spawn attuner:
    inputs: current_draft, three reports, cipher notes, iteration number
    output: drafts/<facet-name>-iter<N+1>.md + attune/iter-<N+1>/attuner-notes.json

  wait

  # Step 3f: Check attuner's convergence_signal
  if attuner.convergence_signal == "stuck" or "halt_corpus_bottleneck":
    log; present at gate; break

# Loop done (either by pass, halt, or max_iterations)
```

### Step 4: Generate Loop Summary

Write `attune/summary.md`:

```markdown
# Attune Summary—{{FACET_NAME}}

**Iterations run:** {{final_iter}}
**Termination reason:** {{converged | max_iterations | halted_by_verifier | halted_by_attuner | user_halt}}

## Trajectory

| Iter | Density | Resonance | Strangeness | Attuner Convergence |
|---|---|---|---|---|
| 0 | (cipher) | (cipher) | (cipher) | (initial) |
| 1 | pass/fail (signal: 0.74) | pass/fail (score: 0.81) | pass/fail (3 high-sev) | improving |
| 2 | ... | ... | ... | ... |

## Final Verdicts

- **Density**: {{final_density_verdict}} (signal: {{signal}})
- **Resonance**: {{final_resonance_verdict}} (score: {{score}})
- **Strangeness**: {{final_strangeness_verdict}} ({{high_sev_count}} high-severity findings)

## Final Draft

`drafts/{{facet-name}}-iter{{final_iter}}.md`

## Status

{{converged | tuning_incomplete | halted_with_reason}}
```

### Step 5: Present Final Gate to User

Display the summary and present options:

1. **Accept**—proceed to `/psychomanteum-bind` with the latest draft
2. **Continue iterating**—run more iterations (`--continue` flag)
3. **Roll back**—select an earlier iteration's draft as the one to bind (sometimes iteration 2 reads better than iteration 3 if the attuner over-corrected)
4. **Abort**—return to distill or even gather to fix upstream issues; the loop has hit a ceiling

### Step 6: On Accept

- Update `.psychomanteum-state.json`: phase → `attuned`, `final_draft_iter: <N>`
- Suggest: `/psychomanteum-bind`

### Step 7: On Continue / Rollback / Abort

- **Continue:** bump `max_iterations` if needed; loop more
- **Rollback:** copy `drafts/<facet-name>-iter<chosen>.md` → `drafts/<facet-name>-final.md`; mark phase `attuned`
- **Abort:** set phase to `inscribed` or earlier per user choice; user runs other commands

## Error Handling

- Verifier fails to produce a report: skip that verifier this iteration; continue with the two that succeeded; warn user
- Attuner fails to produce a revision: stop loop; present partial trajectory to user
- Validation hook blocks attuner's write: surface schema violation; the attuner should not produce schema-violating output, treat as bug
- Loop oscillates (each iteration fails differently): the convergence_signal will report `oscillating` from the attuner; halt and present to user