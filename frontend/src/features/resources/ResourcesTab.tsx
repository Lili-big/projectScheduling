import { CheckCircle2, Loader2, Save, XCircle } from "lucide-react";
import { PanelTitle } from "../../components/common/PanelTitle";
import { resourcePoolQuantity } from "../../domain/resources";
import type { ResourcePool, ScenarioInput } from "../../contracts";

export function ResourcesTab({
  scenario,
  onUpdateResourcePool,
  onSaveLocalConfig,
  savingLocalConfig,
  localConfigDirty,
}: {
  scenario: ScenarioInput;
  onUpdateResourcePool: (index: number, patch: Partial<ResourcePool>) => void;
  onSaveLocalConfig: () => void;
  savingLocalConfig: boolean;
  localConfigDirty: boolean;
}) {
  return (
    <section className="panel full">
      <PanelTitle
        title="资源方案"
        subtitle="复制方案后调整资源数量，再重新求解并保存对比"
        action={
          <button
            className="secondary"
            type="button"
            onClick={onSaveLocalConfig}
            disabled={savingLocalConfig || !localConfigDirty}
            title="保存到后端本地 JSON 配置文件"
            aria-label="保存资源配置"
          >
            {savingLocalConfig ? <Loader2 className="spin" size={16} /> : <Save size={16} />}
            保存
          </button>
        }
      />
      <div className="resource-list-wrap">
        <table className="resource-list-table">
          <thead>
            <tr>
              <th>资源</th>
              <th>默认投入</th>
              <th>可增上限</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            {scenario.resource_pools.map((pool, index) => {
              const quantity = resourcePoolQuantity(pool);
              const maxQuantity = Math.max(pool.max_quantity ?? quantity, quantity);
              return (
                <tr key={pool.id}>
                  <td>
                    <div className="resource-list-name">
                      <strong>{pool.label}</strong>
                      <code>{pool.type}</code>
                      {pool.parallel_rule_description ? (
                        <span className="resource-parallel-note">{pool.parallel_rule_description}</span>
                      ) : null}
                    </div>
                  </td>
                  <td>
                    <input
                      type="number"
                      min={0}
                      value={quantity}
                      aria-label={`${pool.label} 默认投入`}
                      onChange={(event) => {
                        const nextQuantity = Math.max(0, Number(event.target.value));
                        onUpdateResourcePool(index, {
                          resource_mode: "LIMITED",
                          quantity: nextQuantity,
                          max_quantity: Math.max(maxQuantity, nextQuantity),
                        });
                      }}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      min={Math.max(0, quantity)}
                      value={maxQuantity}
                      aria-label={`${pool.label} 可增上限`}
                      onChange={(event) => onUpdateResourcePool(index, {
                        resource_mode: "LIMITED",
                        max_quantity: Math.max(Number(event.target.value), Math.max(0, quantity)),
                      })}
                    />
                  </td>
                  <td>
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
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
