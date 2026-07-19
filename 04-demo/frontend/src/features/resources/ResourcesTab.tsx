import { AlertCircle, CheckCircle2, Loader2, Plus, Save, Trash2, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { PanelTitle } from "../../components/common/PanelTitle";
import type { GeneratedScheduleInput, ProjectMasterWorkpoint, ResourcePool, ScenarioInput } from "../../contracts";
import {
  localResourcePoolsForWorkpoint,
  normalizeResourcePoolForWorkspace,
  resourceCatalogProjection,
  resourcePoolQuantity,
  resourcePoolUsableLimit,
  sharedResourcePools,
  type ResourceCatalogItem,
} from "../../domain/resources";
import "./styles.css";

export type ResourceWorkpointState =
  | { status: "loading"; versionId: string }
  | { status: "error"; versionId: string; message: string }
  | { status: "ready"; versionId: string; workpoints: ProjectMasterWorkpoint[] };

type Props = {
  scenario: ScenarioInput;
  generated: GeneratedScheduleInput | null;
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
  generated,
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
  const catalog = useMemo(
    () => resourceCatalogProjection(scenario.process_library, scenario.resource_pools),
    [scenario.process_library, scenario.resource_pools],
  );
  const sharedPools = useMemo(() => sharedResourcePools(scenario.resource_pools), [scenario.resource_pools]);
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

  const taskLikelyTypes = new Set((generated?.schedule_input.tasks ?? [])
    .filter((task) => task.bridge_id === selectedWorkpoint?.workpoint_id)
    .flatMap((task) => task.compatible_resource_types));
  const likelyTypes = taskLikelyTypes.size > 0
    ? taskLikelyTypes
    : new Set(catalog.filter((item) => item.applicableProcessIds.length > 0).map((item) => item.type));
  const visibleLocalCatalog = catalog.filter((item) => likelyTypes.has(item.type) || localPools.some((pool) => pool.type === item.type));
  const supplementalCatalog = catalog.filter((item) => !visibleLocalCatalog.some((candidate) => candidate.type === item.type));
  const [supplementType, setSupplementType] = useState("");
  const [newSharedType, setNewSharedType] = useState("");
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
      max_quantity: Math.max(quantity, Number(patch.max_quantity ?? item.defaultMaxQuantity)),
      enabled: patch.enabled ?? true,
      authorized_workpoint_ids: null,
      workpoint_overrides: [],
      calendar_id: item.defaultCalendarId,
      compatible_process_ids: item.applicableProcessIds,
    }));
  }

  function addSharedPool() {
    const item = catalog.find((candidate) => candidate.type === newSharedType) ?? catalog[0];
    if (!item) return;
    const poolId = freshSharedPoolId(item.type, scenario.resource_pools);
    onAddResourcePool(normalizeResourcePoolForWorkspace({
      id: poolId,
      type: item.type,
      label: `${item.label}共享池 ${sharedPools.filter((pool) => pool.type === item.type).length + 1}`,
      resource_mode: "LIMITED",
      scope_mode: "PROJECT_SHARED",
      workpoint_id: null,
      quantity: 0,
      max_quantity: Math.max(0, item.defaultMaxQuantity),
      enabled: true,
      authorized_workpoint_ids: null,
      workpoint_overrides: [],
      calendar_id: item.defaultCalendarId,
      compatible_process_ids: item.applicableProcessIds,
    }));
  }

  return (
    <section className="panel full resource-scope-panel" data-resource-version={scenario.project_data_version_id ?? ""}>
      <PanelTitle
        title="工点资源与共享池"
        subtitle="按工点维护本地投入；共享资源在独立区域按池维护"
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
              <div className="resource-workpoint-table-wrap">
                <table className="resource-workpoint-table">
                  <thead><tr><th>资源</th><th>当前投入</th><th>可增上限</th><th>状态</th><th>操作</th></tr></thead>
                  <tbody>
                    {visibleLocalCatalog.map((item) => {
                      const pool = localPools.find((candidate) => candidate.type === item.type);
                      const quantity = pool ? resourcePoolQuantity(pool) : 0;
                      const maxQuantity = pool ? resourcePoolUsableLimit(pool) : Math.max(0, item.defaultMaxQuantity);
                      return <tr key={item.type} data-workpoint-id={selectedWorkpoint.workpoint_id} data-resource-pool={pool?.id ?? "catalog"}>
                        <td><strong>{pool?.label ?? item.label}</strong><code>{item.type}</code>{!pool && <small>任务可能使用，尚未配置</small>}</td>
                        <td><input type="number" min={0} value={quantity} aria-label={`${selectedWorkpoint.workpoint_name} ${item.label} 当前投入`} onChange={(event) => addLocalResource(item, { quantity: Math.max(0, Math.trunc(Number(event.target.value))), max_quantity: Math.max(maxQuantity, Number(event.target.value)) })} /></td>
                        <td><input type="number" min={quantity} value={maxQuantity} aria-label={`${selectedWorkpoint.workpoint_name} ${item.label} 可增上限`} onChange={(event) => addLocalResource(item, { max_quantity: Math.max(quantity, Math.trunc(Number(event.target.value))) })} /></td>
                        <td><label className="resource-status-toggle"><input type="checkbox" checked={pool?.enabled ?? false} onChange={(event) => addLocalResource(item, { enabled: event.target.checked })} /><span className={pool?.enabled ? "resource-status enabled" : "resource-status disabled"}>{pool?.enabled ? <CheckCircle2 size={14} /> : <XCircle size={14} />}{pool?.enabled ? "已启用" : "未启用"}</span></label></td>
                        <td>{pool ? <button className="secondary" type="button" onClick={() => onRemoveResourcePool(pool.id)}><Trash2 size={14} />移除</button> : <button className="secondary" type="button" onClick={() => addLocalResource(item)}><Plus size={14} />添加</button>}</td>
                      </tr>;
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}

      {workpointState.status === "ready" && (
        <section className="resource-shared-section">
          <header className="resource-section-heading"><div><h3>范围共享资源池</h3><p>同类型可建立多个独立池；实例互斥，转场时间 0 天、转场成本 0，顺序由求解器确定。</p></div><div className="resource-shared-add"><select aria-label="新增共享池资源类型" value={newSharedType} onChange={(event) => setNewSharedType(event.target.value)}><option value="">选择资源类型</option>{catalog.map((item) => <option value={item.type} key={item.type}>{item.label}</option>)}</select><button className="secondary" type="button" disabled={!catalog.length} onClick={addSharedPool}><Plus size={14} />新增共享池</button></div></header>
          <div className="resource-scope-list">
            {sharedPools.map((pool) => <SharedPoolCard key={pool.id} pool={pool} workpoints={currentWorkpoints} catalog={catalog} onPatch={(patch) => onUpsertResourcePool(pool.id, patch)} onRemove={() => onRemoveResourcePool(pool.id)} />)}
            {!sharedPools.length && <div className="resource-scope-state empty">尚未配置共享池；工点本地资源仍可独立保存和使用。</div>}
          </div>
        </section>
      )}
    </section>
  );
}

function SharedPoolCard({ pool, workpoints, catalog, onPatch, onRemove }: { pool: ResourcePool; workpoints: ProjectMasterWorkpoint[]; catalog: ResourceCatalogItem[]; onPatch: (patch: Partial<ResourcePool>) => void; onRemove: () => void }) {
  const quantity = resourcePoolQuantity(pool);
  const maxQuantity = resourcePoolUsableLimit(pool);
  const allWorkpoints = pool.authorized_workpoint_ids === null;
  const selected = new Set(pool.authorized_workpoint_ids ?? []);
  return <article className="resource-scope-card" data-resource-pool={pool.id}>
    <header className="resource-scope-card-header"><label>共享池名称<input value={pool.label} onChange={(event) => onPatch({ label: event.target.value })} /></label><code>{pool.id}</code><button className="secondary" type="button" onClick={onRemove}><Trash2 size={14} />删除共享池</button></header>
    <div className="resource-scope-defaults">
      <label>资源类型<select value={pool.type} onChange={(event) => { const item = catalog.find((candidate) => candidate.type === event.target.value); onPatch({ type: event.target.value, compatible_process_ids: item?.applicableProcessIds ?? [] }); }}>{catalog.map((item) => <option value={item.type} key={item.type}>{item.label}</option>)}</select></label>
      <label>当前投入<input type="number" min={0} value={quantity} onChange={(event) => { const next = Math.max(0, Math.trunc(Number(event.target.value))); onPatch({ quantity: next, max_quantity: Math.max(maxQuantity, next) }); }} /></label>
      <label>可增上限<input type="number" min={quantity} value={maxQuantity} onChange={(event) => onPatch({ max_quantity: Math.max(quantity, Math.trunc(Number(event.target.value))) })} /></label>
      <label className="resource-status-toggle"><input type="checkbox" checked={pool.enabled} onChange={(event) => onPatch({ enabled: event.target.checked })} /><span className={pool.enabled ? "resource-status enabled" : "resource-status disabled"}>{pool.enabled ? "已启用" : "已停用"}</span></label>
    </div>
    <div className="resource-shared-range">
      <label className="resource-all-workpoints"><input type="checkbox" checked={allWorkpoints} onChange={(event) => onPatch({ authorized_workpoint_ids: event.target.checked ? null : [] })} />全部工点（动态）</label>
      {!allWorkpoints && <div className="resource-workpoint-options">{workpoints.map((workpoint) => <label key={workpoint.workpoint_id}><input type="checkbox" aria-label={`${pool.label} 可流转至 ${workpoint.workpoint_name}`} checked={selected.has(workpoint.workpoint_id)} onChange={(event) => { const next = event.target.checked ? [...selected, workpoint.workpoint_id] : [...selected].filter((id) => id !== workpoint.workpoint_id); onPatch({ authorized_workpoint_ids: Array.from(new Set(next)).sort() }); }} />{workpoint.workpoint_name}</label>)}</div>}
      {!allWorkpoints && selected.size === 0 && <div className="resource-inline-error" role="alert">共享池至少选择一个可流转工点，或选择全部工点。</div>}
    </div>
    <div className="resource-shared-notice" role="note">共享实例互斥流转；转场时间 0 天、转场成本 0，页面不配置人工顺序。</div>
  </article>;
}

function localPoolId(workpointId: string, resourceType: string): string {
  return `workpoint-${encodeURIComponent(workpointId)}-${encodeURIComponent(resourceType)}`;
}

function freshSharedPoolId(resourceType: string, pools: ResourcePool[]): string {
  const prefix = `shared-${encodeURIComponent(resourceType)}`;
  let index = pools.filter((pool) => pool.id.startsWith(prefix)).length + 1;
  while (pools.some((pool) => pool.id === `${prefix}-${index}`)) index += 1;
  return `${prefix}-${index}`;
}
