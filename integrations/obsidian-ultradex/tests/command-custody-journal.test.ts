import { describe, expect, test } from "vitest";

import {
  COMMAND_CUSTODY_SECRET_ID,
  CommandCustodyJournal,
  type CommandCustodyJournalEntry,
} from "../src/mutations/command-custody-journal.js";
import type { ObsidianSecretStorage } from "../src/settings.js";

class MemorySecretStorage implements ObsidianSecretStorage {
  readonly writes: Array<{
    readonly id: string;
    readonly secret: string;
  }> = [];

  constructor(private value: string | null = null) {}

  getSecret(id: string): string | null {
    return id === COMMAND_CUSTODY_SECRET_ID ? this.value : null;
  }

  setSecret(id: string, secret: string): void {
    this.value = secret;
    this.writes.push({ id, secret });
  }
}

function custodyEntry(
  sequence: number,
  overrides: Partial<CommandCustodyJournalEntry> = {},
): CommandCustodyJournalEntry {
  return {
    commandName: "outreach.send",
    idempotencyKey: `idempotency-journal-synthetic-${sequence}`,
    correlationId: `correlation-journal-synthetic-${sequence}`,
    submittedAt: "2026-07-29T16:00:00.000Z",
    contractId: `contract-journal-synthetic-${sequence}`,
    operationId: `operation-journal-synthetic-${sequence}`,
    approvalContractId: `approval-journal-synthetic-${sequence}`,
    state: "running",
    ...overrides,
  };
}

const PROOF_ID_STATES = [
  "accepted",
  "pending",
  "running",
  "approval-required",
  "refused",
  "failed",
  "succeeded",
] as const;

