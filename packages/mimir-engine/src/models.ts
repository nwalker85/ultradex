import { z } from "zod";

export const StanceEnum = z.enum(["ACT", "REACT", "DIRECT", "WITNESS", "DECLARE"]);
export type Stance = z.infer<typeof StanceEnum>;

export const ModeEnum = z.enum([
  "CREATE",
  "READ",
  "UPDATE",
  "DELETE",
  "INITIATE",
  "RESPOND",
  "NOTIFY",
  "TRANSITION",
]);
export type Mode = z.infer<typeof ModeEnum>;

export const PredicateTypeEnum = z.enum([
  "be",
  "have",
  "know",
  "did",
  "reachable",
  "cite",
]);
export type PredicateType = z.infer<typeof PredicateTypeEnum>;

export interface TripletTemplate {
  actingRole: string;
  stance: Stance;
  mode: Mode;
  targetSelector: string;
}

export interface StepPrecondition {
  predicateType: PredicateType;
  rawExpression: string;
  path?: string;
  operator?: string;
  expectedValue?: any;
  targetRef?: string;
  minWeight?: number;
}

export interface StateEffect {
  path: string;
  operator: ":=";
  value: any;
}

export interface StepProduce {
  kind: "state_effect" | "entity" | "evidence" | "claim";
  declaration: string;
  stateEffect?: StateEffect;
}

export interface Step {
  id: string;
  triplet: TripletTemplate;
  preconditions: StepPrecondition[];
  produces: StepProduce[];
}

export interface Place {
  id: string;
  initial?: boolean;
  terminal?: boolean;
}

export interface WorkflowDefinition {
  id: string;
  version: string;
  description: string;
  places: Place[];
  steps: Step[];
}

export interface WorkflowInstance {
  id: string;
  workflowId: string;
  currentPlaces: string[];
  statePayload: Record<string, any>;
  edges: Array<{
    primitive: string;
    kind: string;
    from: string;
    to: string;
  }>;
  claims: Array<{
    targetRef: string;
    weight: number;
    decayRate: number;
    timestamp: number;
  }>;
  citations: Array<{
    plane: string;
    id: string;
  }>;
  history: Array<{
    stepId: string;
    actor: string;
    executedAt: string;
    stateDelta: Record<string, any>;
  }>;
}
