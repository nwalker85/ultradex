import { readFileSync } from "fs";
import { join } from "path";
import { MimirSurrealClient } from "../../../packages/db-surreal/src/client";
import { MimirWorkflowEngine } from "../../../packages/mimir-engine/src/engine";
import { parseWorkflowYaml } from "../../../packages/mimir-engine/src/parser";
import type { WorkflowInstance } from "../../../packages/mimir-engine/src/models";

export async function runAmbientAccountabilityLoop(client: MimirSurrealClient): Promise<number> {
  const yamlPath = join(__dirname, "../../../workflows/career_pursuit_lifecycle.yaml");
  const yamlContent = readFileSync(yamlPath, "utf-8");
  const workflow = parseWorkflowYaml(yamlContent);
  const engine = new MimirWorkflowEngine(workflow);

  const db = client.getRawDb();

  // 1. Fetch active leads and opportunities from SurrealDB
  const [leads] = await db.query<[any[]]>("SELECT * FROM lead WHERE state != 'disqualified' AND state != 'converted';");
  const [opportunities] = await db.query<[any[]]>("SELECT * FROM opportunity WHERE stage != 'closed_won' AND stage != 'closed_lost';");

  let actionsGenerated = 0;

  // 2. Evaluate Leads
  for (const lead of leads || []) {
    const instance: WorkflowInstance = {
      id: lead.id,
      workflowId: "career_pursuit_lifecycle",
      currentPlaces: [lead.state === "discovered" ? "lead_discovered" : "lead_qualified"],
      statePayload: lead,
      edges: [],
      claims: [],
      citations: [],
      history: [],
    };

    const eligible = engine.getEligibleTransitions(instance);
    for (const step of eligible) {
      if (step.id === "qualify_lead") {
        await client.pushNextBestAction({
          urgency: "high",
          actionType: "recruiter_reply",
          targetId: lead.id,
          title: `Qualify Lead: ${lead.title}`,
          narrative: `Lead matches BANT criteria with need alignment of ${lead.bant?.need_alignment || 0}. Ready to convert to Opportunity.`,
          payload: { stepId: step.id, leadId: lead.id },
        });
        actionsGenerated++;
      }
    }
  }

  // 3. Evaluate Opportunities
  for (const opp of opportunities || []) {
    const instance: WorkflowInstance = {
      id: opp.id,
      workflowId: "career_pursuit_lifecycle",
      currentPlaces: [opp.stage === "1_target" ? "target_mapped" : opp.stage],
      statePayload: opp,
      edges: [],
      claims: [],
      citations: [],
      history: [],
    };

    const eligible = engine.getEligibleTransitions(instance);
    for (const step of eligible) {
      await client.pushNextBestAction({
        urgency: "critical",
        actionType: "champion_followup",
        targetId: opp.id,
        title: `Next Action: ${step.id.replace(/_/g, " ").toUpperCase()} for ${opp.title}`,
        narrative: `Preconditions satisfied for step ${step.id}. Transition ready to fire.`,
        payload: { stepId: step.id, opportunityId: opp.id },
      });
      actionsGenerated++;
    }
  }

  return actionsGenerated;
}

if (import.meta.main) {
  const client = new MimirSurrealClient();
  await client.connect();
  console.log("Connected to SurrealDB. Running Ambient Accountability Loop...");
  const count = await runAmbientAccountabilityLoop(client);
  console.log(`✓ Evaluated Petri Net markings. Generated ${count} Next Best Actions.`);
  await client.close();
}
