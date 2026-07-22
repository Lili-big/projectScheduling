# 实施计划：工点结构物与资源左右分栏配置

**分支/目录**：`057-workpoint-structure-resource-layout` | **日期**：2026-07-21 | **规格**：[spec.md](./spec.md)

**输入**：来自当前 `03-requirements/specs/057-workpoint-structure-resource-layout/spec.md` 的功能规格

## 概要

复用资源页已经加载的当前工点详情，在前端领域层派生六类下部结构的只读汇总：按构件类型、规范化结构参数、施工工艺和单位建立稳定签名，对相同签名累加数量并生成紧凑中文摘要。资源页在工点导航和目录补充区下方改为响应式左右布局，左侧展示结构物汇总，右侧以无字段表头的紧凑资源卡片维护当前投入和可增上限。

`WORKPOINT_EXCLUSIVE` 资源的兼容 `enabled` 字段在既有规范化路径中由 `quantity > 0` 派生，页面删除独立启用控件。项目共享资源、后端契约、持久化结构、资源候选、求解约束和目标均不修改。

## 技术上下文

**语言/版本**：TypeScript 5.7、Node.js（仓库现有前端运行时）

**主要依赖**：React 19、Vite 6、现有 `projectMasterApi.ts`、前端领域模块；不新增依赖

**存储**：沿用场景 `resource_pools`；结构汇总为只读派生状态，不持久化；不新增迁移

**测试**：Node `node:test` 领域/源码契约测试、现有资源页运行时场景一次、TypeScript 类型检查、Vite 生产构建、`validate_docs.py`

**目标平台**：本地 FastAPI + React/Vite Demo；本功能只改前端

**项目类型**：Web 应用前端领域逻辑和资源配置页面

**性能目标**：每次工点详情返回后对当前工点构件执行线性遍历和内存分组；不增加网络请求，不扫描其他工点详情

**约束**：只统计六类有效下部结构；不自动估算资源数量；不新增 API/字段；不恢复共享资源；不改变求解器；旧请求不得覆盖当前选择；历史记录不删除

**规模/范围**：一个前端领域模块、一个页面组件、一个样式文件、两个现有资源定向测试文件以及本功能规格资产

## 生命周期归属

- **规格归属引用**：[`spec.md#生命周期归属`](./spec.md#生命周期归属)
- **实施路径**：`04-demo/frontend/src/domain/resources.ts`、`04-demo/frontend/src/features/resources/ResourcesTab.tsx`、`04-demo/frontend/src/features/resources/styles.css`、`04-demo/frontend/tests/resourceWorkpointScope.test.mjs`、`04-demo/frontend/tests/resourceWorkpointRuntime.test.mjs`

## Constitution 检查

*Phase 0 前检查：通过；Phase 1 设计后复核：通过。*

- 用户已明确结构汇总范围、左右布局和数量派生启用语义；不自动计算资源数量是本规格记录的范围收敛结论。
- `spec.md` 已引用 048/049/050/052 规格、用户截图与当前工点详情/资源页面代码事实。
- 资源影响已明确：仅工点独享资源的 UI 与前端规范化语义变化；共享输入兼容、候选生成、工期、CP-SAT 约束和目标不变。
- 输入、分组键、输出顺序、数量单位、缺失参数、未知工艺、历史矛盾状态、加载/失败/空态和验收样例均可测试。
- 结构汇总是估算辅助信息，不把 Demo 中的默认工艺或展示样式提升为自动资源配置规则。
- `spec.md` 已声明唯一生命周期归属；实现只引用规格，不复制资产分类。
- 本功能不迁移资产或数据，不清理本地状态、用户输入或历史资源记录。
- 规范化仍保留公开 `enabled` 字段，避免前后端/演示镜像契约漂移。

## 项目结构

### 本功能文档

```text
03-requirements/specs/057-workpoint-structure-resource-layout/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── workpoint-structure-resource-ui-contract.md
└── tasks.md
```

### 生命周期与源码结构（仓库根目录）

```text
04-demo/frontend/
├── src/
│   ├── contracts/projectMaster.ts                 # 复用，字段不变
│   ├── domain/resources.ts                        # 结构汇总纯函数与工点资源启用规范化
│   └── features/resources/
│       ├── ResourcesTab.tsx                       # 左右布局与精简资源交互
│       └── styles.css                             # 双栏、汇总项、资源卡片和窄屏布局
└── tests/
    ├── resourceWorkpointScope.test.mjs            # 汇总/数量语义/源码契约定向测试
    └── resourceWorkpointRuntime.test.mjs          # 当前工点页面运行时场景
```

**结构决策**：工点详情请求继续由 `ResourcesTab` 维护，避免增加第二次请求或把页面内部选择状态提升到 `Workspace`。结构汇总与资源规范化属于可复用、可确定测试的领域逻辑，放在现有 `domain/resources.ts`；页面只编排状态、交互和渲染。样式沿用资源功能目录，不新建组件目录或依赖。

## Phase 0：研究结论

- 当前工点详情已包含完成汇总所需的构件类型、`quantity`、`unit`、`enabled`、参数和所属结构参数，无需后端扩展。
- 结构汇总与 feature 050 的资源建议必须共用显式工艺优先、唯一默认工艺兜底的解析边界，避免同一工点左右两块对工艺理解不一致。
- 结构汇总为只读派生数据；页面展示不能创建资源池或预填资源数量。
- `enabled` 仍是公共资源池契约的一部分，不删除字段；只对有明确 `workpoint_id` 的 `WORKPOINT_EXCLUSIVE` 记录将其规范化为 `quantity > 0`，项目共享兼容读取保持原样。
- 现有真实浏览器资源页测试曾受系统 CDP 环境影响；本期仍只尝试一次，并以领域/源码契约、类型检查和构建作为核心可重复证据，相关业务失败必须修正。

详见 [research.md](./research.md)。

## Phase 1：数据与界面契约

- [data-model.md](./data-model.md) 定义结构汇总分类、汇总项、规范化签名、工艺解析结果以及数量派生的工点资源视图，不新增持久化实体。
- [workpoint-structure-resource-ui-contract.md](./contracts/workpoint-structure-resource-ui-contract.md) 固化现有详情接口读取、六类映射、分组/格式化、双栏、资源简化、兼容字段和状态行为。
- [quickstart.md](./quickstart.md) 提供六类结构分组、桩径/尺寸示例、数量启用语义、响应式布局、乱序/失败以及非回归验证步骤。

## 计划实现顺序

1. 在 `resourceWorkpointScope.test.mjs` 固定结构汇总与工点资源数量语义的领域样例。
2. 在 `resources.ts` 增加纯汇总投影并收敛本地工点资源的 `enabled` 规范化。
3. 在 `ResourcesTab.tsx` 和 `styles.css` 接入双栏结构，移除可见表头、技术代码和启用控件，保留目录、输入、保存与显式删除。
4. 更新页面源码契约和运行时场景，验证当前详情身份、左右数据一致及无隐式持久化。
5. 执行一次风险匹配的定向验证批次；修正相关失败，记录有证据的非核心环境问题。

## 复杂度跟踪

无 Constitution 违反项。
