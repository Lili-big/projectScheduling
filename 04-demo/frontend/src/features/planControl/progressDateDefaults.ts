export type ActualDateTaskStatus = "not_started" | "in_progress" | "completed" | "paused" | "cancelled";

export type PlannedTaskDates = {
  taskId: string;
  plannedStartDate: string | null;
  plannedFinishDate: string | null;
  isValid: boolean;
  message: string | null;
};

export type ActualDateSuggestionState = {
  actualStartSuggested: boolean;
  actualFinishSuggested: boolean;
};

export type ActualDateEntry = {
  status: ActualDateTaskStatus;
  actual_start_date?: string | null;
  actual_finish_date?: string | null;
};

type ScheduledTaskDateSource = {
  id: string;
  start_date?: string | null;
  finish_date?: string | null;
};

export type ActualDateDefaultResult<T extends ActualDateEntry> = {
  entry: T;
  suggestion: ActualDateSuggestionState;
};

const emptySuggestion: ActualDateSuggestionState = {
  actualStartSuggested: false,
  actualFinishSuggested: false,
};

const isoDatePattern = /^(\d{4})-(\d{2})-(\d{2})$/;

export function isIsoLocalDate(value: unknown): value is string {
  if (typeof value !== "string") return false;
  const match = isoDatePattern.exec(value);
  if (!match) return false;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  return parsed.getUTCFullYear() === year && parsed.getUTCMonth() === month - 1 && parsed.getUTCDate() === day;
}

export function formatLocalDate(value: Date = new Date()): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function dateCutoff(statusDate: string, today: string = formatLocalDate()): string | null {
  if (!isIsoLocalDate(statusDate) || !isIsoLocalDate(today)) return null;
  return statusDate <= today ? statusDate : today;
}

function plannedTaskDates(source: ScheduledTaskDateSource): PlannedTaskDates {
  const plannedStartDate = source.start_date || null;
  const plannedFinishDate = source.finish_date || null;
  if (!plannedStartDate || !plannedFinishDate) {
    return {
      taskId: source.id,
      plannedStartDate,
      plannedFinishDate,
      isValid: false,
      message: "缺少计划开始或计划完成日期，需人工填写实际日期。",
    };
  }
  if (!isIsoLocalDate(plannedStartDate) || !isIsoLocalDate(plannedFinishDate)) {
    return {
      taskId: source.id,
      plannedStartDate,
      plannedFinishDate,
      isValid: false,
      message: "计划日期格式无法识别，需人工填写实际日期。",
    };
  }
  if (plannedFinishDate < plannedStartDate) {
    return {
      taskId: source.id,
      plannedStartDate,
      plannedFinishDate,
      isValid: false,
      message: "计划完成日期早于计划开始日期，需人工核查。",
    };
  }
  return {
    taskId: source.id,
    plannedStartDate,
    plannedFinishDate,
    isValid: true,
    message: null,
  };
}

export function buildPlannedTaskDatesById(
  tasks: ScheduledTaskDateSource[],
): Record<string, PlannedTaskDates> {
  return Object.fromEntries(tasks.map((task) => [task.id, plannedTaskDates(task)]));
}

function proposedActualStart(planned: PlannedTaskDates | undefined, cutoff: string | null): string | null {
  if (!planned?.isValid || !planned.plannedStartDate || !cutoff) return null;
  return planned.plannedStartDate <= cutoff ? planned.plannedStartDate : cutoff;
}

function proposedActualFinish(
  actualStartDate: string | null,
  planned: PlannedTaskDates | undefined,
  cutoff: string | null,
): string | null {
  if (
    !actualStartDate
    || !isIsoLocalDate(actualStartDate)
    || !planned?.isValid
    || !planned.plannedFinishDate
    || !cutoff
    || actualStartDate > cutoff
  ) {
    return null;
  }
  const boundedPlannedFinish = planned.plannedFinishDate <= cutoff ? planned.plannedFinishDate : cutoff;
  return boundedPlannedFinish >= actualStartDate ? boundedPlannedFinish : actualStartDate;
}

export function applyActualDateStatusDefaults<T extends ActualDateEntry>(
  entry: T,
  status: ActualDateTaskStatus,
  planned: PlannedTaskDates | undefined,
  statusDate: string,
  today: string = formatLocalDate(),
  currentSuggestion: ActualDateSuggestionState = emptySuggestion,
): ActualDateDefaultResult<T> {
  let actualStartDate = entry.actual_start_date || null;
  let actualFinishDate = entry.actual_finish_date || null;
  let suggestion = { ...emptySuggestion, ...currentSuggestion };

  if (status === "not_started") {
    return {
      entry: {
        ...entry,
        status,
        actual_start_date: null,
        actual_finish_date: null,
      } as T,
      suggestion: { ...emptySuggestion },
    };
  }

  if (status !== "completed") {
    actualFinishDate = null;
    suggestion.actualFinishSuggested = false;
  }

  if (status === "cancelled") {
    return {
      entry: {
        ...entry,
        status,
        actual_start_date: actualStartDate,
        actual_finish_date: actualFinishDate,
      } as T,
      suggestion: {
        actualStartSuggested: Boolean(actualStartDate && suggestion.actualStartSuggested),
        actualFinishSuggested: false,
      },
    };
  }

  const cutoff = dateCutoff(statusDate, today);
  if (!actualStartDate) {
    const proposedStart = proposedActualStart(planned, cutoff);
    if (proposedStart) {
      actualStartDate = proposedStart;
      suggestion.actualStartSuggested = true;
    } else {
      suggestion.actualStartSuggested = false;
    }
  }

  if (status === "completed" && !actualFinishDate) {
    const proposedFinish = proposedActualFinish(actualStartDate, planned, cutoff);
    if (proposedFinish) {
      actualFinishDate = proposedFinish;
      suggestion.actualFinishSuggested = true;
    } else {
      suggestion.actualFinishSuggested = false;
    }
  }

  return {
    entry: {
      ...entry,
      status,
      actual_start_date: actualStartDate,
      actual_finish_date: actualFinishDate,
    } as T,
    suggestion,
  };
}

export function markActualDateFieldManual(
  suggestion: ActualDateSuggestionState | undefined,
  field: "actual_start_date" | "actual_finish_date",
): ActualDateSuggestionState {
  const next = { ...emptySuggestion, ...suggestion };
  if (field === "actual_start_date") next.actualStartSuggested = false;
  else next.actualFinishSuggested = false;
  return next;
}

export function recomputeSuggestedActualDates<T extends ActualDateEntry>(
  entry: T,
  suggestion: ActualDateSuggestionState,
  planned: PlannedTaskDates | undefined,
  statusDate: string,
  today: string = formatLocalDate(),
): ActualDateDefaultResult<T> {
  if (!suggestion.actualStartSuggested && !suggestion.actualFinishSuggested) {
    return { entry, suggestion };
  }
  const cutoff = dateCutoff(statusDate, today);
  if (!cutoff || !planned?.isValid) return { entry, suggestion };

  let actualStartDate = entry.actual_start_date || null;
  let actualFinishDate = entry.actual_finish_date || null;
  if (suggestion.actualStartSuggested) {
    actualStartDate = proposedActualStart(planned, cutoff);
  }
  if (suggestion.actualFinishSuggested) {
    actualFinishDate = proposedActualFinish(actualStartDate, planned, cutoff);
  }

  return {
    entry: {
      ...entry,
      actual_start_date: actualStartDate,
      actual_finish_date: actualFinishDate,
    } as T,
    suggestion,
  };
}
