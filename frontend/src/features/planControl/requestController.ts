export type PlanControlRequestState = "loading" | "saving" | "forecast" | "adjustments" | "adopting";

export async function executePlanControlRequest<T>(
  state: PlanControlRequestState,
  setState: (state: PlanControlRequestState | null) => void,
  request: () => Promise<T>,
): Promise<T> {
  setState(state);
  try {
    return await request();
  } finally {
    setState(null);
  }
}
