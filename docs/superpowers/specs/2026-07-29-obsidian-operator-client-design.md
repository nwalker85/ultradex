# Ultradex Obsidian Operator Client Design

**Status:** Approved for implementation on 2026-07-29  
**Product:** Career Command Center  
**Decision:** Obsidian is an interactive Ultradex operator client, including
governed mutations.

## Outcome

An operator can open Obsidian, inspect current job-search projections, submit
bounded career commands, and follow each command through accepted, approval,
refused, failed, unverifiable, or succeeded state without leaving the vault.
Ultradex remains the system of record, authorization boundary, and audit source.

The same-day proof target is an isolated local Ultradex runtime, sanitized data,
and a separate Obsidian test vault. Production deployment and working-vault
installation are separate, explicitly approved rollout steps.

## Invariants

1. The plugin uses the official TypeScript Ultradex SDK for every API call. It
   does not embed REST paths, GraphQL documents, or command payload rules.
2. The server derives actor identity. The client never sends an actor override.
3. A plugin credential has `read` and `command` scopes but not
   `delegation-admin`.
4. Every mutation requires an idempotency key and returns a `ContractHandleV1`.
5. Governed outcomes remain first-class:
   - authentication and validation errors are transport errors;
   - accepted intent returns a handle;
   - refused, failed, and unverifiable terminal states are not thrown away or
     relabeled as generic failures;
   - operation and correlation IDs remain visible and copyable.
6. Outreach approval binds the exact currently projected `pending_approval`
   outreach ID, message commitment, and derived channel, then rechecks that same
   binding immediately before submission. Missing or changed bindings fail
   closed without an SDK request. The plugin never invents or weakens that
   mandate.
7. The plugin stores no API token in ordinary plugin settings or vault notes.
   Use Obsidian SecretStorage when available and fail closed otherwise. The only
   mutation-state persistence exception is the bounded, versioned minimal
   command-custody journal defined below; it also lives in SecretStorage, under
   a stable ID distinct from the token, and never in plugin data or vault notes.
8. Refresh swaps one validated aggregate snapshot atomically. An error keeps the
   last known snapshot, marks it stale, and prevents ambiguous mutation state.
9. Agent tests and fixtures contain only synthetic data. Real career, contact,
   résumé, mailbox, and message contents stay outside agent prompts and test
   artifacts.
10. GitHub is a passive mirror. Forgejo branches, PRs, Actions, and Snotra are the
    delivery gates.

## System boundary

```text
Obsidian operator view
        |
        | Ultradex TypeScript SDK only
        v
Read transport                         Command transport
GraphQL projections                    REST command boundary
  opportunities                          Idempotency-Key
  applications                           X-Correlation-Id
  relationships                          X-Delegation-Id (optional)
  outreach                               parameters-only body
  operations/events                            |
        |                                      v
        +--------------------------- ContractHandleV1
                                               |
                                               v
                                  operation + lifecycle events
                                               |
                            approval / refusal / receipt evidence
```

## Official TypeScript SDK

The package lives at `sdk/typescript` and is independently buildable. Its public
surface is typed and transport-agnostic:

```ts
export interface UltradexTransport {
  request<T>(request: UltradexRequest): Promise<T>;
}

export interface UltradexReadClient {
  getHealth(): Promise<HealthStatus>;
  getReadiness(): Promise<ReadinessStatus>;
  listOpportunities(input?: OpportunityListInput): Promise<OpportunityPage>;
  listApplications(input?: ApplicationListInput): Promise<ApplicationPage>;
  listRelationships(input?: RelationshipListInput): Promise<RelationshipPage>;
  listOutreach(input?: OutreachListInput): Promise<OutreachPage>;
  listOperations(input?: OperationListInput): Promise<Operation[]>;
  getOperation(operationId: string): Promise<Operation | null>;
  getOperationEvents(
    operationId: string,
    input?: EventPageInput,
  ): Promise<OperationEvent[]>;
  getApproval(approvalId: string): Promise<ApprovalEvidence | null>;
  getExecutionReceipt(
    operationId: string,
  ): Promise<ExecutionReceiptEvidence | null>;
}

export interface UltradexCommandClient {
  submitJobSearchCommand(
    command: JobSearchCommandName,
    parameters: JobSearchCommandParameters,
    context: CommandContext,
  ): Promise<ContractHandle>;
}
```

