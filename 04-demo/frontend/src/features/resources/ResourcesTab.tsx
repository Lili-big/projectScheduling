import { AlertCircle, CheckCircle2, Loader2, Plus, Save, Trash2, XCircle } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { getProjectMasterWorkpoint } from "../../api/projectMasterApi";
import { PanelTitle } from "../../components/common/PanelTitle";
import type { ProjectMasterWorkpoint, ResourcePool, ScenarioInput } from "../../contracts";
import {
  localResourcePoolsForWorkpoint,
  normalizeResourcePoolForWorkspace,
  resourceCatalogProjection,
  resourcePoolQuantity,
  resourcePoolUsableLimit,
  resourceTypeLabel,
  workpointResourceTypeProjection,
  type ResourceCatalogItem,
} from "../../domain/resources";
import "./styles.css";

export type ResourceWorkpointState =
  | { status: "loading"; versionId: string }
  | { status: "error"; versionId: string; message: string }
  | { status: "ready"; versionId: string; workpoints: ProjectMasterWorkpoint[] };

type ResourceWorkpointDetailState =
  | { status: "idle" }
  | { status: "loading"; versionId: string; workpointId: string }
  | { status: "error"; versionId: string; workpointId: string; message: string }
  | { status: "ready"; versionId: string; workpointId: string; workpoint: ProjectMasterWorkpoint };

type Props = {
  scenario: ScenarioInput;
  workpointState: ResourceWorkpointState;
  onRetryWorkpoints: () => void;
  onUpsertResourcePool: (poolId: string, patch: Partial<ResourcePool>) => void;
  onAddResourcePool: (pool: ResourcePool) => void;
  onRemoveResourcePool: (poolId: string) => void;
  onSaveLocalConfig: () => void;
  savingLocalConfig: boolean;
  localConfigDirty: boolean;
  saveError: string | null;
};

