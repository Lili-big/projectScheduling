import type { CSSProperties } from "react";
import { createPortal } from "react-dom";
import type { LogicRule, PrecedenceLink, Task } from "../../types/scheduler";

export type PredecessorDetail = {
  predecessorId: string;
  predecessor?: Task;
  predecessorSideLabel?: string;
  link?: PrecedenceLink;
  rule?: LogicRule;
};

export function PredecessorPopover({
  task,
  details,
  anchorRect,
  onMouseEnter,
  onMouseLeave,
}: {
  task: Task;
  details: PredecessorDetail[];
  anchorRect: DOMRect | null;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}) {
  if (typeof document === "undefined") return null;

  return createPortal(
    <div
      className="predecessor-popover"
      style={predecessorPopoverStyle(anchorRect)}
      onPointerDown={(event) => event.stopPropagation()}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      {details.length ? (
        <div className="predecessor-list">
          {details.map((detail) => (
            <div className="predecessor-item" key={`${task.id}-${detail.predecessorId}-${detail.link?.id ?? "missing"}`}>
              <div className="predecessor-item-title">
                {detail.predecessorSideLabel && detail.predecessorSideLabel !== "-" && (
                  <span className="side-tag mini">{detail.predecessorSideLabel}</span>
                )}
                <strong>{detail.predecessor?.name ?? detail.predecessorId}</strong>
                {detail.link && <span className="predecessor-relation-token">{formatPrecedenceToken(detail.link)}</span>}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="predecessor-empty">这个工作项可以直接作为起始工作安排。</div>
      )}
    </div>,
    document.body,
  );
}

export function clearPredecessorHoverTimer(timerRef: { current: number | null }) {
  if (timerRef.current === null) return;
  window.clearTimeout(timerRef.current);
  timerRef.current = null;
}

export function clearPredecessorHoverTimers(
  openTimerRef: { current: number | null },
  closeTimerRef: { current: number | null },
) {
  clearPredecessorHoverTimer(openTimerRef);
  clearPredecessorHoverTimer(closeTimerRef);
}

function predecessorPopoverStyle(anchorRect: DOMRect | null): CSSProperties {
  if (typeof window === "undefined") return {};
  const margin = 12;
  const width = Math.min(360, Math.max(280, window.innerWidth - margin * 2));
  const maxHeight = Math.min(360, Math.max(180, window.innerHeight - margin * 2));
  const fallbackTop = Math.min(96, Math.max(margin, window.innerHeight - maxHeight - margin));

  if (!anchorRect) {
    return {
      top: fallbackTop,
      left: Math.max(margin, window.innerWidth - width - 24),
      width,
      maxHeight,
    };
  }

  const preferredLeft = anchorRect.right - width;
  const left = Math.min(
    Math.max(margin, preferredLeft),
    Math.max(margin, window.innerWidth - width - margin),
  );
  const belowTop = anchorRect.bottom + 8;
  const shouldOpenAbove = belowTop + Math.min(maxHeight, 240) > window.innerHeight - margin
    && anchorRect.top > window.innerHeight / 2;
  const top = shouldOpenAbove
    ? Math.max(margin, anchorRect.top - maxHeight - 8)
    : Math.min(belowTop, Math.max(margin, window.innerHeight - 140));

  return { top, left, width, maxHeight };
}

function formatPrecedenceToken(link?: PrecedenceLink): string {
  if (!link) return "-";
  return `${link.relationship}+${link.lag_days}`;
}
