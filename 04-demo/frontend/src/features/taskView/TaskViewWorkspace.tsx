import type { ReactNode } from "react";

type TaskViewWorkspaceProps = {
  children: ReactNode;
  displayStatus?: "loading" | "ready" | "error";
  onRetry?: () => void;
};

export function TaskViewWorkspace({
  children,
  displayStatus = "ready",
  onRetry,
}: TaskViewWorkspaceProps) {
  if (displayStatus === "loading") {
    return (
      <div className="task-view-grid">
        <section className="panel full">
          <div className="task-view-empty" role="status">
            <strong>正在加载权威项目主数据</strong>
            <span>全部工点名称就绪后将一次性展示任务清单。</span>
          </div>
        </section>
      </div>
    );
  }

  if (displayStatus === "error") {
    return (
      <div className="task-view-grid">
        <section className="panel full">
          <div className="task-view-empty" role="alert">
            <strong>权威项目主数据暂不可用</strong>
            <span>任务数据已保留，请重试加载名称映射。</span>
            <button className="secondary" type="button" onClick={onRetry}>重试</button>
          </div>
        </section>
      </div>
    );
  }

  return <div className="task-view-grid">{children}</div>;
}