The SDK owns:

- bearer, idempotency, correlation, and optional delegation headers;
- typed `/health` and `/health/ready` checks for the connection strip;
- canonical GraphQL documents and response validation;
- the closed nine-command catalog and parameter unions;
- `ContractHandle`, projection, operation, event, and governed-state types;
- contract-backed approval evidence and execution-receipt reads;
- mapping HTTP/auth/schema failures to structured client errors;
- preserving accepted/refused/failed handles returned by the server.

The Obsidian adapter supplies `requestUrl`; browser or Node consumers can supply
another transport without changing SDK behavior.

## Credential model

Add a distinct server credential pair:

- `ULTRADEX_COMMAND_TOKEN`
- `ULTRADEX_COMMAND_ID`

It authenticates with `{read, command}` and no delegation administration.
Existing read-only and full operator credentials remain compatible. No source
default is permitted. Compose wires the new variables from its environment.

The plugin stores the token by a stable secret key and stores only non-secret
configuration in plugin data:

- Ultradex base URL;
- refresh interval;
- active view filters;
- SecretStorage key reference;
- sanitized UI preferences.

If SecretStorage is unavailable, the plugin shows setup instructions and refuses
network access instead of persisting a plaintext token.

SecretStorage also holds a separate
`ultradex-command-custody-v1` journal. Its version-1 envelope retains at most 50
recent entries and allowlists only command name, idempotency and correlation
IDs, actual network-attempt time, returned contract/operation/approval IDs when
known, and the current custody/outcome state. It never stores command
parameters, message content, message commitment, raw errors, reason text,
lifecycle payloads, receipt payloads or signatures, contact/employer data, or
the API token. Malformed, wrong-version, oversized, or extra-field data is
ignored.

## Operator experience

The plugin registers one deferred `ItemView` and four commands:

- **Ultradex: Open operator console**
- **Ultradex: Refresh projections**
- **Ultradex: Retry authentication**
- **Ultradex: Clear cached snapshot**

The native view contains:

1. **Connection strip** — sanitized configured service origin, authentication
   state, last successful refresh, aggregate freshness, and stale/offline
   warning. URL user information, credentials, paths, queries, and fragments
   are not rendered.
2. **Command bar** — explicit forms for safe local commands. Submission shows
   the idempotency key before confirmation.
3. **Pipeline panels** — opportunities, applications, relationships, and
   outreach. Initial rendering favors compact tables and status filters.
4. **Operations rail** — recent handles and lifecycle events, with copyable
   operation and correlation IDs.
5. **Governed outcome card** — accepted, pending, approval-required, refused,
   failed, unverifiable, or succeeded states use distinct labels and retain the
   server reason code. A separate closed evidence label (`pending`, `complete`,
   or `unverifiable`) prevents incomplete reads from overwriting known terminal
   outcomes. Terminal cards resolve the recorded receipt by operation ID;
   outreach cards resolve their exact approval contract.

The receipt card shows the recorded receipt hash, signature key ID, signed
payload, and audit reference. It must distinguish `server-recorded` from
`signature-verified`. Until Ultradex exposes a trusted verification-key registry,
the plugin must say that local signature verification is unavailable; receipt
presence alone is not cryptographic verification.

Optional Bases or Dataview integration may project sanitized notes later. It is
not a dependency for command execution or operational truth.

## Mutation interaction

The first release exposes all nine SDK command methods but uses consequence-aware
UI:

- low-consequence local transitions may submit from a confirmation form;
- outreach preparation shows only the message commitment, never hidden content;
- outreach approval displays the exact bound IDs and commitment;
- outreach send requires the approval contract ID and a second explicit
  confirmation;
- unbound source, scoring, relationship, or sending adapters surface their
  governed refusal rather than pretending the feature is unavailable locally.

Immediately before the SDK network call, the plugin writes a minimal
`submitting` custody entry with the actual attempt time. After submission it
updates custody with the returned handle, refreshes the operation, and polls
bounded lifecycle pages until a terminal state has its required approval and
receipt evidence or the user-visible timeout. A timeout or read failure changes
evidence status to `unverifiable` while preserving any known
approval-required, refused, failed, or succeeded outcome and the operation ID
for later refresh. Only a genuinely unknown nonterminal or pre-handle outcome
uses governed state `unverifiable`. A terminal operation missing required
evidence continues bounded polling and remains manually refreshable if evidence
is still incomplete.

