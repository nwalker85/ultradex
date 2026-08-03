# Job Search Platform Execution Status — 2026-08-03

Supersedes the "Execution status (2026-07-22)" table in
`2026-07-22-job-search-platform-execution-manifest.md`. Unit definitions,
dependency boundaries, and orchestration rules in that manifest remain in
force. This update reconciles the table against verified branch, PR, and
repository state after the Forgejo migration and the 2026-07-29 Obsidian
operator client design approval.

## Delivery-plane note

Delivery moved from GitHub to Forgejo mid-program. JS-U01 and JS-U02 merged as
GitHub squashes (`d068c73`, `17e02b9`) before the move; `origin/main` and
`forgejo/main` are verified identical at `5695a04`. All open review now lives
on Forgejo (`nate/ultradex`). GitHub PR #4 (governed command runtime) is
superseded by Forgejo PR #3 and should be closed, not merged.

## Execution status (2026-08-03)

| ID | State | Evidence |
|---|---|---|
| JS-C01 | **merged** | `ravenhelm-contracts` Forgejo PRs #18 (job-search observability contracts), #22 (approval envelope v1), #23 (workspace initialization); packages published via #19/#20. |
| JS-O01 | **PR open** | `ravenhelm-observability-py` PR #6 "canonical job-search observability context" awaits review and explicit approval. |
| JS-G01 | not started | `ravenhelm-observability-go` repository does not exist; requires repo-lifecycle gates and explicit repo-creation approval. |
| JS-U01 | **merged** | Squash `d068c73` in main. Branch `feat/jobsearch-observability-foundation` retains only docs-record deltas (~10 lines); locked worktree retirable after confirmation. |
| JS-U02 | **merged** | Squash `17e02b9` in main. Branch content fully contained in main (only the later policy workflow differs); locked worktree retirable after confirmation. |
| JS-U03 | **PR open** | Forgejo PR #3 (`feat/jobsearch-governed-commands-forgejo`), base of the stacked Obsidian lane. |
| OB-U01 | **PR open** | Forgejo PR #4 — official TypeScript SDK (`sdk/typescript`), stacked on JS-U03. Added by the 2026-07-29 operator client design; TS SDK is justified by the Obsidian client under the design's "TypeScript SDK only with a web client" rule. |
| OB-U02 | **PR open** | Forgejo PR #5 — governed Obsidian operator plugin, stacked on OB-U01. The three `fix/obsidian-*` branches (167911e, 5aacbbf, dd05ddd) are verified ALREADY ABSORBED into the PR #5 branch — identical `git patch-id` to commits cherry-picked onto the plugin branch one minute after authoring. Delete them; do not merge them. |
| OB-U03 | branch, no PR | `feat/obsidian-onboarding` implements the 2026-07-30 onboarding workflow design; needs its own PR once OB-U02 lands. |
| JS-U04 | not started | Source adapters (Gmail, LinkedIn-safe, Dex, manual/web). `docs/yc-job-feed-watch-design` (GitHub-only branch) is related design intake. |
| JS-U05 | not started | Blocked on JS-G01. |
| JS-U06 | not started | Blocked on JS-U03 merge. |
| JS-U07 | not started | Blocked on JS-O01 merge and JS-U03 merge. |
| JS-U08 | not started | Blocked on JS-U07. |

## Out-of-manifest state

| Item | State | Disposition |
|---|---|---|
| CI meta-lane | Forgejo PR #1 (sovereign CI gate, profile B) and PR #6 (Snotra AI review) open | Land before the JS-U03 chain so subsequent merges get CI and advisory review. Snotra never gates its own CI; a failed Snotra run with no comments means the job died, not zero findings. |
| Legacy rescue | `rescue/ultradex-main-phase1-20260729` (066da60) extends pre-redesign `core/` contact-intelligence | Preserved via WIP PR for visibility. Not mergeable as-is: it bypasses the governed command surface. Fold salvageable enrichment logic into a JS-U04-adjacent unit or close after salvage. |
| `fix/docker-local-contracts` | Same tip as PR #5 branch (7d76558) | Not a distinct fix lane today; either retire the branch or use it for actual docker-contract work. |

## Review blockers (2026-08-03 adversarial verification)

Independent read-only review of the #3→#4→#5 chain found these blockers before
any merge:

1. **CRITICAL — no CI ever ran on PR #4/#5.** `.forgejo/workflows/policy.yml`
   triggers only on `pull_request: branches: [main]`; stacked bases never fire
   it. ~18,300 diff lines have zero gate evidence.
2. **CRITICAL — the policy gate can never pass.** It requires
   `.forgejo/workflows/ci.yml`, which does not exist on main or any branch, so
   `forgejo-policy` fails deterministically on every PR into main (PR #3's red
   CI is this pre-existing defect, not the PR). A real `ci.yml` must run the
   Python and Node suites, building `sdk/typescript` before the plugin tests.
3. **HIGH — `ravenhelm-contracts==0.2.0` resolves from no configured index**;
   clean installs and the Docker image build fail. Publish to the Forgejo
   package registry (or vendor) and configure the index in Dockerfile/CI.
4. **HIGH (PR #3) — delegation validation is opt-in via client-supplied
   `X-Delegation-Id`** (`core/jobsearch_commands.py:272`, header optional at
   `api/routes/v2/jobsearch_commands.py:45-48`); omitting the header bypasses
   the authority check. Decide intended semantics for non-delegated commands.
5. **HIGH (PR #3) — authority refusals are never persisted**: `PermissionError`
   raises before `create_operation`, so refused intent leaves no durable
   record, violating "the Gateway is the source of truth for accepted or
   refused intent."
6. **HIGH (PR #4) — SDK surface deviates from the approved client design**:
   spec'd `submitJobSearchCommand` does not exist (`submit()` instead) and
   `commands.test.ts:66` asserts its absence. Reconcile spec or SDK.
7. **HIGH (PR #4×#3) — governed 403 `command_authority_refused` is relabeled**
   as a thrown generic `UltradexAuthError`, violating invariant 5 (refusals are
   not relabeled as generic failures).
8. **MEDIUM (PR #5) — the implementation PR amends the approved spec it is
   judged against** (invariants 6/7, custody-journal persistence exception,
   outcome-card semantics). Edits are tightening, but require their own
   explicit approval.

Verified strengths: outreach send enforces approval binding on exact ID,
commitment, channel, and expiry on both sides; actor identity is
server-derived; idempotency key is required; the plugin is SDK-only, makes no
vault writes, and fails closed without SecretStorage (37/37 SDK and 109/109
plugin tests pass locally once the SDK is built). Python suites remain unrun
by anyone — blocked on item 3.

## Merge order (pending explicit per-PR approval)

1. Fix blockers 1–3 (CI trigger scope, missing `ci.yml`, contracts publish) —
   repo-level, independent of the chain.
2. Forgejo PR #6 (Snotra review), PR #1 (CI gate) — meta-lane, gives the chain
   review coverage.
3. `ravenhelm-observability-py` PR #6 (JS-O01) — independent.
4. Forgejo PR #3 (JS-U03, after blockers 4–5) → retarget PR #4 (after 6–7) →
   merge → retarget PR #5 (after 8), re-verifying each after its parent lands.
5. Delete `fix/obsidian-custody-semantics`, `fix/obsidian-draft-preservation`,
   `fix/obsidian-tracker-proof-gaps`, `fix/docker-local-contracts` — absorbed.
6. OB-U03 onboarding PR after OB-U02.

No PR merges without explicit approval of that specific PR.
