import type { ReactNode } from "react";
import type { MetricTone } from "../../domain/scheduleDerived";

export function Metric({
  label,
  value,
  tone,
  hint,
  icon,
}: {
  label: string;
  value: string;
  tone: MetricTone;
  hint?: string;
  icon: ReactNode;
}) {
  return (
    <div className={`metric ${tone}`}>
      <div className="metric-icon">{icon}</div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        {hint && <small>{hint}</small>}
      </div>
    </div>
  );
}
