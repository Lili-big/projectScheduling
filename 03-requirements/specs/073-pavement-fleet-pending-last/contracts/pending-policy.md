# 排程后置规则契约

## 接口与字段

- 现有 `/api/generate-schedule-input`、`/api/solve`、`/api/solve-scenario`、`/api/solve-scenario/stream` 不增加端点。
- 生成输入 `pavement_handover_scope.pending_policy` 与结果 `stats.pavement_handover.pending_policy` 输出 `per_fleet_last`；后端 Literal 与前端 union 同步保留旧值 `strict_last` 的读取能力。
- 新规则判断实际单套资源任务路径，不以同类型所有机组或全项目任务作为完工边界。
- 携带旧标识的求解输入返回现有结果状态 `MODEL_INVALID`、诊断码 `PAVEMENT_INPUT_OUTDATED`，提示“后置规则已调整，请重新生成任务后求解”；遵循既有接口封装和 HTTP 状态，不新造状态码。
- 无范围元数据的直接输入从任务属性推导当前规则；现有数据完整性诊断不放松。
- 演示 API 镜像仍返回 HTTP 422 / `PAVEMENT_FEATURE_NOT_SUPPORTED`，不暴露伪实现。

## 展示与状态

- 新规则：“各机组完成自身正常段任务后，再施工待移交段。须在所列日期当天开工前完成移交；实际移交仍待确认。”
- 旧规则：“历史方案按正常段全部完成后安排待移交段”，保持历史日期，提示重新求解才应用新规则。
- 任务预览能识别两种标识中的待移交段，仍标注附条件排程；新生成诊断不再说全项目完成之后。
- 日期公式不变：required_handover_date 为段首任务开工日，estimated_finish_date 为段末任务施工末日；未知/不可行/无结果不填造日期。
- 流式生成、初步方案、改善、完成、中断使用同一规则快照；保留当前最好方案和未证明最优提示。

## 兼容与失效

只读历史结果不迁移、不更换日期；旧输入再次计算须重新生成。当前页面旧方案不静默覆盖；新结果仅来自新求解。规则变更不修改真实移交日、pending 状态、机组或工效配置。
