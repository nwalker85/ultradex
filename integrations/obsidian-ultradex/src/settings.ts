import { UltradexTransportError } from "@ultradex/sdk";

export const ULTRADEX_TOKEN_SECRET_ID = "ultradex-api-token";

export interface UltradexViewFilters {
  readonly opportunityStatuses: readonly string[];
  readonly applicationStages: readonly string[];
  readonly relationshipKinds: readonly string[];
  readonly outreachStatuses: readonly string[];
}

export interface UltradexUiPreferences {
  readonly compactTables: boolean;
  readonly operationsRailOpen: boolean;
}

export interface UltradexPluginSettings {
  readonly baseUrl: string;
  readonly refreshIntervalSeconds: number;
  readonly viewFilters: UltradexViewFilters;
  readonly secretId: string;
  readonly uiPreferences: UltradexUiPreferences;
}

export interface PluginDataPersistence {
  loadData(): Promise<unknown>;
  saveData(data: unknown): Promise<void>;
}

export interface ObsidianSecretStorage {
  getSecret(id: string): string | null;
  setSecret(id: string, secret: string): void;
}

export type UltradexSetupErrorReason =
  | "secret_storage_unavailable"
  | "token_missing";

export class UltradexSetupError extends UltradexTransportError {
  readonly setupCode = "authentication_setup" as const;

  constructor(readonly reason: UltradexSetupErrorReason) {
    const message =
      reason === "secret_storage_unavailable"
        ? "Obsidian SecretStorage is required before Ultradex can connect"
        : "Select or store an Ultradex API token before connecting";
    super(message);
    Object.defineProperty(this, "name", {
      configurable: true,
      value: "UltradexSetupError",
    });
  }
}

export const DEFAULT_ULTRADEX_SETTINGS: UltradexPluginSettings = {
  baseUrl: "http://127.0.0.1:8000",
  refreshIntervalSeconds: 30,
  viewFilters: {
    opportunityStatuses: [],
    applicationStages: [],
    relationshipKinds: [],
    outreachStatuses: [],
  },
  secretId: ULTRADEX_TOKEN_SECRET_ID,
  uiPreferences: {
    compactTables: true,
    operationsRailOpen: true,
  },
};

function stringList(value: unknown): readonly string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(
    (entry): entry is string =>
      typeof entry === "string" && entry.trim().length > 0,
  );
}

function record(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null
    ? (value as Record<string, unknown>)
    : {};
}

function normalizeBaseUrl(value: unknown): string {
  if (typeof value !== "string") {
    return DEFAULT_ULTRADEX_SETTINGS.baseUrl;
  }
  const normalized = value.trim().replace(/\/+$/u, "");
  return normalized.length === 0
    ? DEFAULT_ULTRADEX_SETTINGS.baseUrl
    : normalized;
}

export function normalizePluginSettings(
  value: unknown,
): UltradexPluginSettings {
  const input = record(value);
  const filters = record(input.viewFilters);
  const preferences = record(input.uiPreferences);
  const refreshIntervalSeconds =
    typeof input.refreshIntervalSeconds === "number" &&
    Number.isFinite(input.refreshIntervalSeconds) &&
    input.refreshIntervalSeconds > 0
      ? input.refreshIntervalSeconds
      : DEFAULT_ULTRADEX_SETTINGS.refreshIntervalSeconds;

  return {
    baseUrl: normalizeBaseUrl(input.baseUrl),
    refreshIntervalSeconds,
    viewFilters: {
      opportunityStatuses: stringList(filters.opportunityStatuses),
      applicationStages: stringList(filters.applicationStages),
      relationshipKinds: stringList(filters.relationshipKinds),
      outreachStatuses: stringList(filters.outreachStatuses),
    },
    secretId: ULTRADEX_TOKEN_SECRET_ID,
    uiPreferences: {
      compactTables:
        typeof preferences.compactTables === "boolean"
          ? preferences.compactTables
          : DEFAULT_ULTRADEX_SETTINGS.uiPreferences.compactTables,
      operationsRailOpen:
        typeof preferences.operationsRailOpen === "boolean"
          ? preferences.operationsRailOpen
          : DEFAULT_ULTRADEX_SETTINGS.uiPreferences.operationsRailOpen,
    },
  };
}

export class SecureSettingsStore {
  constructor(
    private readonly persistence: PluginDataPersistence,
    private readonly secretStorage: ObsidianSecretStorage | undefined,
  ) {}

  async load(): Promise<UltradexPluginSettings> {
    return normalizePluginSettings(await this.persistence.loadData());
  }

  async save(
    settings: UltradexPluginSettings,
  ): Promise<UltradexPluginSettings> {
    const safeSettings = normalizePluginSettings(settings);
    await this.persistence.saveData(safeSettings);
    return safeSettings;
  }

  saveToken(token: string): void {
    const secretStorage = this.requireSecretStorage();
    if (token.trim().length === 0) {
      throw new UltradexSetupError("token_missing");
    }
    secretStorage.setSecret(ULTRADEX_TOKEN_SECRET_ID, token);
  }

  requireToken(): string {
    const token = this.requireSecretStorage().getSecret(
      ULTRADEX_TOKEN_SECRET_ID,
    );
    if (token === null || token.trim().length === 0) {
      throw new UltradexSetupError("token_missing");
    }
    return token;
  }

  private requireSecretStorage(): ObsidianSecretStorage {
    if (this.secretStorage === undefined) {
      throw new UltradexSetupError("secret_storage_unavailable");
    }
    return this.secretStorage;
  }
}
