import type { StepPrecondition, WorkflowInstance } from "./models";

/**
 * Resolves an RFC 6901 JSON pointer against an object.
 * e.g. "/bant/budget_fit" -> obj.bant.budget_fit
 */
export function getJsonPointerValue(obj: Record<string, any>, pointer: string): any {
  if (!pointer.startsWith("/")) {
    pointer = "/" + pointer;
  }
  const parts = pointer.split("/").filter(Boolean);
  let curr = obj;
  for (const p of parts) {
    if (curr === undefined || curr === null) return undefined;
    curr = curr[p];
  }
  return curr;
}

/**
 * Sets an RFC 6901 JSON pointer on an object.
 */
export function setJsonPointerValue(obj: Record<string, any>, pointer: string, value: any): void {
  if (!pointer.startsWith("/")) {
    pointer = "/" + pointer;
  }
  const parts = pointer.split("/").filter(Boolean);
  let curr = obj;
  for (let i = 0; i < parts.length - 1; i++) {
    const p = parts[i];
    if (curr[p] === undefined || curr[p] === null) {
      curr[p] = {};
    }
    curr = curr[p];
  }
  if (parts.length > 0) {
    curr[parts[parts.length - 1]] = value;
  }
}

/**
 * Evaluates the 6 closed predicates against a live WorkflowInstance.
 */
export function evaluatePrecondition(
  precondition: StepPrecondition,
  instance: WorkflowInstance
): boolean {
  const { predicateType, rawExpression } = precondition;

  switch (predicateType) {
    case "be": {
      // e.g. "be(/bant/budget_fit == true)", "be(/bant/need_alignment >= 0.70)", "be(/stage in [\"1_target\", \"2_outreach\"])"
      const match = rawExpression.match(/be\(\s*(\/[^\s=><!]+)\s*(==|!=|>=|<=|>|<|in)\s*(.+)\s*\)/);
      if (!match) return false;
      const [, pointer, op, rawExpected] = match;
      const actual = getJsonPointerValue(instance.statePayload, pointer);
      
      let expected: any;
      try {
        expected = JSON.parse(rawExpected);
      } catch {
        expected = rawExpected.replace(/^["']|["']$/g, "");
      }

      if (op === "==") return actual === expected;
      if (op === "!=") return actual !== expected;
      if (op === ">=") return Number(actual) >= Number(expected);
      if (op === "<=") return Number(actual) <= Number(expected);
      if (op === ">") return Number(actual) > Number(expected);
      if (op === "<") return Number(actual) < Number(expected);
      if (op === "in") {
        return Array.isArray(expected) && expected.includes(actual);
      }
      return false;
    }

    case "have": {
      // e.g. "have(CONNECTS_TO__SHARED, contact:*)"
      const match = rawExpression.match(/have\(\s*([A-Za-z0-9_]+)\s*,\s*([^)]+)\s*\)/);
      if (!match) return false;
      const [, requiredKind, targetPattern] = match;
      return instance.edges.some(edge => {
        const kindMatches = edge.kind === requiredKind || edge.primitive === requiredKind.split("__")[0];
        const targetMatches = targetPattern === "*" || edge.to.includes(targetPattern.replace("*", ""));
        return kindMatches && targetMatches;
      });
    }

    case "know": {
      // e.g. "know(contact:*, 0.70)"
      const match = rawExpression.match(/know\(\s*([^,]+)\s*,\s*([0-9.]+)\s*\)/);
      if (!match) return false;
      const [, targetPattern, rawMinWeight] = match;
      const minWeight = parseFloat(rawMinWeight);
      const now = Date.now();

      return instance.claims.some(claim => {
        const targetMatches = targetPattern === "*" || claim.targetRef.includes(targetPattern.replace("*", ""));
        if (!targetMatches) return false;

        // Apply exponential decay: W(t) = W0 * e^(-gamma * delta_t_days)
        const daysElapsed = (now - claim.timestamp) / (1000 * 60 * 60 * 24);
        const currentWeight = claim.weight * Math.exp(-claim.decayRate * daysElapsed);
        return currentWeight >= minWeight;
      });
    }

    case "did": {
      // e.g. "did(INITIATE, contact:*)"
      const match = rawExpression.match(/did\(\s*([A-Za-z]+)\s*,\s*([^)]+)\s*\)/);
      if (!match) return false;
      const [, mode, target] = match;
      return instance.history.some(h => h.stepId.includes(mode.toLowerCase()) || h.stepId.includes(target));
    }

    case "reachable": {
      // e.g. "reachable(contact:*)"
      return instance.edges.some(e => e.kind.startsWith("CONNECTS_TO"));
    }

    case "cite": {
      // e.g. "cite(google_calendar, event_id)"
      const match = rawExpression.match(/cite\(\s*([A-Za-z0-9_]+)\s*,\s*([^)]+)\s*\)/);
      if (!match) return false;
      const [, requiredPlane] = match;
      return instance.citations.some(c => c.plane === requiredPlane && c.id !== "");
    }

    default:
      return false;
  }
}
