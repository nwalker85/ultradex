import { Surreal } from "surrealdb";

export interface MimirSurrealConfig {
  url?: string;
  namespace?: string;
  database?: string;
  username?: string;
  password?: string;
}

export class MimirSurrealClient {
  private db: Surreal;
  private config: MimirSurrealConfig;

  constructor(config: MimirSurrealConfig = {}) {
    this.db = new Surreal();
    this.config = {
      url: config.url || process.env.SURREAL_URL || "http://127.0.0.1:8000/rpc",
      namespace: config.namespace || process.env.SURREAL_NS || "ravenhelm",
      database: config.database || process.env.SURREAL_DB || "career_command_center",
      username: config.username || process.env.SURREAL_USER || "root",
      password: config.password || process.env.SURREAL_PASS || "root",
    };
  }

  public async connect(): Promise<void> {
    await this.db.connect(this.config.url!);
    await this.db.use({
      namespace: this.config.namespace!,
      database: this.config.database!,
    });
    if (this.config.username && this.config.password) {
      await this.db.signin({
        username: this.config.username,
        password: this.config.password,
      });
    }
  }

  public async close(): Promise<void> {
    await this.db.close();
  }

  public getRawDb(): Surreal {
    return this.db;
  }

  // --- Graph Relation Helpers ---

  public async createContainsEdge(fromRecord: string, toRecord: string, kind = "CONTAINS__SHARED"): Promise<any> {
    return this.db.query(`RELATE ${fromRecord}->contains_edge->${toRecord} SET kind = $kind;`, { kind });
  }

  public async createConnectsToEdge(fromRecord: string, toRecord: string, kind = "CONNECTS_TO__SHARED"): Promise<any> {
    return this.db.query(`RELATE ${fromRecord}->connects_to_edge->${toRecord} SET kind = $kind;`, { kind });
  }

  public async createDerivedFromEdge(fromRecord: string, toRecord: string, kind = "DERIVED_FROM__SHARED"): Promise<any> {
    return this.db.query(`RELATE ${fromRecord}->derived_from_edge->${toRecord} SET kind = $kind;`, { kind });
  }

  // --- KNOW Claim Receipts ---

  public async issueKnowClaim(claim: {
    observer: string;
    method: string;
    targetRef: string;
    weight: number;
    decayRate?: number;
    validityWindowSeconds?: number;
    evidenceDigest: string;
  }): Promise<any> {
    return this.db.create("know_claim", {
      observer: claim.observer,
      method: claim.method,
      target_ref: claim.targetRef,
      weight: claim.weight,
      decay_rate: claim.decayRate ?? 0.05,
      validity_window_seconds: claim.validityWindowSeconds ?? 2592000,
      evidence_digest: claim.evidenceDigest,
      created_at: new Date().toISOString(),
    });
  }

  // --- Next Best Actions (Live Push) ---

  public async pushNextBestAction(action: {
    urgency: "critical" | "high" | "medium" | "low";
    actionType: "recruiter_reply" | "champion_followup" | "interview_prep" | "interview_debrief" | "tofu_publish";
    targetId: string;
    title: string;
    narrative: string;
    payload?: Record<string, any>;
    deadline?: string;
  }): Promise<any> {
    return this.db.create("next_best_action", {
      urgency: action.urgency,
      action_type: action.actionType,
      target_id: action.targetId,
      title: action.title,
      narrative: action.narrative,
      payload: action.payload || {},
      status: "pending",
      deadline: action.deadline,
      created_at: new Date().toISOString(),
    });
  }

  public async listPendingActions(): Promise<any[]> {
    const [result] = await this.db.query<[any[]]>(
      "SELECT * FROM next_best_action WHERE status = 'pending' ORDER BY created_at DESC;"
    );
    return result || [];
  }
}