export function ResourcesTab({
  scenario,
  workpointState,
  onRetryWorkpoints,
  onUpsertResourcePool,
  onAddResourcePool,
  onRemoveResourcePool,
  onSaveLocalConfig,
  savingLocalConfig,
  localConfigDirty,
  saveError,
}: Props) {
  const currentWorkpoints = workpointState.status === "ready" && workpointState.versionId === scenario.project_data_version_id
    ? workpointState.workpoints
    : [];
  const [selectedWorkpointId, setSelectedWorkpointId] = useState("");
  const [detailState, setDetailState] = useState<ResourceWorkpointDetailState>({ status: "idle" });
  const [detailReloadToken, setDetailReloadToken] = useState(0);
  const detailRequestRef = useRef(0);
  const catalog = useMemo(
    () => resourceCatalogProjection(scenario.process_library, scenario.resource_pools),
    [scenario.process_library, scenario.resource_pools],
  );
  const selectedWorkpoint = currentWorkpoints.find((workpoint) => workpoint.workpoint_id === selectedWorkpointId)
    ?? currentWorkpoints[0]
    ?? null;
  const localPools = selectedWorkpoint
    ? localResourcePoolsForWorkpoint(scenario.resource_pools, selectedWorkpoint.workpoint_id)
    : [];

  useEffect(() => {
    if (!currentWorkpoints.some((item) => item.workpoint_id === selectedWorkpointId)) {
      setSelectedWorkpointId(currentWorkpoints[0]?.workpoint_id ?? "");
    }
  }, [currentWorkpoints, selectedWorkpointId]);

  useEffect(() => {
    const versionId = scenario.project_data_version_id ?? "";
    const workpointId = selectedWorkpoint?.workpoint_id ?? "";
    const detailRequestId = ++detailRequestRef.current;
    if (!versionId || !workpointId) {
      setDetailState({ status: "idle" });
      return;
    }
    setDetailState({ status: "loading", versionId, workpointId });
    void getProjectMasterWorkpoint(versionId, workpointId)
      .then((workpoint) => {
        if (detailRequestId !== detailRequestRef.current) return;
        setDetailState({ status: "ready", versionId, workpointId, workpoint });
      })
      .catch((loadError) => {
        if (detailRequestId !== detailRequestRef.current) return;
        setDetailState({ status: "error", versionId, workpointId, message: errorText(loadError) });
      });
    return () => {
      if (detailRequestId === detailRequestRef.current) detailRequestRef.current += 1;
    };
  }, [detailReloadToken, scenario.project_data_version_id, selectedWorkpoint?.workpoint_id]);

  const currentDetailState = selectedWorkpoint
    && detailState.status !== "idle"
    && detailState.versionId === scenario.project_data_version_id
    && detailState.workpointId === selectedWorkpoint.workpoint_id
    ? detailState
    : null;
  const matchedResourceTypes = useMemo(
    () => new Set(
      currentDetailState?.status === "ready"
        ? workpointResourceTypeProjection(currentDetailState.workpoint, scenario.process_library)
        : [],
    ),
    [currentDetailState, scenario.process_library],
  );
  const visibleLocalCatalog = catalog.filter((item) => (
    matchedResourceTypes.has(item.type) || localPools.some((pool) => pool.type === item.type)
  ));
  const supplementalCatalog = catalog.filter((item) => !visibleLocalCatalog.some((candidate) => candidate.type === item.type));
  const [supplementType, setSupplementType] = useState("");
  const saveLabel = saveError ? "重试保存" : "保存";

  function addLocalResource(item: ResourceCatalogItem, patch: Partial<ResourcePool> = {}) {
    if (!selectedWorkpoint) return;
    const existing = localPools.find((pool) => pool.type === item.type);
    if (existing) {
      onUpsertResourcePool(existing.id, patch);
      return;
    }
    const quantity = Math.max(0, Number(patch.quantity ?? 0));
    onAddResourcePool(normalizeResourcePoolForWorkspace({
      id: localPoolId(selectedWorkpoint.workpoint_id, item.type),
      type: item.type,
      label: item.label,
      resource_mode: "LIMITED",
      scope_mode: "WORKPOINT_EXCLUSIVE",
      workpoint_id: selectedWorkpoint.workpoint_id,
      quantity,
      max_quantity: Math.max(quantity, Number(patch.max_quantity ?? 0)),
      enabled: patch.enabled ?? true,
      authorized_workpoint_ids: null,
      workpoint_overrides: [],
      calendar_id: item.defaultCalendarId,
      compatible_process_ids: item.applicableProcessIds,
    }));
  }

  return (
    <section className="panel full resource-scope-panel" data-resource-version={scenario.project_data_version_id ?? ""}>
      <PanelTitle
        title="工点资源配置"
        subtitle="按工点维护资源的当前投入、可增上限和启用状态"
        action={(
          <button className="secondary" type="button" onClick={onSaveLocalConfig} disabled={savingLocalConfig || !localConfigDirty || workpointState.status !== "ready"} aria-label={saveLabel}>
            {savingLocalConfig ? <Loader2 className="spin" size={16} /> : <Save size={16} />}{saveLabel}
          </button>
        )}
      />

      {workpointState.status === "loading" && <div className="resource-scope-state" role="status"><Loader2 className="spin" size={18} />正在加载当前版本的权威桥梁工点…</div>}
      {workpointState.status === "error" && <div className="resource-scope-state error" role="alert"><AlertCircle size={18} /><span>{workpointState.message}</span><button className="secondary" type="button" onClick={onRetryWorkpoints}>重试</button></div>}
      {saveError && <div className="resource-scope-state error" role="alert"><AlertCircle size={18} /><span>{saveError}，请检查后重试保存。</span></div>}
      {workpointState.status === "ready" && currentWorkpoints.length === 0 && <div className="resource-scope-state empty" data-resource-empty="true">当前项目主数据版本没有桥梁工点，无法维护工点资源。</div>}

      {workpointState.status === "ready" && currentWorkpoints.length > 0 && (
        <section className="resource-workpoint-section">
          <header className="resource-section-heading"><div><h3>工点资源</h3><p>每条记录只属于当前工点，数量 0 表示当前没有该资源。</p></div></header>
          <nav className="resource-workpoint-nav" aria-label="桥梁工点">
            {currentWorkpoints.map((workpoint) => <button key={workpoint.workpoint_id} type="button" className={workpoint.workpoint_id === selectedWorkpoint?.workpoint_id ? "active" : ""} onClick={() => setSelectedWorkpointId(workpoint.workpoint_id)}>{workpoint.workpoint_name || workpoint.workpoint_id}</button>)}
          </nav>
          {selectedWorkpoint && (
            <>
              <div className="resource-catalog-add">
                <label>从资源目录补充<select value={supplementType} onChange={(event) => setSupplementType(event.target.value)}><option value="">选择资源类型</option>{supplementalCatalog.map((item) => <option value={item.type} key={item.type}>{item.label}</option>)}</select></label>
                <button className="secondary" type="button" disabled={!supplementType} onClick={() => { const item = catalog.find((candidate) => candidate.type === supplementType); if (item) addLocalResource(item); setSupplementType(""); }}><Plus size={14} />添加到当前工点</button>
              </div>

              {(!currentDetailState || currentDetailState.status === "loading") && <div className="resource-scope-state" role="status"><Loader2 className="spin" size={18} />正在加载当前工点结构…</div>}
              {currentDetailState?.status === "error" && <div className="resource-scope-state error" role="alert"><AlertCircle size={18} /><span>当前工点结构加载失败：{currentDetailState.message}</span><button className="secondary" type="button" onClick={() => setDetailReloadToken((current) => current + 1)}>重试</button></div>}
              {currentDetailState?.status === "ready" && visibleLocalCatalog.length === 0 && <div className="resource-scope-state empty" data-resource-suggestion-empty="true">当前工点没有匹配到待配置资源，可从完整资源目录补充。</div>}
              {currentDetailState?.status === "ready" && visibleLocalCatalog.length > 0 && (
                <div className="resource-workpoint-table-wrap">
                  <table className="resource-workpoint-table">
                    <thead><tr><th>资源</th><th>当前投入</th><th>可增上限</th><th>状态</th><th>操作</th></tr></thead>
                    <tbody>
                      {visibleLocalCatalog.map((item) => {
                        const pool = localPools.find((candidate) => candidate.type === item.type);
                        const quantity = pool ? resourcePoolQuantity(pool) : 0;
                        const maxQuantity = pool ? resourcePoolUsableLimit(pool) : 0;
                        const label = resourceTypeLabel(item.type, pool ? [pool] : []);
                        return <tr key={item.type} data-workpoint-id={selectedWorkpoint.workpoint_id} data-resource-pool={pool?.id ?? "catalog"}>
                          <td><strong>{label}</strong><code>{item.type}</code>{!pool && <small>结构可能使用，尚未配置</small>}</td>
                          <td><input type="number" min={0} value={quantity} aria-label={`${selectedWorkpoint.workpoint_name} ${label} 当前投入`} onChange={(event) => addLocalResource(item, { quantity: Math.max(0, Math.trunc(Number(event.target.value))), max_quantity: Math.max(maxQuantity, Number(event.target.value)) })} /></td>
                          <td><input type="number" min={quantity} value={maxQuantity} aria-label={`${selectedWorkpoint.workpoint_name} ${label} 可增上限`} onChange={(event) => addLocalResource(item, { max_quantity: Math.max(quantity, Math.trunc(Number(event.target.value))) })} /></td>
                          <td><label className="resource-status-toggle"><input type="checkbox" checked={pool?.enabled ?? false} onChange={(event) => addLocalResource(item, { enabled: event.target.checked })} /><span className={pool?.enabled ? "resource-status enabled" : "resource-status disabled"}>{pool?.enabled ? <CheckCircle2 size={14} /> : <XCircle size={14} />}{pool?.enabled ? "已启用" : "未启用"}</span></label></td>
                          <td>{pool ? <button className="secondary" type="button" onClick={() => onRemoveResourcePool(pool.id)}><Trash2 size={14} />移除</button> : <button className="secondary" type="button" onClick={() => addLocalResource(item)}><Plus size={14} />添加</button>}</td>
                        </tr>;
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </section>
      )}
    </section>
  );
}

function localPoolId(workpointId: string, resourceType: string): string {
  return `workpoint-${encodeURIComponent(workpointId)}-${encodeURIComponent(resourceType)}`;
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
