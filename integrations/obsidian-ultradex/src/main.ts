import { UltradexClient } from "@ultradex/sdk";
import {
  Notice,
  Plugin,
  PluginSettingTab,
  Setting,
  type App,
  type WorkspaceLeaf,
} from "obsidian";

import { ObsidianRequestTransport } from "./obsidian-transport.js";
import { CommandController } from "./mutations/command-controller.js";
import { CommandCustodyJournal } from "./mutations/command-custody-journal.js";
import { OperationTracker } from "./mutations/operation-tracker.js";
import { ProjectionStore } from "./projection-store.js";
import {
  DEFAULT_ULTRADEX_SETTINGS,
  SecureSettingsStore,
  UltradexSetupError,
  type ObsidianSecretStorage,
  type UltradexPluginSettings,
} from "./settings.js";
import { sanitizeDisplayText } from "./sanitize.js";
import {
  ULTRADEX_OPERATOR_VIEW_TYPE,
  UltradexMonitorView,
} from "./views/monitor-view.js";

export { ULTRADEX_OPERATOR_VIEW_TYPE } from "./views/monitor-view.js";

class UltradexSettingsTab extends PluginSettingTab {
  constructor(
    app: App,
    private readonly plugin: UltradexPlugin,
  ) {
    super(app, plugin);
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();
    containerEl.createEl("h2", { text: "Ultradex Operator" });

    new Setting(containerEl)
      .setName("Ultradex base URL")
      .setDesc("The Ultradex service origin. API paths remain owned by the SDK.")
      .addText((text) =>
        text
          .setPlaceholder("http://127.0.0.1:8000")
          .setValue(this.plugin.settings.baseUrl)
          .onChange(async (baseUrl) => {
            await this.plugin.saveSettings({
              ...this.plugin.settings,
              baseUrl,
            });
          }),
      );

    new Setting(containerEl)
      .setName("Refresh interval")
      .setDesc("Seconds between automatic projection refreshes.")
      .addText((text) =>
        text
          .setPlaceholder("30")
          .setValue(String(this.plugin.settings.refreshIntervalSeconds))
          .onChange(async (value) => {
            const refreshIntervalSeconds = Number(value);
            if (
              !Number.isFinite(refreshIntervalSeconds) ||
              refreshIntervalSeconds <= 0
            ) {
              return;
            }
            await this.plugin.saveSettings({
              ...this.plugin.settings,
              refreshIntervalSeconds,
            });
          }),
      );

    if (!this.plugin.hasSecretStorage()) {
      containerEl.createDiv({
        cls: "ultradex-settings-note",
        text: "Obsidian 1.11.4 or newer with SecretStorage is required. Ultradex will not connect or store a plaintext token.",
      });
      return;
    }

    let pendingToken = "";
    let tokenInput: HTMLInputElement | undefined;
    new Setting(containerEl)
      .setName("API token")
      .setDesc(
        "Saved only in Obsidian SecretStorage as ultradex-api-token. The field is cleared after saving.",
      )
      .addText((text) => {
        tokenInput = text.inputEl;
        text.inputEl.type = "password";
        text
          .setPlaceholder("Enter token")
          .onChange((token) => {
            pendingToken = token;
          });
      })
      .addButton((button) =>
        button
          .setButtonText("Save token")
          .setCta()
          .onClick(() => {
            try {
              this.plugin.saveToken(pendingToken);
              pendingToken = "";
              if (tokenInput !== undefined) {
                tokenInput.value = "";
              }
              new Notice("Ultradex API token saved to Obsidian SecretStorage.");
            } catch (error) {
              const message =
                error instanceof UltradexSetupError
                  ? error.message
                  : "Ultradex API token could not be saved.";
              new Notice(message);
            }
          }),
      );
  }
}

export default class UltradexPlugin extends Plugin {
  settings: UltradexPluginSettings = DEFAULT_ULTRADEX_SETTINGS;

  private settingsStore!: SecureSettingsStore;
  private projectionStore: ProjectionStore | null = null;
  private viewRegistered = false;

  async onload(): Promise<void> {
    this.settingsStore = new SecureSettingsStore(
      {
        loadData: () => this.loadData(),
        saveData: (data) => this.saveData(data),
      },
      this.secretStorage(),
    );
    this.settings = await this.settingsStore.load();

    this.addSettingTab(new UltradexSettingsTab(this.app, this));
    this.ensureViewRegistered();
    this.registerCommands();
  }

