import type {
  Step,
  WorkflowDefinition,
  WorkflowInstance,
} from "./models";
import { evaluatePrecondition, setJsonPointerValue } from "./predicates";

export interface FiredTransitionReceipt {
  receiptId: string;
  workflowId: string;
  instanceId: string;
  stepId: string;
  actor: string;
  stance: string;
  mode: string;
  targetSelector: string;
  stateDelta: Record<string, any>;
  executedAt: string;
  digest: string;
}

export class MimirWorkflowEngine {
  private workflow: WorkflowDefinition;

  constructor(workflow: WorkflowDefinition) {
    this.workflow = workflow;
  }

  /**
   * Computes all eligible transitions for a given instance based on current marking & 6 closed predicates.
   * This directly powers the Next Best Action (NBA) stream!
   */
  public getEligibleTransitions(instance: WorkflowInstance): Step[] {
    const eligible: Step[] = [];

    for (const step of this.workflow.steps) {
      // All preconditions must evaluate to true
      const allPreconditionsMet = step.preconditions.every((precondition) =>
        evaluatePrecondition(precondition, instance)
      );

      if (allPreconditionsMet) {
        eligible.push(step);
      }
    }

    return eligible;
  }

  /**
   * Fires an eligible transition on an instance, applying produces effects and emitting an immutable DO receipt.
   */
  public fireTransition(
    instance: WorkflowInstance,
    stepId: string,
    actor: string
  ): { instance: WorkflowInstance; receipt: FiredTransitionReceipt } {
    const step = this.workflow.steps.find((s) => s.id === stepId);
    if (!step) {
      throw new Error(`Step '${stepId}' not found in workflow '${this.workflow.id}'`);
    }

    // Verify eligibility
    const isEligible = step.preconditions.every((p) => evaluatePrecondition(p, instance));
    if (!isEligible) {
      throw new Error(`Step '${stepId}' preconditions not met for instance '${instance.id}'`);
    }

    const stateDelta: Record<string, any> = {};
    const updatedPayload = { ...instance.statePayload };

    // Apply produces effects
    for (const produce of step.produces) {
      if (produce.kind === "state_effect") {
        // e.g. "be(/stage := \"3_applied\")"
        const match = produce.declaration.match(/be\(\s*(\/[^\s:=]+)\s*:=\s*(.+)\s*\)/);
        if (match) {
          const [, pointer, rawVal] = match;
          let val: any;
          try {
            val = JSON.parse(rawVal);
          } catch {
            val = rawVal.replace(/^["']|["']$/g, "");
          }
          setJsonPointerValue(updatedPayload, pointer, val);
          stateDelta[pointer] = val;
        }
      }
    }

    const executedAt = new Date().toISOString();
    const receipt: FiredTransitionReceipt = {
      receiptId: `rcpt_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`,
      workflowId: this.workflow.id,
      instanceId: instance.id,
      stepId: step.id,
      actor,
      stance: step.triplet.stance,
      mode: step.triplet.mode,
      targetSelector: step.triplet.targetSelector,
      stateDelta,
      executedAt,
      digest: `sha256:${Buffer.from(`${instance.id}-${step.id}-${executedAt}`).toString("hex").substring(0, 32)}`,
    };

    const updatedInstance: WorkflowInstance = {
      ...instance,
      statePayload: updatedPayload,
      history: [
        ...instance.history,
        {
          stepId: step.id,
          actor,
          executedAt,
          stateDelta,
        },
      ],
    };

    return { instance: updatedInstance, receipt };
  }
}
