import type { ScheduleResult, ValidationMessage } from "../../contracts";
import { scheduleStatusLabels } from "../../domain/labels";

export function formatScheduleStatus(value: unknown): string {
  if (typeof value === "string" && Object.prototype.hasOwnProperty.call(scheduleStatusLabels, value)) {
    return scheduleStatusLabels[value as ScheduleResult["status"]];
  }
  return value == null ? "-" : String(value);
}

export function scheduleResultSummary(result: ScheduleResult | null) {
  return result
    ? { status: formatScheduleStatus(result.status), days: result.objective_days, tasks: result.tasks.length }
    : { status: "-", days: null, tasks: 0 };
}

export function summarizeDiagnostics(diagnostics: ValidationMessage[]) {
  return diagnostics.reduce(
    (summary, item) => ({ ...summary, [item.level]: summary[item.level] + 1 }),
    { error: 0, warning: 0, info: 0 },
  );
}

export function objectiveBreakdownEntries(result: ScheduleResult | null): Array<[string, unknown]> {
  return Object.entries(result?.objective_breakdown ?? {}).sort(([left], [right]) => left.localeCompare(right));
}
