import type { ReactNode } from "react";

export function TaskViewWorkspace({ children }: { children: ReactNode }) {
  return <div className="task-view-grid">{children}</div>;
}
