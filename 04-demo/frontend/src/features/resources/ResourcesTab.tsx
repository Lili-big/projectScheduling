import { AlertCircle, CheckCircle2, Loader2, Plus, Save, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { getProjectMasterWorkpoint } from "../../api/projectMasterApi";
import { initializeAiWorkpointResources } from "../../api/resourceAssistantApi";
import { PanelTitle } from "../../components/common/PanelTitle";
import type {
  AiWorkpointResourceInitializationResponse,
  ProjectMasterWorkpoint,
  ResourcePool,
  ScenarioInput,
} from "../../contracts";
import {
  localResourcePoolsForWorkpoint,
  normalizeResourcePoolForWorkspace,
  resourceCatalogProjection,
  resourcePoolsSemanticFingerprint,
  resourcePoolQuantity,
  resourcePoolUsableLimit,
  resourceTypeLabel,
  workpointResourceTypeProjection,
  workpointStructureSummaryProjection,
  type ResourceCatalogItem,
} from "../../domain/resources";
import "./styles.css";
import { newPavementFleet, pavementFleetErrors, togglePavementFleetProcess } from "../../domain/pavement";

export type ResourceWorkpointState =
  | { status: "loading"; versionId: string }
  | { status: "error"; versionId: string; message: string }
  | { status: "ready"; versionId: string; workpoints: ProjectMasterWorkpoint[] };

type ResourceWorkpointDetailState =
  | { status: "idle" }
  | { status: "loading"; versionId: string; workpointId: string }
  | { status: "error"; versionId: string; workpointId: string; message: string }
  | { status: "ready"; versionId: string; workpointId: string; workpoint: ProjectMasterWorkpoint };

export function PavementResources({ scenario, onChange, onSave, saving }: {
  scenario: ScenarioInput; onChange: (pools: ResourcePool[]) => void; onSave: () => void; saving: boolean;
}) {
  const patch = (id: string, values: Partial<ResourcePool>) => onChange(scenario.resource_pools.map(p => p.id === id ? { ...p, ...values } : p));
  const errors = pavementFleetErrors(scenario);
  return <section className="panel full pavement-fleets"><PanelTitle title="路面关键机组" subtitle="同一套机组可承担多种工艺，同一时间只施工一个任务。" action={<button disabled={saving || errors.length > 0} onClick={onSave}>{saving ? "正在保存…" : "保存配置"}</button>} />
    <div className="pavement-fleet-toolbar"><span>养生不占机组；同段同幅换层不转场，跨段/幅按实际作业顺序转场。</span><button disabled={saving} onClick={() => onChange([...scenario.resource_pools, newPavementFleet(crypto.randomUUID())])}>新增机组</button></div>
    {errors.length > 0 && <ul className="pavement-fleet-errors" role="alert">{errors.map((error, i) => <li key={i}>{error}</li>)}</ul>}
    <fieldset disabled={saving}><div className="table-wrap"><table><thead><tr><th>机组名称</th><th>适用工艺（可多选）</th><th>数量（套）</th><th>跨段转场（天）</th><th>适用工点</th><th>状态</th></tr></thead><tbody>
      {scenario.resource_pools.map(pool => <tr key={pool.id}><td><input className="pavement-fleet-name" aria-label={`${pool.label}名称`} value={pool.label} onChange={e => patch(pool.id, {label:e.target.value})} /></td>
        <td><div className="pavement-fleet-processes">{scenario.process_library.map(process => <label key={process.id}><input type="checkbox" aria-label={`${pool.label}适用${process.process_name}`} checked={pool.compatible_process_ids.includes(process.id)} onChange={e => patch(pool.id, togglePavementFleetProcess(pool, process.id, e.target.checked))} />{process.process_name}</label>)}
          {pool.compatible_process_ids.filter(id => !scenario.process_library.some(p => p.id === id)).map(id => <label key={id}><input type="checkbox" checked onChange={() => patch(pool.id,togglePavementFleetProcess(pool,id,false))} />失效工艺（{id}）</label>)}
        </div></td>
        <td><input aria-label={`${pool.label}数量`} type="number" min="0" step="1" value={pool.quantity ?? 0} onChange={e => patch(pool.id,{quantity:Number(e.target.value),max_quantity:Number(e.target.value),resource_mode:"LIMITED"})} /></td>
        <td><input aria-label={`${pool.label}转场天数`} type="number" min="0" step="1" placeholder="待确认" value={pool.transfer_days ?? ""} onChange={e => patch(pool.id,{transfer_days:e.target.value === "" ? null : Number(e.target.value)})} /></td>
        <td><label><input type="checkbox" checked={pool.authorized_workpoint_ids == null} onChange={e => patch(pool.id,{authorized_workpoint_ids:e.target.checked ? null : []})} />全部路面工点共享</label>
          {pool.authorized_workpoint_ids != null && scenario.project.bridges.map(w => <label key={w.id}><input type="checkbox" checked={pool.authorized_workpoint_ids?.includes(w.id)} onChange={e => patch(pool.id,{authorized_workpoint_ids:e.target.checked ? [...pool.authorized_workpoint_ids!,w.id] : pool.authorized_workpoint_ids!.filter(id=>id!==w.id)})} />{w.name}</label>)}</td>
        <td><label><input type="checkbox" checked={pool.enabled} onChange={e=>patch(pool.id,{enabled:e.target.checked})} />启用</label>{!pool.quantity && <small>无可用机组</small>}</td>
      </tr>)}
    </tbody></table></div></fieldset>
    {!scenario.resource_pools.length && <p>尚未配置机组，请新增机组并选择适用工艺。</p>}
  </section>;
}

type AiInitializationState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; response: AiWorkpointResourceInitializationResponse }
  | { status: "error"; message: string };

