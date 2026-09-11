import { Hono } from "hono";
import { cors } from "hono/cors";
import { readFileSync } from "fs";
import { join } from "path";
import { MimirSurrealClient } from "../../../packages/db-surreal/src/client";
import { MimirWorkflowEngine } from "../../../packages/mimir-engine/src/engine";
import { parseWorkflowYaml } from "../../../packages/mimir-engine/src/parser";
import type { WorkflowInstance } from "../../../packages/mimir-engine/src/models";

const app = new Hono();
app.use("*", cors());

const surrealClient = new MimirSurrealClient();
const yamlPath = join(__dirname, "../../../workflows/career_pursuit_lifecycle.yaml");
const yamlContent = readFileSync(yamlPath, "utf-8");
const workflow = parseWorkflowYaml(yamlContent);
const workflowEngine = new MimirWorkflowEngine(workflow);

app.get("/health", (c) => c.json({ status: "ok", engine: "mimir-v0.7.0", db: "surrealdb" }));

// 1. Next Best Actions (The Live Ambient Rail)
app.get("/api/v1/nba", async (c) => {
  try {
    const actions = await surrealClient.listPendingActions();
    return c.json({ items: actions, count: actions.length });
  } catch (err: any) {
    return c.json({ error: err.message }, 500);
  }
});

// 2. Fire Transition (Mímir State Machine Execution)
app.post("/api/v1/transitions/fire", async (c) => {
  try {
    const body = await c.req.json();
    const { instanceId, stepId, actor = "nate" } = body;

    const db = surrealClient.getRawDb();
    const [record] = await db.query<[any[]]>(`SELECT * FROM ${instanceId};`);
    if (!record || record.length === 0) {
      return c.json({ error: `Instance ${instanceId} not found` }, 404);
    }

    const instanceData = record[0];
    const instance: WorkflowInstance = {
      id: instanceId,
      workflowId: workflow.id,
      currentPlaces: [instanceData.stage || instanceData.state || "lead_discovered"],
      statePayload: instanceData,
      edges: [],
      claims: [],
      citations: [],
      history: [],
    };

    const { instance: updated, receipt } = workflowEngine.fireTransition(instance, stepId, actor);

    // Save updated state and DO receipt in SurrealDB
    await db.query(`UPDATE ${instanceId} MERGE $payload;`, { payload: updated.statePayload });
    await db.create("do_receipt", {
      acting_role: actor,
      stance: receipt.stance,
      mode: receipt.mode,
      target_entity: instanceId,
      transition_id: stepId,
      state_delta: receipt.stateDelta,
      evidence_digest: receipt.digest,
      executed_at: receipt.executedAt,
    });

    return c.json({ success: true, updatedState: updated.statePayload, receipt });
  } catch (err: any) {
    return c.json({ error: err.message }, 400);
  }
});

// 3. Pipeline Deals & Opportunities
app.get("/api/v1/opportunities", async (c) => {
  try {
    const db = surrealClient.getRawDb();
    const [opps] = await db.query<[any[]]>(
      "SELECT *, ->pursuit_for->organization.* AS organizations FROM opportunity ORDER BY created_at DESC;"
    );
    return c.json({ items: opps || [] });
  } catch (err: any) {
    return c.json({ error: err.message }, 500);
  }
});

// 4. Organizations & Warm Contacts
app.get("/api/v1/organizations", async (c) => {
  try {
    const db = surrealClient.getRawDb();
    const [orgs] = await db.query<[any[]]>(
      "SELECT *, ->contains_edge->contact.* AS contacts FROM organization ORDER BY name ASC;"
    );
    return c.json({ items: orgs || [] });
  } catch (err: any) {
    return c.json({ error: err.message }, 500);
  }
});

// 5. Leads (Top of Funnel)
app.get("/api/v1/leads", async (c) => {
  try {
    const db = surrealClient.getRawDb();
    const [leads] = await db.query<[any[]]>(
      "SELECT * FROM lead ORDER BY bant.need_alignment DESC, created_at DESC;"
    );
    return c.json({ items: leads || [] });
  } catch (err: any) {
    return c.json({ error: err.message }, 500);
  }
});

export default {
  port: parseInt(process.env.PORT || "8787"),
  fetch: app.fetch,
};
