import { AlertCircle, CheckCircle2, Loader2, RotateCcw, Save, XCircle } from "lucide-react";
import { PanelTitle } from "../../components/common/PanelTitle";
import {
  effectiveWorkpointResource,
  normalizeResourcePoolForWorkspace,
  resourcePoolQuantity,
  resourceScopeLabels,
  restoreWorkpointResourceInheritance,
  setWorkpointResourceOverride,
} from "../../domain/resources";
import type { ProjectMasterWorkpoint, ResourcePool, ScenarioInput } from "../../contracts";
import "./styles.css";

export type ResourceWorkpointState =
  | { status: "loading"; versionId: string }
  | { status: "error"; versionId: string; message: string }
  | { status: "ready"; versionId: string; workpoints: ProjectMasterWorkpoint[] };

export function ResourcesTab({
  scenario,
  workpointState,
  onRetryWorkpoints,
  onUpdateResourcePool,
  onSaveLocalConfig,
  savingLocalConfig,
  localConfigDirty,
  saveError,
}: {
  scenario: ScenarioInput;
  workpointState: ResourceWorkpointState;
  onRetryWorkpoints: () => void;
  onUpdateResourcePool: (index: number, patch: Partial<ResourcePool>) => void;
  onSaveLocalConfig: () => void;
  savingLocalConfig: boolean;
  localConfigDirty: boolean;
  saveError: string | null;
}) {
  const currentWorkpoints = workpointState.status === "ready" && workpointState.versionId === scenario.project_data_version_id
    ? workpointState.workpoints
    : [];
  const saveLabel = saveError ? "重试保存" : "保存";

  return (
    <section className="panel full resource-scope-panel" data-resource-version={scenario.project_data_version_id ?? ""}>
      <PanelTitle
        title="资源方案"
        subtitle="配置项目共享或工点独享资源；未覆盖的工点继承全局默认"
        action={
          <button
            className="secondary"
            type="button"
            onClick={onSaveLocalConfig}
            disabled={savingLocalConfig || !localConfigDirty || workpointState.status !== "ready"}
            title="保存当前项目主数据版本的资源配置"
            aria-label={saveLabel}
          >
            {savingLocalConfig ? <Loader2 className="spin" size={16} /> : <Save size={16} />}
            {saveLabel}
          </button>
        }
      />

      {workpointState.status === "loading" && (
        <div className="resource-scope-state" role="status">
          <Loader2 className="spin" size={18} />
          正在加载当前版本的权威桥梁工点…
        </div>
      )}
      {workpointState.status === "error" && (
        <div className="resource-scope-state error" role="alert">
          <AlertCircle size={18} />
          <span>{workpointState.message}</span>
          <button className="secondary" type="button" onClick={onRetryWorkpoints}>重试</button>
        </div>
      )}
      {saveError && (
        <div className="resource-scope-state error" role="alert">
          <AlertCircle size={18} />
          <span>{saveError}，请检查后重试保存。</span>
        </div>
      )}
      {workpointState.status === "ready" && currentWorkpoints.length === 0 && (
        <div className="resource-scope-state empty" data-resource-empty="true">
          当前项目主数据版本没有桥梁工点，无法创建工点资源覆盖。
        </div>
      )}

      {workpointState.status === "ready" && (
        <div className="resource-scope-list">
          {scenario.resource_pools.map((rawPool, index) => {
            const pool = normalizeResourcePoolForWorkspace(rawPool);
            const quantity = resourcePoolQuantity(pool);
            const maxQuantity = Math.max(pool.max_quantity ?? quantity, quantity);
            const authorizedIds = pool.authorized_workpoint_ids;
            const authorized = new Set(authorizedIds ?? currentWorkpoints.map((workpoint) => workpoint.workpoint_id));
            return (
              <article className="resource-scope-card" key={pool.id} data-resource-pool={pool.id}>
                <header className="resource-scope-card-header">
                  <div className="resource-list-name">
                    <strong>{pool.label}</strong>
                    <code>{pool.type}</code>
                    {pool.parallel_rule_description ? (
                      <span className="resource-parallel-note">{pool.parallel_rule_description}</span>
                    ) : null}
                  </div>
                  <label className="resource-status-toggle">
                    <input
                      type="checkbox"
                      checked={pool.enabled}
                      onChange={(event) => onUpdateResourcePool(index, { enabled: event.target.checked })}
                    />
                    <span className={pool.enabled ? "resource-status enabled" : "resource-status disabled"}>
                      {pool.enabled ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                      {pool.enabled ? "可模拟" : "已停用"}
                    </span>
                  </label>
                </header>

                <div className="resource-scope-defaults">
                  <label>
                    作用域
                    <select
                      aria-label={`${pool.label} 作用域`}
                      value={pool.scope_mode}
                      onChange={(event) => onUpdateResourcePool(index, {
                        scope_mode: event.target.value as ResourcePool["scope_mode"],
                      })}
                    >
                      <option value="PROJECT_SHARED">{resourceScopeLabels.PROJECT_SHARED}</option>
                      <option value="WORKPOINT_EXCLUSIVE">{resourceScopeLabels.WORKPOINT_EXCLUSIVE}</option>
                    </select>
                  </label>
                  <label>
                    全局默认投入
                    <input
                      type="number"
                      min={0}
                      value={quantity}
                      aria-label={`${pool.label} 全局默认投入`}
                      onChange={(event) => {
                        const nextQuantity = Math.max(0, Math.trunc(Number(event.target.value)));
                        onUpdateResourcePool(index, {
                          resource_mode: "LIMITED",
                          quantity: nextQuantity,
                          max_quantity: Math.max(maxQuantity, nextQuantity),
                        });
                      }}
                    />
                  </label>
                  <label>
                    全局可增上限
                    <input
                      type="number"
                      min={Math.max(0, quantity)}
                      value={maxQuantity}
                      aria-label={`${pool.label} 全局可增上限`}
                      onChange={(event) => onUpdateResourcePool(index, {
                        resource_mode: "LIMITED",
                        max_quantity: Math.max(Math.trunc(Number(event.target.value)), Math.max(0, quantity)),
                      })}
                    />
                  </label>
                  <div className="resource-scope-authority-summary">
                    <span>获准工点</span>
                    <strong>{authorizedIds === null ? "全部当前桥梁工点" : `${authorized.size} 个工点`}</strong>
                  </div>
                </div>

                {pool.scope_mode === "PROJECT_SHARED" && (
                  <div className="resource-shared-notice" role="note">
                    项目共享资源跨工点串行使用，转场时间按 0 天。
                  </div>
                )}

                {currentWorkpoints.length > 0 && (
                  <div className="resource-workpoint-table-wrap">
                    <table className="resource-workpoint-table">
                      <thead>
                        <tr>
                          <th>获准</th>
                          <th>权威桥梁工点</th>
                          <th>来源</th>
                          <th>有效投入</th>
                          <th>有效上限</th>
                          <th>有效状态</th>
                          <th>操作</th>
                        </tr>
                      </thead>
                      <tbody>
                        {currentWorkpoints.map((workpoint) => {
                          const workpointId = workpoint.workpoint_id;
                          const isAuthorized = authorized.has(workpointId);
                          const effective = effectiveWorkpointResource(pool, workpointId);
                          const canOverride = pool.scope_mode === "WORKPOINT_EXCLUSIVE" && isAuthorized;
                          return (
                            <tr key={workpointId} data-workpoint-id={workpointId}>
                              <td>
                                <input
                                  type="checkbox"
                                  aria-label={`${workpoint.workpoint_name} 获准`}
                                  checked={isAuthorized}
                                  onChange={(event) => {
                                    const base = authorizedIds ?? currentWorkpoints.map((item) => item.workpoint_id);
                                    const next = event.target.checked
                                      ? [...base, workpointId]
                                      : base.filter((item) => item !== workpointId);
                                    onUpdateResourcePool(index, { authorized_workpoint_ids: Array.from(new Set(next)).sort() });
                                  }}
                                />
                              </td>
                              <td><strong>{workpoint.workpoint_name || "工点名称不可用"}</strong></td>
                              <td>
                                {canOverride
                                  ? effective.inheritanceSource === "overridden" ? "工点覆盖" : "继承全局默认"
                                  : isAuthorized ? "共享全局配置" : "未获准"}
                              </td>
                              <td>
                                <input
                                  type="number"
                                  min={0}
                                  disabled={!canOverride}
                                  value={effective.quantity}
                                  aria-label={`${workpoint.workpoint_name} 有效投入`}
                                  onChange={(event) => onUpdateResourcePool(
                                    index,
                                    setWorkpointResourceOverride(pool, workpointId, {
                                      quantity: Math.max(0, Math.trunc(Number(event.target.value))),
                                    }),
                                  )}
                                />
                              </td>
                              <td>
                                <input
                                  type="number"
                                  min={effective.quantity}
                                  disabled={!canOverride}
                                  value={effective.maxQuantity}
                                  aria-label={`${workpoint.workpoint_name} 有效上限`}
                                  onChange={(event) => onUpdateResourcePool(
                                    index,
                                    setWorkpointResourceOverride(pool, workpointId, {
                                      max_quantity: Math.max(effective.quantity, Math.trunc(Number(event.target.value))),
                                    }),
                                  )}
                                />
                              </td>
                              <td>
                                <input
                                  type="checkbox"
                                  disabled={!canOverride}
                                  checked={effective.enabled}
                                  aria-label={`${workpoint.workpoint_name} 有效状态`}
                                  onChange={(event) => onUpdateResourcePool(
                                    index,
                                    setWorkpointResourceOverride(pool, workpointId, { enabled: event.target.checked }),
                                  )}
                                />
                              </td>
                              <td>
                                <button
                                  className="secondary resource-restore-button"
                                  type="button"
                                  disabled={!canOverride || effective.inheritanceSource !== "overridden"}
                                  onClick={() => onUpdateResourcePool(index, restoreWorkpointResourceInheritance(pool, workpointId))}
                                >
                                  <RotateCcw size={14} />
                                  恢复继承
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
