import { parse } from "yaml";
import type {
  PredicateType,
  Step,
  StepPrecondition,
  StepProduce,
  WorkflowDefinition,
} from "./models";

export function parsePreconditionString(raw: string): StepPrecondition {
  const match = raw.match(/^(be|have|know|did|reachable|cite)\(/);
  if (!match) {
    throw new Error(`Invalid precondition predicate: ${raw}`);
  }
  const predicateType = match[1] as PredicateType;
  return {
    predicateType,
    rawExpression: raw.trim(),
  };
}

export function parseProduceString(declaration: string, kind: string): StepProduce {
  return {
    kind: (kind as any) || "state_effect",
    declaration: declaration.trim(),
  };
}

export function parseWorkflowYaml(yamlContent: string): WorkflowDefinition {
  const parsed = parse(yamlContent);

  const steps: Step[] = (parsed.steps || []).map((s: any) => ({
    id: s.id,
    triplet: {
      actingRole: s.triplet.acting_role,
      stance: s.triplet.stance,
      mode: s.triplet.mode,
      targetSelector: s.triplet.target,
    },
    preconditions: (s.preconditions || []).map(parsePreconditionString),
    produces: (s.produces || []).map((p: any) =>
      parseProduceString(p.declaration, p.kind)
    ),
  }));

  return {
    id: parsed.id,
    version: parsed.version,
    description: parsed.description,
    places: parsed.places || [],
    steps,
  };
}
