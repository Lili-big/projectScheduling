# 实施计划：移除资源共享模式

**分支/目录**：`049-remove-shared-resource-mode` | **日期**：2026-07-19 | **规格**：[spec.md](./spec.md)

**输入**：来自 `03-requirements/specs/049-remove-shared-resource-mode/spec.md` 的已确认功能规格。

## 概要

保留 `PROJECT_SHARED` 契约及求解器既有共享计算能力，只从正常项目数据链路移除共享资源：清空代码默认与 bundled 默认数据；本地配置加载时识别并删除共享池、原子写回清理后的配置；保存接口允许空资源集合且过滤共享池；前端场景标准化和 Demo API 参考镜像只向正常项目流程传播工点独享池。被删除共享数量不转换为工点资源，历史排程快照不追溯修改。

## 技术上下文

**语言/版本**：Python 3.12、TypeScript 5.7、Node.js 24

**主要依赖**：FastAPI、Pydantic、OR-Tools CP-SAT、React 19、Vite 6

**存储**：`.local-data/state/scheduler-config.json` 当前本地配置；`04-demo/backend/app/default_scenario_config.json` bundled 默认配置；写入沿用临时文件替换的原子方式

**测试**：pytest、Node `node:test`、TypeScript `tsc --noEmit`、Vite production build、Demo API mirror verify

**目标平台**：本地 FastAPI 服务与 React/Vite Demo；`04-demo/tools/demo-api-mirror/api.mts` 为未部署参考镜像

**项目类型**：前后端 Web Demo、JSON 本地配置迁移和共享输入契约兼容

**性能目标**：资源清理为单次 O(n) 过滤，不增加求解阶段耗时；求解器路径保持不变

**约束**：不修改共享候选、互斥和零转场求解规则；不把共享数量转换为本地数量；允许清理后资源池为空；不追溯删除历史结果；不覆盖工作树无关改动

**规模/范围**：默认场景、本地配置加载/保存、前端场景标准化、资源页现有 UI 删除、Demo API 参考镜像及相邻契约/迁移测试

## 生命周期归属

- **规格归属引用**：[`spec.md#生命周期归属`](./spec.md#生命周期归属)
- **实施路径**：`04-demo/backend/app/scenario_data.py`、`04-demo/backend/app/default_scenario_config.json`、`04-demo/backend/app/local_scenario_config.py`、`04-demo/backend/app/contracts/_models.py`、`04-demo/frontend/src/domain/resources.ts`、`04-demo/frontend/src/features/resources/ResourcesTab.tsx`、`04-demo/tools/demo-api-mirror/api.mts` 及对应 `04-demo/backend/tests/`、`04-demo/frontend/tests/`

## Constitution 检查

### 设计前门禁

- 已由用户明确确认删除当前项目共享数据，并确认求解器无需忽略共享输入。
- `spec.md` 已引用 048、用户新口径和当前代码事实。
- 输入、输出、持久化清理、空态、本地资源缺口和历史保留均有可测试要求。
- 删除范围限定为当前项目默认/持久化 `resource_pools` 中的共享记录；工点独享池、历史结果和无关本地状态受保护。
- 清理属于用户明确授权的数据迁移；写回必须复用现有原子替换，失败不得产生半写文件。
- 不把 Demo 限制提升为求解器规则，不删除 `PROJECT_SHARED` 公开识别能力。

结论：通过，无 Constitution 违反项。

### 设计后复核

- 数据模型定义了旧共享记录、当前有效集合和清理状态转换。
- 接口契约明确 GET/PUT 的空列表、清理结果和 503 写入失败行为，求解接口保持不变。
- Quickstart 使用不同证据验证持久化、正常项目计算、前端入口和镜像一致性，未安排重复全量门禁。
- 历史快照、审计证据、工点资源字段和共享求解能力均明确不在删除范围。

结论：通过，可以进入 `$speckit-tasks`。

## 设计决策

1. **清理边界在项目数据入口，不在求解器**：后端默认/本地配置和前端 `normalizeScenarioResourcePools` 形成正常项目数据链路；`resolve_effective_resource_pools`、求解器共享候选及零转场逻辑保持原样。
2. **本地配置加载即持久化清理**：仅对本地状态文件检测并删除共享记录，保留其他字段后使用现有临时文件替换原子写回；bundled 配置通过代码变更直接清空，不在运行时改写仓库文件。
3. **允许空资源集合**：移除 `LocalScenarioConfigSaveRequest.resource_pools` 的最小长度限制，并取消保存函数“资源配置不能为空”的校验；空集合表示项目尚未配置任何工点资源。
4. **先迁移合法 legacy 独享池，再过滤共享池**：`WORKPOINT_EXCLUSIVE` 且缺少直接 `workpoint_id` 的旧记录继续按 048 规则无损展开；显式或默认 `PROJECT_SHARED` 记录直接删除。
5. **前端只传播当前有效集合**：场景加载、保存、生成、求解、AI 参数和指纹均复用现有标准化入口，过滤后自然使旧当前结果失效；不另建共享禁用状态。
6. **参考镜像保持项目数据一致**：清空镜像默认共享池，并在缓存加载/保存和计算前的场景标准化中只保留工点独享池；不改镜像底层共享匹配函数。

## 项目结构

### 本功能文档

```text
03-requirements/specs/049-remove-shared-resource-mode/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── project-resource-cleanup.md
└── tasks.md
```

### 实施源码与测试

```text
04-demo/backend/
├── app/
│   ├── contracts/_models.py
│   ├── default_scenario_config.json
│   ├── local_scenario_config.py
│   └── scenario_data.py
└── tests/
    ├── test_local_scenario_config.py
    ├── test_architecture_api_contract.py
    └── scheduling/test_fixed_resource_application.py

04-demo/frontend/
├── src/
│   ├── domain/resources.ts
│   └── features/resources/ResourcesTab.tsx
└── tests/
    ├── resourceWorkpointScope.test.mjs
    └── resourceWorkpointRuntime.test.mjs

04-demo/tools/demo-api-mirror/
├── api.mts
└── verify.mjs
```

**结构决策**：复用现有后端配置、前端资源领域函数和参考镜像，不新增运行时模块、依赖或兼容目录。规格资产唯一归属 049；代码和测试继续归 `04-demo`。

## 复杂度跟踪

无 Constitution 违反项，不需要额外复杂度豁免。
