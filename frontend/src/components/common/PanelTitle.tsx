import type { ReactNode } from "react";

export function PanelTitle({ title, subtitle, action }: { title: string; subtitle: string; action?: ReactNode }) {
  return (
    <div className="panel-title">
      <div>
        <h2>{title}</h2>
        <span>{subtitle}</span>
      </div>
      {action && <div className="panel-title-action">{action}</div>}
    </div>
  );
}
