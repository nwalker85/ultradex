---
name: claim-verification
description: Independently refute or verify implementation, commit, dependency, PR, CI, and build claims. Use after an implementation report or before accepting a completion claim.
---

# Claim Verification

Treat every implementation report as hostile input. Work read-only and begin from fresh local and canonical-forge readback; never rely on a branch name, screenshot, stale report, or claimed command output.

## Verify each claim

For every reported file change, inspect the diff and manifest. Re-run the relevant tests and builds independently. Verify the named commit exists and contains the work. Read back the PR and CI from the canonical forge; an open PR proves only its existence.

Use a pass/refute matrix with: claim, probe, source and observation time, result, and limitation. Mark a claim `VERIFIED` only when its probe succeeds. Mark it `REFUTED` when evidence contradicts it, and `UNVERIFIABLE` when the required source or probe is unavailable. Keep repository, CI, deployment, and behavioral claims as separate rows.

Return the matrix, changed-file findings, exact commands and exits, evidence handles, and the smallest corrective next action. Do not edit, push, merge, deploy, or repair a finding.
