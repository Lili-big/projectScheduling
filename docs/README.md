# 项目文档索引

本页是 `docs/` 的唯一入口。状态含义：`current` 表示当前实现的权威说明，`draft` 表示仍需确认，`superseded` 表示已被新文档替代，`historical` 表示仅保留审计，`missing_source` 表示历史引用的源文件已缺失。

代码和文档冲突时，解释实现行为应以当前代码、测试和 [架构地图](./architecture/module-map.md) 为准；产品目标与范围以已确认 PRD/Spec 为准。

## 当前权威入口

| 文档 | 状态 | 权威范围 | 替代/关联 | 维护触发条件 |
| --- | --- | --- | --- | --- |
| [系统上下文](./architecture/system-context.md) | current | 角色、主链路、系统与外部边界 | 根 `README.md` 提供快速入口 | 用户角色、系统边界或主流程变化 |
| [模块地图](./architecture/module-map.md) | current | 后端、前端、数据、工具所有权 | `agent.md` 提供修改矩阵 | 模块移动、入口或所有权变化 |
| [依赖规则](./architecture/dependency-rules.md) | current | 允许/禁止依赖和兼容 façade | 042 ADR | 新模块、新跨域调用或兼容入口变化 |
| [运行与部署](./architecture/runtime-and-deployment.md) | current | 本地、单服务、Docker、Netlify 边界 | 根 `README.md` 提供命令 | 命令、端口、环境变量或部署方式变化 |
| [仓库与资产治理](./architecture/repository-governance.md) | current | 根目录、文档、工具、交付物、生成物和日志放置 | [路径迁移记录](./archive/path-migration.md) | 新资产类别、迁移或 Git 策略变化 |
| [排程算法当前实现交底文档 v1.2](./engineering/排程算法当前实现交底文档_v1.2.md) | current | CP-SAT 当前实现和结果语义 | 历史算法规格位于 `specs/` | 约束、目标、策略或结果口径变化 |
| [项目排程系统整体说明 v1.1](./product/项目排程系统整体说明_v1.1.md) | current | 产品能力总览 | 当前实现边界仍以代码/测试为准 | 产品能力或页面闭环变化 |
| [AI 参数输入助手验证说明](./validation/AI参数输入助手验证说明.md) | current | 参数助手使用与验证 | 对应 `002-ai-parameter-assistant` | 输入限制、模型接入或应用流程变化 |
| [AI 资源配置与排程优化助手验证说明](./validation/AI资源配置与排程优化助手验证说明.md) | current | 资源助手使用与降级边界 | 对应 `022`、`028`～`038` | 推荐、求解、比较或时限变化 |

## 页面与规则文档

| 主题 | 文档 | 状态 | 说明 |
| --- | --- | --- | --- |
| 工艺工效 | [施工工艺及工效库需求文档 v1.1](./product/施工工艺及工效库需求文档_v1.1.md) | current | 工艺、工效和默认资源配置 |
| 工艺逻辑 | [工艺逻辑约束需求文档 v1.1](./engineering/工艺逻辑约束需求文档_v1.1.md) | current | 下部和部分上部结构逻辑 |
| 任务视图 | [任务视图页面需求文档 v1.0](./product/任务视图页面需求文档_v1.0.md) | current | 任务、前置和诊断展示 |
| 资源配置 | [资源配置页面需求文档 v1.2](./product/资源配置页面需求文档_v1.2.md) | current | 资源池、上限、成本和日历 |
| 里程碑 | [里程碑页面需求文档 v1.0](./product/里程碑页面需求文档_v1.0.md) | current | 控制节点配置与评价 |
| 模拟求解 | [模拟求解 MVP 页面需求文档 v1.2](./product/模拟求解-MVP页面需求文档_v1.2.md) | current | 三类求解与方案比较页面 |
| 墩柱工期 | [墩柱按高度计算工期算法需求文档 v1.0](./engineering/墩柱按高度计算工期算法需求文档_v1.0.md) | current | 高度分段工期规则 |
| 连续梁 | [现浇连续梁结构排程 PRD 算法 v1.10](./engineering/现浇连续梁结构排程_PRD算法_v1.10.md) | current | 连续梁任务生成和排程规则 |
| 计划发布 | [计划发布与审批入口需求文档 v1.0](./product/计划发布与审批入口需求文档_v1.0.md) | draft | 产品目标；不得视为已完整实现 |
| 产品中枢 | [基建智能计划管控中枢整体产品方案 v1.0](./product/基建智能计划管控中枢整体产品方案_v1.0.md) | draft | 长期产品方向，不等于当前 Demo |

## 调研与案例材料

- 泸古项目访谈、验证计划、调研记录和前期策划材料：`historical`，用于客户调研证据，不作为代码规则。
- `AI驱动Demo快速验证与研发交付案例_v1.0.md`、`v1.1.md`：`superseded`，由 v1.2/申报版承接。
- `AI驱动Demo快速验证与研发交付案例_v1.2.md`、申报版：`current`，仅对案例叙事负责。

## 分区与迁移记录

- `product/`：产品目标、方案和页面 PRD。
- `engineering/`：算法、规则和工程交底。
- `validation/`：验证说明和客户验证计划。
- `research/`：调研原始材料，不作为代码规则。
- `archive/`：已替代案例与 [路径迁移记录](./archive/path-migration.md)。

JSON/HTML 结果查看器已移至 `examples/result-viewer/`；可重新生成的预览、检查结果和 Office 临时锁已移至本地 `artifacts/` 并取消跟踪。正式交付物位于根 `deliverables/`。

## 新文档放置规则

- 当前架构与 ADR：`docs/architecture/`。
- 产品方案和 PRD：`docs/product/`；算法和规则交底：`docs/engineering/`。
- 验证材料：`docs/validation/`；调研材料：`docs/research/`；替代资料：`docs/archive/`。
- 已确认进入开发的规格：`specs/<编号>-<功能名>/`，入口见 [规格索引](../specs/README.md)。
- 临时分析不得放根目录；可再生成的预览和检查结果进入 `artifacts/` 且默认不跟踪。
