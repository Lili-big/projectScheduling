import { PanelTitle } from "../../components/common/PanelTitle";
import { resourceCostTypeLabels, resourceModeLabels } from "../../domain/constants";
import {
  resourcePoolBillingPeriodDays,
  resourcePoolCostType,
  resourcePoolMode,
  resourcePoolQuantity,
  resourcePoolUnitCost,
} from "../../domain/resources";
import type { ResourceCostType, ResourceMode, ResourcePool, ScenarioInput } from "../../types/scheduler";

export function ResourcesTab({
  scenario,
  onUpdateResourcePool,
}: {
  scenario: ScenarioInput;
  onUpdateResourcePool: (index: number, patch: Partial<ResourcePool>) => void;
}) {
  return (
    <section className="panel full">
      <PanelTitle title="资源配置约束" subtitle="仅限制数量的资源会参与容量判断；默认充足资源不会产生等待" />
      <div className="resource-grid">
        {scenario.resource_pools.map((pool, index) => {
          const mode = resourcePoolMode(pool);
          const isLimited = mode === "LIMITED";
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
              <label className="resource-mode-field">
                资源级别
                <select
                  value={mode}
                  onChange={(event) => {
                    const nextMode = event.target.value as ResourceMode;
                    if (nextMode === "LIMITED") {
                      const nextQuantity = Math.max(0, quantity);
                      onUpdateResourcePool(index, {
                        resource_mode: nextMode,
                        quantity: nextQuantity,
                        max_quantity: Math.max(maxQuantity, nextQuantity),
                      });
                    } else {
                      onUpdateResourcePool(index, { resource_mode: nextMode });
                    }
                  }}
                >
                  <option value="LIMITED">{resourceModeLabels.LIMITED}</option>
                  <option value="UNLIMITED">{resourceModeLabels.UNLIMITED}</option>
                </select>
              </label>
              <label>
                当前数量
                <input
                  type="number"
                  min={0}
                  disabled={!isLimited}
                  value={isLimited ? quantity : ""}
                  placeholder="默认充足"
                  onChange={(event) => {
                    const nextQuantity = Math.max(0, Number(event.target.value));
                    onUpdateResourcePool(index, {
                      quantity: nextQuantity,
                      max_quantity: Math.max(maxQuantity, nextQuantity),
                    });
                  }}
                />
              </label>
              <label>
                最大数量
                <input
                  type="number"
                  min={Math.max(0, quantity)}
                  disabled={!isLimited}
                  value={isLimited ? maxQuantity : ""}
                  placeholder="默认充足"
                  onChange={(event) => onUpdateResourcePool(index, { max_quantity: Math.max(Number(event.target.value), Math.max(0, quantity)) })}
                />
              </label>
              <label>
                日历
                <select value={pool.calendar_id} onChange={(event) => onUpdateResourcePool(index, { calendar_id: event.target.value })}>
                  {scenario.resource_calendars.map((calendar) => (
                    <option value={calendar.id} key={calendar.id}>{calendar.name}</option>
                  ))}
                </select>
              </label>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={pool.enabled}
                  onChange={(event) => onUpdateResourcePool(index, { enabled: event.target.checked })}
                />
                启用
              </label>
              {!isLimited && <p className="resource-mode-note">该资源按默认充足处理，不限制并行任务数。</p>}
              {isLimited && (
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
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
