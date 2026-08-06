import { describe, expect, test } from "vitest";

import {
  DEFAULT_ULTRADEX_SETTINGS,
  SecureSettingsStore,
  ULTRADEX_TOKEN_SECRET_ID,
  type ObsidianSecretStorage,
  type PluginDataPersistence,
  type UltradexPluginSettings,
} from "../src/settings.js";

class MemoryPluginData implements PluginDataPersistence {
  loaded: unknown = null;
  readonly saved: unknown[] = [];

  async loadData(): Promise<unknown> {
    return this.loaded;
  }

  async saveData(data: unknown): Promise<void> {
    this.saved.push(structuredClone(data));
  }
}

class MemorySecretStorage implements ObsidianSecretStorage {
  private readonly values = new Map<string, string>();

  getSecret(id: string): string | null {
    return this.values.get(id) ?? null;
  }

  setSecret(id: string, secret: string): void {
    this.values.set(id, secret);
  }
}

describe("SecureSettingsStore", () => {
  test("ordinary plugin data contains only the non-secret settings allowlist", async () => {
    const persistence = new MemoryPluginData();
    const secrets = new MemorySecretStorage();
    const store = new SecureSettingsStore(persistence, secrets);
    const settings: UltradexPluginSettings & { token: string } = {
      ...DEFAULT_ULTRADEX_SETTINGS,
      baseUrl: "https://synthetic.invalid",
      refreshIntervalSeconds: 45,
      viewFilters: {
        opportunityStatuses: ["active"],
        applicationStages: ["screen"],
        relationshipKinds: ["recruiter"],
        outreachStatuses: ["draft"],
      },
      uiPreferences: {
        compactTables: false,
        operationsRailOpen: true,
      },
      token: "synthetic-secret-value",
    };

    await store.save(settings);

    expect(persistence.saved).toEqual([
      {
        baseUrl: "https://synthetic.invalid",
        refreshIntervalSeconds: 45,
        viewFilters: {
          opportunityStatuses: ["active"],
          applicationStages: ["screen"],
          relationshipKinds: ["recruiter"],
          outreachStatuses: ["draft"],
        },
        secretId: "ultradex-api-token",
        uiPreferences: {
          compactTables: false,
          operationsRailOpen: true,
        },
      },
    ]);
    expect(JSON.stringify(persistence.saved)).not.toContain(
      "synthetic-secret-value",
    );
  });

  test("token writes go only to SecretStorage under the stable secret ID", () => {
    const persistence = new MemoryPluginData();
    const secrets = new MemorySecretStorage();
    const store = new SecureSettingsStore(persistence, secrets);

    store.saveToken("synthetic-secret-value");

    expect(secrets.getSecret(ULTRADEX_TOKEN_SECRET_ID)).toBe(
      "synthetic-secret-value",
    );
    expect(persistence.saved).toEqual([]);
  });

  test("loading strips unknown plaintext secret fields from plugin data", async () => {
    const persistence = new MemoryPluginData();
    persistence.loaded = {
      baseUrl: "https://synthetic.invalid/",
      refreshIntervalSeconds: 60,
      secretId: "ultradex-api-token",
      token: "must-not-enter-settings",
    };
    const store = new SecureSettingsStore(
      persistence,
      new MemorySecretStorage(),
    );

    const loaded = await store.load();

    expect(loaded).toEqual({
      ...DEFAULT_ULTRADEX_SETTINGS,
      baseUrl: "https://synthetic.invalid",
      refreshIntervalSeconds: 60,
    });
    expect(loaded).not.toHaveProperty("token");
  });
});
