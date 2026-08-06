# Ultradex Obsidian Operator

The Obsidian integration is an operator client for Ultradex. It reads current
job-search projections through the official TypeScript SDK and submits governed
commands through the same SDK. Ultradex remains the system of record,
authorization boundary, and audit source.

This delivery proves the backend loop and installs the built plugin only in a
synthetic test vault. It does not prove the native Obsidian GUI loop, deploy to
production, authorize a production mutation, or install anything in a working
vault.

## Isolated proof boundary

Run the automated runtime proof with the repository virtual environment:

```bash
.venv/bin/python -m pytest \
  tests/integration/test_obsidian_operator_runtime.py -q
```

The test uses only synthetic identifiers and content. It creates a
migration-backed temporary SQLite database, starts the real
`/opt/homebrew/bin/nats-server` with JetStream on a dynamic port from a literal
`port: 0` configuration, uses a fresh temporary store and unique durable
consumer, and calls FastAPI in-process with `httpx.ASGITransport`. It exercises
the real publisher, pull consumer, worker, executor, projection writer, lifecycle
events, and receipt issuer. It does not use Docker Compose, production
Ultradex, a shared NATS stream, port 8000, secrets, a working vault, or Obsidian.

The harness seeds one synthetic evidence reference. It also records explicit
`fresh` checkpoints for the empty applications, relationships, and outreach
projections so aggregate freshness is truthful. These are harness-only markers,
not production source positions. `opportunities.create` writes the
opportunities checkpoint from its own terminal lifecycle event.

## Fixed synthetic test vault

The only installer destination is:

```text
/Users/nate/var/obsidian-test-vaults/ultradex-operator/.obsidian/plugins/ultradex-operator
```

Prepare only the synthetic vault container, then run the fixed-path installer:

```bash
mkdir -p /Users/nate/var/obsidian-test-vaults/ultradex-operator/.obsidian/plugins
scripts/create-obsidian-test-vault.sh
```

The installer accepts no arguments or destination environment overrides. It
refuses symlinked vault, `.obsidian`, plugins, or plugin-destination components.
It builds through the repository npm workspace script, creates only the fixed
plugin directory, installs `main.js`, `manifest.json`, and `styles.css` as mode
`0644`, and verifies every installed artifact byte-for-byte with `cmp`. Existing
`data.json` and `.obsidian/community-plugins.json` are preserved.

The installer does not enable the plugin or open Obsidian. Native GUI acceptance
is a separate operator step.

## Connection and credential setup

For the later native acceptance step, use Obsidian 1.11.4 or newer:

1. Open **Settings → Ultradex Operator** in the isolated test vault.
2. Set **Ultradex base URL** to the explicitly approved isolated API origin.
   Do not use the plugin's port-8000 placeholder for this proof.
3. Save the dedicated scoped command token using **Save token**.

The connection strip displays only the configured service origin. User
information, credentials, API paths, query parameters, and fragments are never
rendered from the configured URL.

The server credential represented by that token has exactly `{read, command}`
scope and no `delegation-admin` scope. The plugin stores it under
`ultradex-api-token` in Obsidian SecretStorage. If SecretStorage is unavailable
or the token is missing, the plugin refuses network access. The token is never
written to ordinary plugin settings or a vault note.

Non-secret settings such as the base URL, refresh interval, view filters, and UI
preferences may live in plugin `data.json`. The bounded
`ultradex-command-custody-v1` journal lives separately in SecretStorage and
retains only sanitized command-custody identifiers and states. Projections,
command parameters, lifecycle payloads, receipt payloads or signatures, and
career/contact content are not persisted to vault notes or plugin data.

## Governed commands and confirmation

The command bar exposes the closed nine-command catalog:

- `sources.ingest`
- `opportunities.create`
- `opportunities.score`
- `applications.transition`
- `relationships.sync`
- `outreach.prepare`
- `outreach.approve`
- `outreach.send`
- `evidence.export`

Every submission displays its consequence, exact sanitized bound fields, and
idempotency key before confirmation. Outreach preparation and approval bind the
message commitment rather than hidden message content. Before
`outreach.approve` creates a review, the current verified projection must contain
the exact outreach ID in `pending_approval` state with the submitted commitment.
The review derives its channel from that record and rechecks the same ID,
commitment, state, and channel immediately before submission. A missing or
changed binding sends no command and directs the operator to refresh and start a
fresh review. `outreach.send` displays the outreach ID, approval contract ID,
message commitment, and channel, and requires a second explicit confirmation.

The plugin never supplies an actor override. The server derives actor identity
from the scoped credential.

## Read, freshness, and outcome semantics

Refresh reads opportunities, applications, relationships, outreach, operations,
and their freshness as one candidate snapshot:

- A complete, validated refresh replaces the prior snapshot atomically.
- A partial or schema-invalid refresh retains the prior snapshot and identifies
  the failed projection.
- An authentication failure retains prior data, marks authentication failed,
  and disables mutations.
- A network failure retains prior data, marks the view stale/offline, and
  disables mutations.
- Aggregate freshness is the oldest projection checkpoint. Any unknown, stale,
  or otherwise ambiguous freshness disables mutations.
- Clearing the cached snapshot does not clear credentials, command custody,
  vault files, or server data.

Accepted, pending, running, approval-required, refused, failed, unverifiable,
and succeeded are distinct operator states. A governed refusal remains refused
with the server reason. A failed operation remains failed. Each record separately
labels evidence as `pending`, `complete`, or `unverifiable`. If terminal evidence
cannot be read or bounded polling ends before required terminal evidence arrives,
the known approval-required, refused, failed, or succeeded outcome is preserved
and only its evidence status becomes `unverifiable`. Only an actually unknown
nonterminal or pre-handle outcome becomes governed state `unverifiable`. The
operation and correlation identifiers remain available for manual refresh, and
an exact successful refresh changes the evidence status to `complete`.

The content-free custody journal does not persist evidence bodies or evidence
status. On restart, records with an operation ID safely resume with pending
evidence; pre-handle completion-unknown records resume as unverifiable.

Obsidian `requestUrl` is not cancellable. If a submission times out before a
handle returns, the server may still have accepted it. The plugin records
`completion unknown`, retains the command name, idempotency key, correlation ID,
and actual attempt time in bounded SecretStorage custody, and prohibits
automatic or one-click resubmission. Convenience retry is unsafe and is not
available; later reconciliation requires an operation identifier or a future
server lookup contract.

Terminal receipt evidence is labeled `server-recorded`. The plugin displays the
recorded receipt hash, key ID, signed payload, and audit reference when
available, but local signature verification is `unavailable` until Ultradex
publishes a trusted verification-key registry. Receipt presence is not presented
as cryptographic verification.

## Production gates

This code and synthetic-vault proof do not authorize production use. Production
requires all of the following separate gates:

1. approval and merge of the applicable Forgejo pull request;
2. provisioning of the dedicated `{read, command}` credential;
3. deployment of the approved Ultradex version and runtime configuration;
4. an explicitly approved installation in the working vault; and
5. separate authorization for the intended production mutation.

No gate above is implied by a successful automated test, plugin build, or
synthetic test-vault installation.
