const INVISIBLE_CONTROL_CHARACTERS =
  /[\u0000-\u001F\u007F-\u009F\u061C\u200E\u200F\u202A-\u202E\u2066-\u2069]/gu;

export function sanitizeDisplayText(
  value: unknown,
  fallback = "Unavailable",
  maxLength = 160,
): string {
  const input = typeof value === "string" ? value : "";
  const normalized = input
    .replace(INVISIBLE_CONTROL_CHARACTERS, " ")
    .replace(/\s+/gu, " ")
    .trim();
  if (normalized.length === 0) {
    return fallback;
  }
  const characters = Array.from(normalized);
  if (characters.length <= maxLength) {
    return normalized;
  }
  return `${characters.slice(0, Math.max(0, maxLength - 1)).join("")}…`;
}
