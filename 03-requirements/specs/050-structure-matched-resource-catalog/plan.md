# 实施计划：结构物匹配的中文资源目录

**分支/目录**：`050-structure-matched-resource-catalog` | **日期**：2026-07-19 | **规格**：[spec.md](./spec.md)

**输入**：来自当前 `03-requirements/specs/050-structure-matched-resource-catalog/spec.md` 的功能规格

## 概要

将资源页的默认展示从“已生成任务资源，缺失时退化为全部工艺资源”改为“当前项目主数据版本下所选桥梁工点的结构物资源建议”。页面继续复用工点列表做导航，并按所选工点懒加载现有工点详情接口；前端领域函数根据启用结构、构件、显式工艺参数或默认工艺确定资源类型，去重后与已保存的工点独享资源合并展示。内置资源名称集中维护为中文，配置池的中文 `label` 优先，自定义未知类型显示中文未命名提示及代码。

本功能只改变资源目录投影和页面展示，不新增后端接口、持久化字段或共享资源，不修改资源候选、CP-SAT 约束和求解目标。

## 技术上下文

**语言/版本**：TypeScript 5.7、Node.js（仓库当前前端运行时）

**主要依赖**：React 19、Vite 6；复用现有 `projectMasterApi.ts` 和前端领域模块，无新增依赖

**存储**：沿用本地场景配置中的 `resource_pools`；匹配建议不持久化，不增加迁移

**测试**：Node `node:test` 前端领域测试、资源页源代码契约测试、现有浏览器运行时场景、TypeScript 类型检查、Vite 生产构建、`validate_docs.py`

**目标平台**：本地 FastAPI + React/Vite Demo 及现有 Demo API 镜像兼容路径

**项目类型**：Web 应用前端领域逻辑与资源配置页面变更

**性能目标**：切换工点只请求一个工点详情；投影复杂度保持为当前工点结构/构件数与工艺数的线性组合，不批量请求全部工点详情

**约束**：以当前 `project_data_version_id` 的工点详情为权威；旧响应不得覆盖新版本或新选择；建议数量和上限均为 0；保留已配置资源；不恢复 `PROJECT_SHARED`；不修改求解器

**规模/范围**：集中中文名称常量、资源领域投影、资源页详情加载/状态、资源页面与两类前端测试；不改后端模型、API schema 和持久化

## 生命周期归属

- **规格归属引用**：[`spec.md#生命周期归属`](./spec.md#生命周期归属)
- **实施路径**：`04-demo/frontend/src/domain/constants.ts`、`04-demo/frontend/src/domain/resources.ts`、`04-demo/frontend/src/domain/resourceAssistant.ts`、`04-demo/frontend/src/features/resources/ResourcesTab.tsx`、`04-demo/frontend/src/app/Workspace.tsx`、`04-demo/frontend/tests/resourceWorkpointScope.test.mjs`、`04-demo/frontend/tests/resourceWorkpointRuntime.test.mjs`

## Constitution 检查

*Phase 0 前检查：通过；Phase 1 设计后复核：通过。*

- 已完成需求评审：用户明确提出中文名称和结构自动匹配，048/049 已给出工点独享、数量 0 和无共享资源边界。
- `spec.md` 已引用用户截图、产品文档、048/049 规格以及当前前后端代码事实。
- 资源影响已明确：只改变只读目录/建议投影；工期、CP-SAT、候选、求解目标和共享输入兼容均不变。
- 输入、输出、优先级、去重、加载/失败/空态、版本切换和验收样例均可测试。
- 未将 Demo 默认工艺扩展为正式资源数量规则；默认工艺仅在没有显式工艺时用于类型匹配。
- `spec.md` 已声明唯一生命周期归属；实现只引用规格，不复制第二份分类。
- 本功能没有资产迁移；既有本地配置和用户资源记录不自动删除或重写。
- 只读建议不作为缓存清理对象，也不改变本地正式配置的保留方式。

## 项目结构

### 本功能文档

```text
03-requirements/specs/050-structure-matched-resource-catalog/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── resource-suggestion-ui-contract.md
└── tasks.md
```

### 生命周期与源码结构（仓库根目录）

```text
04-demo/frontend/
├── src/
│   ├── api/projectMasterApi.ts                    # 复用现有工点详情读取接口，不修改
│   ├── domain/constants.ts                        # 内置资源中文名称和结构映射常量
│   ├── domain/resources.ts                        # 目录名称与工点结构资源投影
│   ├── domain/resourceAssistant.ts                # 复用统一中文名称，移除私有重复表
│   ├── features/resources/ResourcesTab.tsx        # 当前工点详情加载、状态和建议行展示
│   └── app/Workspace.tsx                          # 移除资源页对已生成任务的旧输入
└── tests/
    ├── resourceWorkpointScope.test.mjs            # 领域与静态契约验证
    └── resourceWorkpointRuntime.test.mjs          # 页面切换、请求竞争和展示验证
```

**结构决策**：复用现有 `GET /api/project-master/versions/{version_id}/workpoints/{workpoint_id}`，不新增后端资源建议接口。工点详情请求由 `ResourcesTab` 按当前选择管理，从而无需把页面内部选中状态上移到 `Workspace`；纯匹配规则留在 `domain/resources.ts`，页面只编排状态和渲染。中文名称放入现有 `domain/constants.ts`，供资源页和资源助手共用，避免两份名称表漂移。

## 设计阶段

### Phase 0：研究结论

- 当前工点列表只适合导航，结构匹配必须读取当前版本的工点详情。
- 已生成任务不能作为默认资源唯一来源，因为空资源时生成可能失败，且其缺失回退会把全项目资源错误展示到每个工点。
- 项目主数据构件未显式提供工艺选择时，采用工艺库中同构件类型唯一默认工艺；存在 `method_id`/等价参数时优先按该参数匹配。
- 建议行只读派生；已配置工点资源无论是否继续匹配都保留并展示。

详见 [research.md](./research.md)。

### Phase 1：数据与接口设计

- [data-model.md](./data-model.md) 定义中文目录项、结构资源建议和页面详情状态，不新增持久化实体。
- [resource-suggestion-ui-contract.md](./contracts/resource-suggestion-ui-contract.md) 固化现有详情接口的使用方式、匹配优先级、名称解析和加载/失败/空态。
- [quickstart.md](./quickstart.md) 给出桩基方法、连续梁、中文名称、非持久化、保留已配置资源和版本竞争的可复现验收。

## 复杂度跟踪

无 Constitution 违反项。
