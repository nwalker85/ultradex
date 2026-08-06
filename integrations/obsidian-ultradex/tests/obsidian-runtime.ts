interface RegisteredCommand {
  readonly id: string;
  readonly name: string;
  readonly callback?: () => unknown;
}

interface TestElementOptions {
  readonly text?: string;
  readonly cls?: string | readonly string[];
  readonly attr?: Readonly<Record<string, string | number | boolean | null>>;
  readonly type?: string;
}

export class TestElement {
  readonly children: TestElement[] = [];
  readonly attributes: Record<string, string> = {};
  readonly eventListeners: Record<
    string,
    Array<(event: unknown) => unknown>
  > = {};
  readonly style: Record<string, string> = {};
  disabled = false;
  readOnly = false;
  required = false;
  value = "";
  readonly ownerDocument: {
    activeElement: TestElement | null;
  };
  readonly classList = {
    add: (...tokens: string[]): void => {
      const classes = new Set(this.className.split(/\s+/u).filter(Boolean));
      for (const token of tokens) {
        classes.add(token);
      }
      this.className = [...classes].join(" ");
    },
  };
  private ownText = "";

  constructor(
    readonly tagName = "div",
    public className = "",
    ownerDocument?: {
      activeElement: TestElement | null;
    },
  ) {
    this.ownerDocument = ownerDocument ?? { activeElement: null };
  }

  get textContent(): string {
    return this.ownText + this.children.map((child) => child.textContent).join("");
  }

  set textContent(value: string) {
    this.ownText = value;
  }

  empty(): void {
    this.children.length = 0;
    this.ownText = "";
  }

  createEl(
    tag: string,
    options: TestElementOptions | string = {},
  ): TestElement {
    const normalized =
      typeof options === "string" ? { text: options } : options;
    const className = Array.isArray(normalized.cls)
      ? normalized.cls.join(" ")
      : normalized.cls ?? "";
    const child = new TestElement(
      tag,
      className,
      this.ownerDocument,
    );
    child.textContent = normalized.text ?? "";
    if (normalized.type !== undefined) {
      child.setAttribute("type", normalized.type);
    }
    for (const [name, value] of Object.entries(normalized.attr ?? {})) {
      if (value !== null) {
        child.setAttribute(name, String(value));
      }
    }
    this.children.push(child);
    return child;
  }

  createDiv(options: TestElementOptions | string = {}): TestElement {
    return this.createEl("div", options);
  }

  createSpan(options: TestElementOptions | string = {}): TestElement {
    return this.createEl("span", options);
  }

  setAttribute(name: string, value: string): void {
    this.attributes[name] = value;
  }

  getAttribute(name: string): string | null {
    return this.attributes[name] ?? null;
  }

  setText(value: string): void {
    this.textContent = value;
  }

  addEventListener(
    type: string,
    listener: (event: unknown) => unknown,
  ): void {
    (this.eventListeners[type] ??= []).push(listener);
  }

  click(): void {
    if (this.disabled) {
      return;
    }
    for (const listener of this.eventListeners.click ?? []) {
      void listener({ type: "click", target: this });
    }
  }

  contains(element: TestElement | null): boolean {
    return (
      element === this ||
      this.children.some((child) => child.contains(element))
    );
  }

  focus(): void {
    this.ownerDocument.activeElement = this;
  }

  querySelectorAll(selector: string): TestElement[] {
    const attributePresence =
      /^\[([A-Za-z0-9_-]+)\]$/u.exec(selector)?.[1];
    if (attributePresence === undefined) {
      return [];
    }
    return [
      ...(this.getAttribute(attributePresence) === null ? [] : [this]),
      ...this.children.flatMap((child) =>
        child.querySelectorAll(selector),
      ),
    ];
  }
}

export class Plugin {
  readonly registeredCommands: RegisteredCommand[] = [];
  readonly registeredSettingTabs: PluginSettingTab[] = [];
  readonly registeredViews: {
    readonly type: string;
    readonly creator: (leaf: unknown) => unknown;
  }[] = [];
  readonly savedData: unknown[] = [];

  constructor(
    readonly app: Record<string, unknown>,
    readonly manifest: Record<string, unknown>,
  ) {}

  addCommand(command: RegisteredCommand): RegisteredCommand {
    this.registeredCommands.push(command);
    return command;
  }

  addSettingTab(settingTab: PluginSettingTab): void {
    this.registeredSettingTabs.push(settingTab);
  }

  registerView(
    type: string,
    creator: (leaf: unknown) => unknown,
  ): void {
    this.registeredViews.push({ type, creator });
  }

  async loadData(): Promise<unknown> {
    return null;
  }

  async saveData(data: unknown): Promise<void> {
    this.savedData.push(structuredClone(data));
  }
}

export class ItemView {
  readonly contentEl = new TestElement();

  constructor(readonly leaf: unknown) {}
}

export class PluginSettingTab {
  readonly containerEl = new TestElement();

  constructor(
    readonly app: Record<string, unknown>,
    readonly plugin: Plugin,
  ) {}
}

class TextControl {
  readonly inputEl = { type: "text" };

  setPlaceholder(): this {
    return this;
  }

  setValue(): this {
    return this;
  }

  onChange(): this {
    return this;
  }
}

class ButtonControl {
  setButtonText(): this {
    return this;
  }

  setCta(): this {
    return this;
  }

  onClick(): this {
    return this;
  }
}

export class Setting {
  constructor(readonly containerEl: TestElement) {}

  setName(): this {
    return this;
  }

  setDesc(): this {
    return this;
  }

  addText(callback: (control: TextControl) => unknown): this {
    callback(new TextControl());
    return this;
  }

  addButton(callback: (control: ButtonControl) => unknown): this {
    callback(new ButtonControl());
    return this;
  }
}

export class Notice {
  static readonly messages: string[] = [];

  constructor(readonly message: string) {
    Notice.messages.push(message);
  }
}

export async function requestUrl(): Promise<never> {
  throw new Error(
    "Tests must inject the requestUrl boundary instead of using the Obsidian host runtime",
  );
}

export class TestSecretStorage {
  readonly values = new Map<string, string>();
  readonly writes: Array<{
    readonly id: string;
    readonly secret: string;
  }> = [];

  getSecret(id: string): string | null {
    return this.values.get(id) ?? null;
  }

  setSecret(id: string, secret: string): void {
    this.values.set(id, secret);
    this.writes.push({ id, secret });
  }
}

export function createTestApp(): {
  readonly app: Record<string, unknown>;
  readonly leafStates: unknown[];
  readonly secretStorage: TestSecretStorage;
} {
  const leafStates: unknown[] = [];
  const secretStorage = new TestSecretStorage();
  const leaf = {
    async setViewState(state: unknown): Promise<void> {
      leafStates.push(structuredClone(state));
    },
  };
  return {
    app: {
      secretStorage,
      workspace: {
        getLeaf(): typeof leaf {
          return leaf;
        },
        getLeavesOfType(): unknown[] {
          return [];
        },
        async revealLeaf(): Promise<void> {},
      },
    },
    leafStates,
    secretStorage,
  };
}
