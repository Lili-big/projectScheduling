---

description: "三方案生成前 LLM 项目信息下载实施任务"
---

# 任务清单：三方案生成前 LLM 项目信息下载

**输入**：来自 `specs/025-llm-project-context-export/` 的设计文档

**前置条件**：`plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/llm-project-context-export-contract.md`

**测试要求**：本功能增加前后端共享字段并改变用户可见工作流，必须包含后端契约测试、敏感信息检查、前端生产构建和页面状态验证。

## Phase 1：准备（共享基础）

**目标**：确认改动边界并保护工作区已有修改。

- [x] T001 核对 `git status` 和 `git diff`，确认保留 `frontend/src/app/App.tsx`、`frontend/src/features/assistant/parameter/ParameterAssistantPanel.tsx`、`frontend/src/styles.css` 中已有 Excel 导入调整
- [x] T002 复核 `backend/app/services/ai_resource_scheduling_assistant.py`、`backend/app/models.py`、`frontend/src/types/scheduler.ts` 和 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 的当前初始化数据流

---

## Phase 2：基础能力（阻塞前置）

**目标**：建立共享响应字段和前端类型，所有用户故事基于同一契约实现。

- [x] T003 在 `backend/app/models.py` 为 `ResourceAssistantInitialResponse` 增加向后兼容的 `llm_generation_context` 响应字段
- [x] T004 [P] 在 `frontend/src/types/scheduler.ts` 定义六分区 `ResourceAssistantLlmGenerationContext` 并扩展 `ResourceAssistantInitialResponse`

**检查点**：后端响应和前端类型已对齐，可开始同源上下文与页面下载实现。

---

## Phase 3：用户故事 1 - 下载三方案生成依据（优先级：P1）

**目标**：三方案初始化成功后，用户可下载与实际 LLM 生成调用完全一致的项目上下文。

**独立测试**：捕获三方案生成函数收到的上下文并与响应字段逐字段比较；页面生成三方案后下载文件并解析六个分区。

### 用户故事 1 的测试

- [x] T005 [US1] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加上下文同源、六分区完整性、当前资源需求统计和敏感配置排除测试，并确认新增测试在实现前失败

### 用户故事 1 的实现

- [x] T006 [US1] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 将 `_llm_generation_context` 提升为唯一构造函数，并让初始化流程复用同一对象完成 LLM 调用和响应返回
- [x] T007 [US1] 在 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 增加响应上下文下载状态、UTF-8 JSON Blob、时间戳文件名、链接展示和对象 URL 回收
- [x] T008 [US1] 在 `frontend/src/styles.css` 增加 AI 多方案比选下载链接的桌面与窄屏样式，保持入口仅位于页面主操作区

**检查点**：外部 LLM 正常生成场景下，下载内容与实际生成上下文完全一致。

---

## Phase 4：用户故事 2 - 在回退场景核查预备输入（优先级：P2）

**目标**：本地 Provider 和外部调用失败回退时仍可下载已准备的上下文，整体请求失败时不沿用旧链接。

**独立测试**：分别运行本地回退、模拟外部失败回退和初始化整体失败，核对响应字段及页面入口状态。

### 用户故事 2 的测试

- [x] T009 [US2] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加本地 Provider、外部调用成功和外部调用失败回退三种上下文返回测试

### 用户故事 2 的实现

- [x] T010 [US2] 在 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 完善再次生成、场景变化和初始化失败时清除旧下载状态的逻辑

**检查点**：成功响应始终可下载本次上下文，失败响应不会展示上一轮入口。

---

## Phase 5：收尾与横切事项

**目标**：完成兼容性、构建和端到端验收。

- [x] T011 [P] 运行 `python -m pytest backend/tests/test_ai_resource_scheduling_assistant.py -q` 并记录测试结果
- [x] T012 [P] 在 `frontend/` 运行 `npm.cmd run build` 并确认 TypeScript 与 Vite 生产构建通过
- [x] T013 按 `specs/025-llm-project-context-export/quickstart.md` 验证下载文件名、中文内容、六分区、重新生成替换、场景变化失效和整体失败清除
- [x] T014 检查 `specs/025-llm-project-context-export/spec.md`、`plan.md`、`tasks.md` 与最终代码一致，并准备 `$speckit-converge` 收敛检查

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1**：无依赖，先确认工作区安全边界。
- **Phase 2**：依赖 Phase 1，阻塞所有用户故事。
- **US1（Phase 3）**：依赖 Phase 2，完成核心下载闭环。
- **US2（Phase 4）**：依赖 US1 的上下文响应和下载状态，补齐回退与失败行为。
- **Phase 5**：依赖 US1、US2 完成。

### 单个故事内部顺序

- 测试任务先于对应实现任务。
- 响应模型和前端类型先于服务与页面接入。
- 后端同源上下文先于前端下载入口验证。
- 核心成功流完成后再补回退和失败状态。

### 并行机会

- T003 与 T004 修改不同文件，可并行。
- T007 与 T008 在页面逻辑确定后可由不同人员并行，但合并时需共同验证样式类名。
- T011 与 T012 可并行执行。

---

## 并行示例：用户故事 1

```text
Task: "扩展后端初始化响应模型：backend/app/models.py"
Task: "扩展前端初始化响应类型：frontend/src/types/scheduler.ts"

基础契约完成后：
Task: "实现下载交互：frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx"
Task: "实现下载样式：frontend/src/styles.css"
```

---

## 实施策略

### MVP 优先

1. 完成 Phase 1 和 Phase 2。
2. 完成 US1，实现成功初始化后的真实上下文下载。
3. 运行后端同源测试和前端构建。
4. 再完成 US2 的回退与失败状态。

### 增量交付

1. 先建立向后兼容响应字段和前端类型。
2. 接入唯一上下文构造函数，证明发送与返回同源。
3. 增加页面下载入口和文件生命周期。
4. 补齐本地回退、调用失败回退和整体失败状态。
5. 完成自动与页面验证后进入收敛检查。

## 备注

- 全部任务遵循 `- [ ] Txxx [P?] [US?] 描述 + 文件路径` 格式。
- 不新增依赖、不修改 README、不提交 Git、不扩充现有 LLM 上下文信息量。
