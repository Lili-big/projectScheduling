# 求解时限接口与显示契约

## 普通求解

POST `/api/solve-scenario/stream` 请求结构不变，scenario.time_limit_seconds 为本次输入值；界面创建请求副本，不改业务配置。started 与 pavement_optimization 均记录此预算。

## 窝工优化

POST `/api/solve-scenario/idle/stream` 请求为 `{scenario, baseline, time_budget_seconds?}`。新字段定义见 [数据模型](../data-model.md)。

- 示例：基准原预算 15 秒，用户改为 60 秒；scenario 和 baseline 保留原预算身份，独立 time_budget_seconds=60。本轮 started 和最终 idle 元数据均为 60，第一阶段元数据仍为 15。
- 缺省或 null 回退 scenario.time_limit_seconds；0、负数和非有限数值返回既有 Pydantic HTTP422 结构，不开启流。
- 当前业务 scenario 仍由服务端物化、生成并与基准逐字段核对；只在前端请求副本中恢复基准原 time_limit_seconds。任何主数据、工序、资源、版本、范围或任务时刻差异仍按既有规则拒绝，错误码保持。
- 不改 started → initial → improvement* → complete/error 事件结构和 sequence 校验；基准指纹、cap 和目标比较保持。
- 本轮预算从既有 began 时点起覆盖验证、建模与搜索，结果收尾和网络不承诺精确同秒返回。
- 客户端连接等待采用本轮有效预算加既有 30 秒余量；不会因基准只有 15 秒而截断更长的窝工优化。
- 演示镜像继续返回不支持路面求解的明确诊断。

## 界面

求解按钮旁显示“求解时限（秒）”，初值 15，说明“用于本次工期求解或窝工优化”。有效值允许超过 15 秒；空值、0、负值或非有限值显示“请输入大于 0 的有效秒数”。

修改时限保留当前结果和窝工入口；没有可行基准时窝工入口仍禁用。运行中时限及求解按钮禁用；结束后恢复。时限不写保存配置，页面新会话默认 15 秒。

错误、中断、预算耗尽、无改善、提前最优和历史结果显示沿用现有语义。