On restart, a `submitting` entry without an operation ID restores as
`completion unknown`, `unverifiable`, and non-resubmittable. The content-free
journal does not persist evidence status: records with an operation ID safely
restore with pending evidence, while pre-handle records restore as
unverifiable. Other entries restore without their non-persistent
form/projection/evidence bodies. Exact operation, lifecycle, approval, and
receipt evidence is reacquired through the SDK by operation ID only after the
operator view opens. Closing a view
permanently stops its controller/tracker instance: an already in-flight command
may finish only the minimal custody update and cannot start timers, reads, or
late DOM updates.

Obsidian's native `requestUrl` cannot be cancelled. If a command request times
out before a handle is returned, the transport marks
`requestMayHaveCompleted: true`. The controller must retain the idempotency key,
correlation ID, command, and submitted-at time, render `completion unknown`, and
prohibit automatic or one-click resubmission. Until Ultradex exposes lookup by
idempotency/correlation, this state cannot be reconciled to an operation ID and
must remain visibly unverifiable.

## Snapshot and failure semantics

`ProjectionStore.refresh()` fetches all required pages into a candidate snapshot,
validates each response, and swaps the store only when the complete candidate is
valid. Concurrent refreshes collapse into one in-flight request.

- Authentication failure: clear no data; mark auth failed; disable mutations.
- Network failure: retain last snapshot; mark stale/offline; disable mutations.
- Partial/schema failure: retain last snapshot; show which projection failed.
- Successful refresh: atomically swap; derive aggregate freshness from the oldest
  projection checkpoint.
- Manual clear: remove only the projection snapshot cache, never custody,
  SecretStorage credentials, vault files, or server data.

## Testing

Tests name the production break they catch and exercise real SDK/store behavior:

- SDK request contract tests use a recording transport with literal expected
  paths, headers, GraphQL variables, and complete responses.
- SDK schema tests reject incomplete or malformed projection and handle payloads.
- Backend and SDK tests prove approval evidence is resolved by its exact approval
  ID and a receipt is resolved by its unique operation ID, under `read` scope.
- Auth tests prove the command token can read and command but cannot administer
  delegation.
- Store tests prove partial refresh never replaces a good snapshot.
- Mutation-controller tests prove refused/unverifiable handles remain visible and
  polling never performs a second submission.
- Custody tests prove the pre-network write, actual attempt timestamp, strict
  allowlist and bounds, malformed-data rejection, restart recovery, deferred
  evidence reacquisition, and snapshot-clear separation.
- DOM tests drive all nine native forms, exact confirmation bindings, actionable
  RFC3339/sha256 validation, refresh single-flight state, lifecycle ID copy,
  focus restoration, and live announcements.
- UI tests render the real view/controller against synthetic SDK data; mocks stop
  at Obsidian or network boundaries.
- An isolated integration test runs one synthetic
  `opportunities.create` command through API, JetStream, worker, projection,
  lifecycle event, and signed receipt.

## Rollout

1. Restore JS-U03 through a canonical Forgejo PR.
2. Stack approval/receipt reads, the TypeScript SDK, and scoped credential
   changes on JS-U03.
3. Stack the Obsidian plugin on the SDK branch.
4. Build and load into a separate test vault.
5. Validate a sanitized read and mutation end to end.
6. Present PRs, CI/Snotra evidence, test-vault path, and operator instructions.
7. Await per-PR merge approval and a separate production rollout decision.

## References

- [Obsidian plugin build guide](https://docs.obsidian.md/Plugins/Getting%20started/Build%20a%20plugin)
- [Obsidian SecretStorage guide](https://docs.obsidian.md/plugins/guides/secret-storage)
- [Obsidian deferred views guide](https://docs.obsidian.md/plugins/guides/defer-views)
- [Obsidian plugin load-time guide](https://docs.obsidian.md/plugins/guides/load-time)
- [Obsidian Bases view guide](https://docs.obsidian.md/plugins/guides/bases-view)
