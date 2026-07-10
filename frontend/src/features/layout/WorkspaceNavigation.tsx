import {
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  Database,
  Flag,
  Files,
  PanelLeftClose,
  PanelLeftOpen,
  Server,
  Workflow,
  X,
} from "lucide-react";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import type { TabKey } from "../../types/scheduler";

type NavigationItem = { key: TabKey; label: string; icon: ReactNode };
type NavigationGroup = { key: "projectParameters" | "prePlanning"; label: string; items: NavigationItem[] };

const navigationGroups: NavigationGroup[] = [
  {
    key: "projectParameters",
    label: "项目基本参数",
    items: [
      { key: "projectFiles", label: "项目文件", icon: <Files size={15} /> },
      { key: "process", label: "工艺工效库", icon: <Database size={15} /> },
      { key: "logic", label: "工艺逻辑", icon: <Workflow size={15} /> },
      { key: "resources", label: "资源配置", icon: <Server size={15} /> },
      { key: "tasks", label: "任务视图", icon: <ClipboardList size={15} /> },
      { key: "milestones", label: "里程碑", icon: <Flag size={15} /> },
    ],
  },
  {
    key: "prePlanning",
    label: "前期策划",
    items: [
      { key: "resourceAssistant", label: "AI多方案比选", icon: <Bot size={15} /> },
      { key: "results", label: "模拟求解", icon: <CheckCircle2 size={15} /> },
    ],
  },
];

const tabs = navigationGroups.flatMap((group) => group.items);

export function SideNavigation({
  activeTab,
  openTabs,
  onOpen,
  collapsed,
  onToggleCollapsed,
}: {
  activeTab: TabKey | null;
  openTabs: TabKey[];
  onOpen: (tabKey: TabKey) => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
}) {
  const [expandedGroups, setExpandedGroups] = useState<Record<NavigationGroup["key"], boolean>>({
    projectParameters: true,
    prePlanning: true,
  });
  const visibleGroups = useMemo(
    () => navigationGroups.map((group) => ({ ...group, expanded: expandedGroups[group.key] })),
    [expandedGroups],
  );

  function toggleGroup(groupKey: NavigationGroup["key"]) {
    setExpandedGroups((current) => ({ ...current, [groupKey]: !current[groupKey] }));
  }

  return (
    <aside className={`side-nav ${collapsed ? "collapsed" : ""}`}>
      <div className="side-nav-section">
        <div className="side-nav-header">
          {!collapsed && <div className="side-nav-heading">功能导航</div>}
          <button
            className="side-nav-toggle"
            type="button"
            aria-label={collapsed ? "展开功能导航" : "折叠功能导航"}
            title={collapsed ? "展开功能导航" : "折叠功能导航"}
            onClick={onToggleCollapsed}
          >
            {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
          </button>
        </div>
        {visibleGroups.map((group) => (
          <div className="side-nav-group" key={group.key}>
            {!collapsed && (
              <button
                className="side-nav-group-toggle"
                type="button"
                aria-expanded={group.expanded}
                onClick={() => toggleGroup(group.key)}
              >
                {group.expanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                <span>{group.label}</span>
              </button>
            )}
            {(collapsed || group.expanded) && (
              <div className="side-nav-group-items">
                {group.items.map((tab) => (
                  <button
                    key={tab.key}
                    className={`side-nav-item ${activeTab === tab.key ? "active" : ""}`}
                    type="button"
                    title={collapsed ? tab.label : undefined}
                    onClick={() => onOpen(tab.key)}
                  >
                    <span className="side-nav-icon">{tab.icon}</span>
                    <span className="side-nav-label">{tab.label}</span>
                    {openTabs.includes(tab.key) && <span className="side-nav-dot" />}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </aside>
  );
}

export function WorkspaceTabStrip({
  openTabs,
  activeTab,
  onSelect,
  onClose,
}: {
  openTabs: TabKey[];
  activeTab: TabKey | null;
  onSelect: (tabKey: TabKey) => void;
  onClose: (tabKey: TabKey) => void;
}) {
  return (
    <div className="workspace-tabs" role="tablist" aria-label="已打开模块">
      {openTabs.map((tabKey) => {
        const tab = tabs.find((item) => item.key === tabKey);
        if (!tab) return null;

        return (
          <div className={`workspace-tab ${activeTab === tabKey ? "active" : ""}`} key={tab.key}>
            <button className="workspace-tab-main" type="button" onClick={() => onSelect(tab.key)}>
              {tab.icon}
              <span>{tab.label}</span>
            </button>
            <button
              className="workspace-tab-close"
              type="button"
              aria-label={`关闭${tab.label}`}
              onClick={() => onClose(tab.key)}
            >
              <X size={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
