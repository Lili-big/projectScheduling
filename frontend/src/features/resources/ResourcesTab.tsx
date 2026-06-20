import { Loader2, Save } from "lucide-react";
import { PanelTitle } from "../../components/common/PanelTitle";
import { resourceCostTypeLabels } from "../../domain/constants";
import {
  resourcePoolBillingPeriodDays,
  resourcePoolCostType,
  resourcePoolQuantity,
  resourcePoolUnitCost,
} from "../../domain/resources";
import type { ResourceCostType, ResourcePool, ScenarioInput } from "../../types/scheduler";

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
        title="资源配置约束"
        subtitle="配置默认 / 最大资源数量，资源均参与容量约束；资源日历暂按默认连续自然日处理"
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
      <div className="resource-grid">
        {scenario.resource_pools.map((pool, index) => {
          const quantity = resourcePoolQuantity(pool);
          const maxQuantity = Math.max(pool.max_quantity ?? quantity, quantity);
          const costType = resourcePoolCostType(pool);
          const unitCost = resourcePoolUnitCost(pool);
          const billingPeriodDays = resourcePoolBillingPeriodDays(pool);
          return (
            <div className="resource-card" key={pool.id}>
              <div>
                <strong>{pool.label}</strong>
                <code>{pool.type}</code>
              </div>
              <label>
                默认投入数量
                <input
                  type="number"
                  min={0}
                  value={quantity}
                  onChange={(event) => {
                    const nextQuantity = Math.max(0, Number(event.target.value));
                    onUpdateResourcePool(index, {
                      resource_mode: "LIMITED",
                      quantity: nextQuantity,
                      max_quantity: Math.max(maxQuantity, nextQuantity),
                    });
                  }}
                />
              </label>
              <label>
                可增配上限数量
                <input
                  type="number"
                  min={Math.max(0, quantity)}
                  value={maxQuantity}
                  onChange={(event) => onUpdateResourcePool(index, {
                    resource_mode: "LIMITED",
                    max_quantity: Math.max(Number(event.target.value), Math.max(0, quantity)),
                  })}
                />
              </label>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={pool.enabled}
                  onChange={(event) => onUpdateResourcePool(index, { enabled: event.target.checked })}
                />
                启用
              </label>
              <div className="linear-cost-editor">
                <strong>线性成本</strong>
                <label>
                  成本类型
                  <select
                    value={costType}
                    onChange={(event) => onUpdateResourcePool(index, { cost_type: event.target.value as ResourceCostType })}
                  >
                    {Object.entries(resourceCostTypeLabels).map(([value, label]) => (
                      <option value={value} key={value}>{label}</option>
                    ))}
                  </select>
                </label>
                <label>
                  {costType === "monthly_rental" ? "月租金" : "新增单价"}
                  <input
                    type="number"
                    min={0}
                    disabled={costType === "none"}
                    value={costType === "none" ? "" : unitCost}
                    placeholder="0"
                    onChange={(event) => onUpdateResourcePool(index, { incremental_unit_cost: Math.max(0, Number(event.target.value)) })}
                  />
                </label>
                {costType === "monthly_rental" && (
                  <label>
                    计费周期
                    <input
                      type="number"
                      min={1}
                      value={billingPeriodDays}
                      onChange={(event) => onUpdateResourcePool(index, { billing_period_days: Math.max(1, Number(event.target.value)) })}
                    />
                  </label>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
