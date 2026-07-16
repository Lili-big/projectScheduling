import type { ReactNode } from "react";

export function ScheduleResultsWorkspace({ children }: { children: ReactNode }) {
  return <div className="results-grid">{children}</div>;
}