  async saveSettings(
    settings: UltradexPluginSettings,
  ): Promise<void> {
    this.settings = await this.settingsStore.save(settings);
  }

  saveToken(token: string): void {
    this.settingsStore.saveToken(token);
  }

  requireToken(): string {
    return this.settingsStore.requireToken();
  }

  hasSecretStorage(): boolean {
    return this.secretStorage() !== undefined;
  }

  createClient(): UltradexClient {
    const token = this.requireToken();
    return new UltradexClient({
      baseUrl: this.settings.baseUrl,
      token,
      transport: new ObsidianRequestTransport({
        secretStorage: this.secretStorage(),
        secretId: this.settings.secretId,
      }),
    });
  }

  private registerCommands(): void {
    this.addCommand({
      id: "open-operator-console",
      name: "Open operator console",
      callback: () => this.openOperatorConsole(),
    });
    this.addCommand({
      id: "refresh-projections",
      name: "Refresh projections",
      callback: async () => {
        await this.refreshAndOpen("Ultradex projections refreshed.");
      },
    });
    this.addCommand({
      id: "retry-authentication",
      name: "Retry authentication",
      callback: async () => {
        await this.refreshAndOpen("Ultradex authentication rechecked.");
      },
    });
    this.addCommand({
      id: "clear-cached-snapshot",
      name: "Clear cached snapshot",
      callback: () => {
        const snapshot = this.projectionStore?.getState().snapshot;
        const hadSnapshot = snapshot !== null && snapshot !== undefined;
        this.projectionStore?.clear();
        new Notice(
          hadSnapshot
            ? "Cached Ultradex snapshot cleared. Server and vault data were not changed."
            : "No Ultradex projection snapshot is cached.",
        );
      },
    });
  }

  private async refreshAndOpen(successMessage: string): Promise<void> {
    const refresh = this.getProjectionStore().refresh();
    await this.openOperatorConsole();
    const state = await refresh;
    if (state.status === "ready") {
      new Notice(successMessage);
      return;
    }
    if (
      state.status === "stale" &&
      state.errorCategory === null &&
      state.snapshot !== null
    ) {
      const aggregate = state.snapshot.aggregateFreshness;
      new Notice(
        `Ultradex projections refreshed with degraded freshness. ${sanitizeDisplayText(aggregate.projection)} is ${aggregate.status}.`,
      );
      return;
    }
    new Notice(
      state.errorCategory === "authentication"
        ? "Ultradex authentication is required. Check Operator settings."
        : state.status === "stale"
          ? "Ultradex refresh failed. The previous verified snapshot is retained."
          : "Ultradex projections are unavailable. Check the operator monitor.",
    );
  }

  private async openOperatorConsole(): Promise<void> {
    this.ensureViewRegistered();
    const existingLeaf = this.app.workspace.getLeavesOfType(
      ULTRADEX_OPERATOR_VIEW_TYPE,
    )[0];
    const leaf = existingLeaf ?? this.app.workspace.getLeaf("tab");
    await leaf.setViewState({
      type: ULTRADEX_OPERATOR_VIEW_TYPE,
      active: true,
    });
    await this.app.workspace.revealLeaf(leaf);
  }

  private ensureViewRegistered(): void {
    if (this.viewRegistered) {
      return;
    }
    this.registerView(
      ULTRADEX_OPERATOR_VIEW_TYPE,
      (leaf) => {
        const store = this.getProjectionStore();
        let client: UltradexClient | null = null;
        const clientProvider = (): UltradexClient => {
          client ??= this.createClient();
          return client;
        };
        const tracker = new OperationTracker(clientProvider);
        const controller = new CommandController({
          client: clientProvider,
          projectionStore: store,
          operationTracker: tracker,
          journal: new CommandCustodyJournal(this.secretStorage()),
        });
        return new UltradexMonitorView(leaf, store, {
          commandController: controller,
          baseUrl: () => this.settings.baseUrl,
        });
      },
    );
    this.viewRegistered = true;
  }

  private getProjectionStore(): ProjectionStore {
    this.projectionStore ??= new ProjectionStore(() => this.createClient());
    return this.projectionStore;
  }

  private secretStorage(): ObsidianSecretStorage | undefined {
    const app = this.app as App & {
      readonly secretStorage?: ObsidianSecretStorage;
    };
    return app.secretStorage;
  }
}
