import { describe, expect, it } from "bun:test";
import { readFileSync } from "fs";
import { join } from "path";
import { parseWorkflowYaml } from "./parser";
import { MimirWorkflowEngine } from "./engine";
import type { WorkflowInstance } from "./models";

describe("Mímir Workflow Engine v0.7.0 (Career Pursuit Formalism)", () => {
  const yamlPath = join(__dirname, "../../../workflows/career_pursuit_lifecycle.yaml");
  const yamlContent = readFileSync(yamlPath, "utf-8");
  const workflow = parseWorkflowYaml(yamlContent);
  const engine = new MimirWorkflowEngine(workflow);

  it("parses the career_pursuit_lifecycle workflow correctly", () => {
    expect(workflow.id).toBe("career_pursuit_lifecycle");
    expect(workflow.places.length).toBeGreaterThan(5);
    expect(workflow.steps.length).toBeGreaterThan(5);
  });

  it("qualifies a high-fit BANT lead into an eligible transition", () => {
    const qualifiedLeadInstance: WorkflowInstance = {
      id: "lead_parloa_ai",
      workflowId: "career_pursuit_lifecycle",
      currentPlaces: ["lead_discovered"],
      statePayload: {
        title: "Principal Solutions Architect — Enterprise Voice AI",
        state: "discovered",
        bant: {
          budget_fit: true,
          need_alignment: 0.92,
          authority_identified: true,
          timeline: "immediate",
        },
      },
      edges: [],
      claims: [],
      citations: [],
      history: [],
    };

    const eligible = engine.getEligibleTransitions(qualifiedLeadInstance);
    expect(eligible.map((s) => s.id)).toContain("qualify_lead");
    expect(eligible.map((s) => s.id)).not.toContain("disqualify_lead");

    // Fire transition
    const { instance: updated, receipt } = engine.fireTransition(
      qualifiedLeadInstance,
      "qualify_lead",
      "copilot"
    );
    expect(updated.statePayload.state).toBe("qualified");
    expect(receipt.stance).toBe("ACT");
    expect(receipt.mode).toBe("UPDATE");
  });

  it("surfaces champion outreach as Next Best Action when warm graph edge & know claim exist", () => {
    const opportunityTarget: WorkflowInstance = {
      id: "opp_parloa_vp",
      workflowId: "career_pursuit_lifecycle",
      currentPlaces: ["target_mapped"],
      statePayload: {
        title: "VP of Solutions Architecture",
        stage: "1_target",
      },
      edges: [
        {
          primitive: "CONNECTS_TO",
          kind: "CONNECTS_TO__SHARED",
          from: "contact:nate",
          to: "contact:brynn_ireland",
        },
      ],
      claims: [
        {
          targetRef: "contact:brynn_ireland",
          weight: 0.95,
          decayRate: 0.01,
          timestamp: Date.now(), // fresh
        },
      ],
      citations: [],
      history: [],
    };

    const eligible = engine.getEligibleTransitions(opportunityTarget);
    expect(eligible.map((s) => s.id)).toContain("initiate_champion_outreach");

    // Fire outreach transition
    const { instance: updated, receipt } = engine.fireTransition(
      opportunityTarget,
      "initiate_champion_outreach",
      "nate"
    );
    expect(updated.statePayload.stage).toBe("2_outreach");
    expect(receipt.stance).toBe("ACT");
    expect(receipt.mode).toBe("INITIATE");
  });
});