type Props = {
  scenario: ScenarioInput;
  workpointState: ResourceWorkpointState;
  onRetryWorkpoints: () => void;
  onUpsertResourcePool: (poolId: string, patch: Partial<ResourcePool>) => void;
  onAddResourcePool: (pool: ResourcePool) => void;
  onRemoveResourcePool: (poolId: string) => void;
  onApplyAiWorkpointResources: (
    response: AiWorkpointResourceInitializationResponse,
    requestVersionId: string,
    requestResourceFingerprint: string,
  ) => void;
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
  onApplyAiWorkpointResources,
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
  const aiRequestRef = useRef(0);
  const aiRequestInFlightRef = useRef(false);
  const scenarioRef = useRef(scenario);
  scenarioRef.current = scenario;
  const [aiInitializationState, setAiInitializationState] = useState<AiInitializationState>({ status: "idle" });
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
  const structureSummaries = useMemo(
    () => currentDetailState?.status === "ready"
      ? workpointStructureSummaryProjection(currentDetailState.workpoint, scenario.process_library)
      : [],
    [currentDetailState, scenario.process_library],
  );
  const visibleLocalCatalog = catalog.filter((item) => (
    matchedResourceTypes.has(item.type) || localPools.some((pool) => pool.type === item.type)
  ));
  const supplementalCatalog = catalog.filter((item) => !visibleLocalCatalog.some((candidate) => candidate.type === item.type));
  const [supplementType, setSupplementType] = useState("");
  const saveLabel = saveError ? "重试保存" : "保存";

  useEffect(() => {
    aiRequestRef.current += 1;
    aiRequestInFlightRef.current = false;
    setAiInitializationState({ status: "idle" });
  }, [scenario.project_data_version_id]);

  async function initializeAllWorkpointResources() {
    const versionId = scenario.project_data_version_id ?? "";
    if (
      aiRequestInFlightRef.current
      || !versionId
      || workpointState.status !== "ready"
      || workpointState.versionId !== versionId
      || currentWorkpoints.length === 0
    ) return;
    aiRequestInFlightRef.current = true;
    const requestId = ++aiRequestRef.current;
    const requestResourceFingerprint = resourcePoolsSemanticFingerprint(scenario.resource_pools);
    setAiInitializationState({ status: "loading" });
    try {
      const response = await initializeAiWorkpointResources({ scenario });
      if (requestId !== aiRequestRef.current) return;
      const latestScenario = scenarioRef.current;
      if (
        response.project_data_version_id !== versionId
        || (latestScenario.project_data_version_id ?? "") !== versionId
        || resourcePoolsSemanticFingerprint(latestScenario.resource_pools) !== requestResourceFingerprint
      ) {
        throw new Error("项目版本或资源配置已变化，本次 AI 推荐未应用，请重新生成。");
      }
      onApplyAiWorkpointResources(response, versionId, requestResourceFingerprint);
      setAiInitializationState({ status: "success", response });
    } catch (initializationError) {
      if (requestId !== aiRequestRef.current) return;
      setAiInitializationState({ status: "error", message: errorText(initializationError) });
    } finally {
      if (requestId === aiRequestRef.current) aiRequestInFlightRef.current = false;
    }
  }

  function addLocalResource(item: ResourceCatalogItem, patch: Partial<ResourcePool> = {}) {
    if (!selectedWorkpoint) return;
    const existing = localPools.find((pool) => pool.type === item.type);
    if (existing) {
      const quantity = Math.max(0, Math.trunc(Number(patch.quantity ?? resourcePoolQuantity(existing))));
      onUpsertResourcePool(existing.id, { ...patch, enabled: quantity > 0 });
      return;
    }
    const quantity = Math.max(0, Math.trunc(Number(patch.quantity ?? 0)));
    onAddResourcePool(normalizeResourcePoolForWorkspace({
      id: localPoolId(selectedWorkpoint.workpoint_id, item.type),
      type: item.type,
      label: item.label,
      resource_mode: "LIMITED",
      scope_mode: "WORKPOINT_EXCLUSIVE",
      workpoint_id: selectedWorkpoint.workpoint_id,
      quantity,
      max_quantity: Math.max(quantity, Number(patch.max_quantity ?? 0)),
      enabled: quantity > 0,
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
        subtitle="结合当前工点结构物汇总，维护资源的当前投入和可增上限"
        action={(
          <div className="resource-title-actions">
            <button
              className="secondary"
              type="button"
              onClick={() => void initializeAllWorkpointResources()}
              disabled={
                aiInitializationState.status === "loading"
                || savingLocalConfig
                || workpointState.status !== "ready"
                || workpointState.versionId !== (scenario.project_data_version_id ?? "")
                || currentWorkpoints.length === 0
              }
              aria-label="AI快速配置工装"
            >
              {aiInitializationState.status === "loading" ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />}
              {aiInitializationState.status === "loading" ? "AI配置中…" : "AI快速配置工装"}
            </button>
            <button className="secondary" type="button" onClick={onSaveLocalConfig} disabled={savingLocalConfig || !localConfigDirty || workpointState.status !== "ready"} aria-label={saveLabel}>
              {savingLocalConfig ? <Loader2 className="spin" size={16} /> : <Save size={16} />}{saveLabel}
            </button>
          </div>
        )}
      />

      {workpointState.status === "loading" && <div className="resource-scope-state" role="status"><Loader2 className="spin" size={18} />正在加载当前版本的权威桥梁工点…</div>}
      {workpointState.status === "error" && <div className="resource-scope-state error" role="alert"><AlertCircle size={18} /><span>{workpointState.message}</span><button className="secondary" type="button" onClick={onRetryWorkpoints}>重试</button></div>}
      {saveError && <div className="resource-scope-state error" role="alert"><AlertCircle size={18} /><span>{saveError}，请检查后重试保存。</span></div>}
      {aiInitializationState.status === "error" && <div className="resource-scope-state error" role="alert"><AlertCircle size={18} /><span>AI 工装配置失败：{aiInitializationState.message}</span></div>}
      {aiInitializationState.status === "success" && (
        <div className="resource-scope-state success" role="status" data-ai-resource-initialization="success">
          <CheckCircle2 size={18} />
          <span>
            AI 已新增 {aiInitializationState.response.summary.added_resource_count} 项资源，涉及 {aiInitializationState.response.summary.recommended_workpoint_count} 个工点；
            {aiInitializationState.response.summary.unchanged_workpoint_ids.length} 个工点无需补充。
            模型：{aiInitializationState.response.llm_config_status.model ?? aiInitializationState.response.llm_config_status.provider}。配置已填入当前页面，尚未保存，请逐工点确认后点击“保存”。
          </span>
        </div>
      )}
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
              {currentDetailState?.status === "ready" && (
                <div className="resource-workpoint-detail-grid">
                  <section className="resource-detail-panel resource-structure-panel" aria-labelledby="resource-structure-heading">
                    <header className="resource-detail-heading">
                      <h4 id="resource-structure-heading">结构物信息</h4>
                      <p>按结构参数、施工工艺和单位汇总，仅供配置资源时估算参考。</p>
                    </header>
                    {structureSummaries.length === 0 ? (
                      <div className="resource-detail-empty" data-structure-summary-empty="true">当前工点没有可汇总的下部结构信息。</div>
                    ) : (
                      <div className="resource-structure-groups">
                        {structureSummaries.map((group) => (
                          <section className="resource-structure-group" key={group.componentType}>
                            <h5>{group.label}</h5>
                            <ul>{group.items.map((item) => <li key={item.signature}>{item.displayText}</li>)}</ul>
                          </section>
                        ))}
                      </div>
                    )}
                  </section>

                  <section className="resource-detail-panel resource-config-panel" aria-labelledby="resource-config-heading">
                    <header className="resource-detail-heading">
                      <h4 id="resource-config-heading">资源配置</h4>
                      <p>数量 0 表示当前没有该资源，输入正数后自动生效。</p>
                    </header>
                    {visibleLocalCatalog.length === 0 ? (
                      <div className="resource-detail-empty" data-resource-suggestion-empty="true">当前工点没有匹配到待配置资源，可从完整资源目录补充。</div>
                    ) : (
                      <div className="resource-config-list">
                        {visibleLocalCatalog.map((item) => {
                          const pool = localPools.find((candidate) => candidate.type === item.type);
                          const quantity = pool ? resourcePoolQuantity(pool) : 0;
                          const maxQuantity = pool ? resourcePoolUsableLimit(pool) : 0;
                          const label = resourceTypeLabel(item.type, pool ? [pool] : []);
                          return (
                            <article className="resource-config-item" key={item.type} data-workpoint-id={selectedWorkpoint.workpoint_id} data-resource-pool={pool?.id ?? "catalog"}>
                              <div className="resource-config-name"><strong>{label}</strong>{!pool && <small>结构可能使用，尚未配置</small>}</div>
                              <div className="resource-config-controls">
                                <input type="number" min={0} value={quantity} title="当前投入" aria-label={`${selectedWorkpoint.workpoint_name} ${label} 当前投入`} onChange={(event) => { const nextQuantity = Math.max(0, Math.trunc(Number(event.target.value))); addLocalResource(item, { quantity: nextQuantity, max_quantity: Math.max(maxQuantity, nextQuantity), enabled: nextQuantity > 0 }); }} />
                                <input type="number" min={quantity} value={maxQuantity} title="可增上限" aria-label={`${selectedWorkpoint.workpoint_name} ${label} 可增上限`} onChange={(event) => addLocalResource(item, { max_quantity: Math.max(quantity, Math.trunc(Number(event.target.value))) })} />
                                {pool ? <button className="secondary" type="button" onClick={() => onRemoveResourcePool(pool.id)}><Trash2 size={14} />移除</button> : <button className="secondary" type="button" onClick={() => addLocalResource(item)}><Plus size={14} />添加</button>}
                              </div>
                            </article>
                          );
                        })}
                      </div>
                    )}
                  </section>
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