describe("CommandCustodyJournal", () => {
  test("writes only the versioned allowlisted custody fields to its stable SecretStorage ID and bounds retained entries", () => {
    const storage = new MemorySecretStorage();
    const journal = new CommandCustodyJournal(storage, {
      maxEntries: 2,
    });

    journal.upsert(custodyEntry(1));
    journal.upsert(custodyEntry(2));
    journal.upsert(custodyEntry(3));

    expect(storage.writes.at(-1)?.id).toBe(
      "ultradex-command-custody-v1",
    );
    expect(JSON.parse(storage.writes.at(-1)?.secret ?? "{}")).toEqual({
      version: 1,
      entries: [custodyEntry(3), custodyEntry(2)],
    });
    const serialized = storage.writes.at(-1)?.secret ?? "";
    expect(serialized).not.toContain("parameters");
    expect(serialized).not.toContain("messageCommitment");
    expect(serialized).not.toContain("payload");
    expect(serialized).not.toContain("signature");
    expect(serialized).not.toContain("reason");
    expect(serialized).not.toContain("token");
  });

  test("removes custody by idempotency key and rewrites only the bounded versioned envelope", () => {
    const storage = new MemorySecretStorage();
    const journal = new CommandCustodyJournal(storage, {
      maxEntries: 2,
    });
    journal.upsert(custodyEntry(1));
    journal.upsert(custodyEntry(2));

    journal.remove("idempotency-journal-synthetic-1");
    journal.remove("idempotency-journal-synthetic-1");

    expect(JSON.parse(storage.writes.at(-1)?.secret ?? "{}")).toEqual({
      version: 1,
      entries: [custodyEntry(2)],
    });
    expect(journal.load()).toEqual([custodyEntry(2)]);
  });

  test("ignores malformed, wrong-version, oversized, and extra-field journal data", () => {
    const examples = [
      "{not-json",
      JSON.stringify({ version: 2, entries: [] }),
      JSON.stringify({
        version: 1,
        entries: [{ ...custodyEntry(1), messageCommitment: "forbidden" }],
      }),
      JSON.stringify({
        version: 1,
        entries: Array.from({ length: 3 }, (_, index) =>
          custodyEntry(index + 1),
        ),
      }),
    ];

    expect(
      examples.map((value) =>
        new CommandCustodyJournal(
          new MemorySecretStorage(value),
          { maxEntries: 2 },
        ).load(),
      ),
    ).toEqual([[], [], [], []]);
  });

  test.each(PROOF_ID_STATES)(
    "rejects %s custody when either proof identifier is missing",
    (state) => {
      const impossibleEntries = [
        custodyEntry(1, {
          state,
          contractId: null,
          operationId: "operation-journal-synthetic-001",
        }),
        custodyEntry(2, {
          state,
          contractId: "contract-journal-synthetic-002",
          operationId: null,
        }),
        custodyEntry(3, {
          state,
          contractId: null,
          operationId: null,
        }),
      ];

      for (const entry of impossibleEntries) {
        const persisted = new MemorySecretStorage(
          JSON.stringify({ version: 1, entries: [entry] }),
        );
        expect(new CommandCustodyJournal(persisted).load()).toEqual([]);

        const writable = new MemorySecretStorage();
        expect(() =>
          new CommandCustodyJournal(writable).upsert(entry),
        ).toThrow("Invalid command custody entry");
        expect(writable.writes).toEqual([]);
      }
    },
  );

  test("accepts submitting custody only before contract and operation identifiers exist", () => {
    const valid = custodyEntry(1, {
      contractId: null,
      operationId: null,
      state: "submitting",
    });
    const journal = new CommandCustodyJournal(
      new MemorySecretStorage(
        JSON.stringify({ version: 1, entries: [valid] }),
      ),
    );

    expect(journal.load()).toEqual([valid]);

    for (const impossible of [
      custodyEntry(2, {
        contractId: "contract-journal-synthetic-002",
        operationId: null,
        state: "submitting",
      }),
      custodyEntry(3, {
        contractId: null,
        operationId: "operation-journal-synthetic-003",
        state: "submitting",
      }),
      custodyEntry(4, {
        state: "submitting",
      }),
    ]) {
      const storage = new MemorySecretStorage();
      expect(() =>
        new CommandCustodyJournal(storage).upsert(impossible),
      ).toThrow("Invalid command custody entry");
      expect(storage.writes).toEqual([]);
    }
  });

  test("accepts unverifiable custody with either no proof identifiers or both known identifiers", () => {
    const completionUnknown = custodyEntry(1, {
      contractId: null,
      operationId: null,
      state: "unverifiable",
    });
    const evidenceRefreshFailed = custodyEntry(2, {
      state: "unverifiable",
    });
    const storage = new MemorySecretStorage(
      JSON.stringify({
        version: 1,
        entries: [completionUnknown, evidenceRefreshFailed],
      }),
    );

    expect(new CommandCustodyJournal(storage).load()).toEqual([
      completionUnknown,
      evidenceRefreshFailed,
    ]);

    for (const impossible of [
      custodyEntry(3, {
        contractId: null,
        state: "unverifiable",
      }),
      custodyEntry(4, {
        operationId: null,
        state: "unverifiable",
      }),
    ]) {
      expect(
        new CommandCustodyJournal(
          new MemorySecretStorage(
            JSON.stringify({
              version: 1,
              entries: [impossible],
            }),
          ),
        ).load(),
      ).toEqual([]);

      const writable = new MemorySecretStorage();
      expect(() =>
        new CommandCustodyJournal(writable).upsert(impossible),
      ).toThrow("Invalid command custody entry");
      expect(writable.writes).toEqual([]);
    }
  });

  test("fails closed on a malicious persisted success claim without proof identifiers", () => {
    const storage = new MemorySecretStorage(
      JSON.stringify({
        version: 1,
        entries: [
          custodyEntry(1),
          custodyEntry(2, {
            contractId: null,
            operationId: null,
            state: "succeeded",
          }),
        ],
      }),
    );

    expect(new CommandCustodyJournal(storage).load()).toEqual([]);
  });

  test("clamps an oversized configured retention limit to the absolute 50-entry ceiling", () => {
    const storage = new MemorySecretStorage();
    const journal = new CommandCustodyJournal(storage, {
      maxEntries: 500,
    });

    for (let sequence = 1; sequence <= 51; sequence += 1) {
      journal.upsert(custodyEntry(sequence));
    }

    const persisted = JSON.parse(
      storage.writes.at(-1)?.secret ?? "{}",
    ) as {
      readonly entries?: readonly CommandCustodyJournalEntry[];
    };
    expect(persisted.entries).toHaveLength(50);
    expect(persisted.entries?.at(0)?.idempotencyKey).toBe(
      "idempotency-journal-synthetic-51",
    );
    expect(persisted.entries?.at(-1)?.idempotencyKey).toBe(
      "idempotency-journal-synthetic-2",
    );

    const preloadedOversized = new MemorySecretStorage(
      JSON.stringify({
        version: 1,
        entries: Array.from({ length: 51 }, (_, index) =>
          custodyEntry(index + 1),
        ),
      }),
    );
    expect(
      new CommandCustodyJournal(preloadedOversized, {
        maxEntries: 500,
      }).load(),
    ).toEqual([]);
  });
});
