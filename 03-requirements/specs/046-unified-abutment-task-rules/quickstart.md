# 快速验证：统一桥台任务生成、工期与资源规则

**状态**：实施后的可复现验证指南；当前仅用于计划与验收

## 1. 前置条件

- Python 3.12 与项目 `.venv` 可用。
- Node.js 22 与前端依赖已安装。
- 使用固定样例：一个历史 `bridge_abutment + cap_beam` 非桩构件、一个桥台桩基、一个桥墩盖梁、两个可并行桥台主体任务。
- 未经用户确认 `tasks.md` 和规格分析结果，不执行实现。

## 2. 场景 A：项目主数据规范投影

运行：

```powershell
.\.venv\Scripts\python.exe -m pytest 04-demo\backend\tests\test_project_master_adapter.py -q
```

预期：

- 历史桥台 `cap_beam` 投影为 `abutment_body`。
- 桥台桩基仍为 `pile`，来源 ID、数量和参数保持。
- 桥墩 `cap_beam` 仍为 `cap_beam`。
- 投影来源包含当前 `scheduling_projection_version`。

## 3. 场景 B：任务、工期与资源语义

运行：

```powershell
.\.venv\Scripts\python.exe -m pytest 04-demo\backend\tests\test_scheduler.py -q -k "abutment or unlimited"
```

预期：

- `abutment_body` 任务使用“桥台施工”。
- 数量 1 个时 `duration_days=15`。
- 默认场景与部署配置中不存在 `abutment_team` 资源池。
- `compatible_resource_types=[]`。
- `ScheduleInput.resources` 和资源分配中无 `abutment_team`。
- 两个无其他互斥约束的桥台任务不因资源而串行。

## 4. 场景 C：HTTP 契约与历史重新投影

运行：

```powershell
.\.venv\Scripts\python.exe -m pytest 04-demo\backend\tests\test_scheduling_routes.py 04-demo\backend\tests\test_architecture_api_contract.py -q
```

预期：

- 现有生成/求解路径和状态码保持兼容。
- 带历史 `project_data_version_id` 的请求在每次生成/求解时使用当前投影规则。
- `source_summary` 包含项目主数据版本和投影规则版本。
- 旧投影版本的派生结果被识别为过期。

## 5. 场景 D：验证工作包输出

按工作包 README 运行项目主数据生成脚本，并检查输出工作簿：

```powershell
node 01-customer-validation\泸古1标\validation-results\_scripts\build_lugu_project_master.mjs
```

预期：

- `bridge_abutment` 的非桩构件输出 `component_type=abutment_body`。
- 桥台桩基仍输出 `pile`。
- 桥墩盖梁仍输出 `cap_beam`。
- 数据验证列表同时允许 `abutment_body` 和 `cap_beam`。

## 6. 场景 E：工作台展示

运行：

```powershell
npm.cmd --workspace 04-demo/frontend test
npm.cmd run build
```

预期：

- 任务视图展示“桥台”“桥台施工”“15 天”和通用无受限资源状态。
- 空态、错误态使用通用路径。
- 前端测试不依赖桥台名称、ID 或 10/15 特殊值修正。
- 行为测试用可控请求顺序覆盖映射未就绪、全量成功、任一失败、失败重试、版本快速切换和旧请求晚到。
- `loading` 期间不渲染任务名称 rows；`error` 期间显示通用错误/不可用态和重试。
- 全量成功后一次性展示同一 `project_data_version_id` 的权威名称；任一场景中原始 ID 和 `"-"` 冒充名称次数均为 0。
- 旧请求晚到不会覆盖新版本映射，部分成功映射不会提交。

## 7. 场景 F：禁止硬编码扫描

运行受影响路径的静态扫描与人工复核：

```powershell
rg -n -i "台帽|bridge_abutment|abutment|A0|AB|duration_days.*(10|15)|bridge_id.*\?\?|work_section_id.*\?\?" 04-demo\backend\app\project_master 04-demo\backend\app\scheduling 04-demo\frontend\src\app\Workspace.tsx 04-demo\frontend\src\features\taskView 04-demo\frontend\src\features\projectMasterData
```

验收方式：

- 允许规范枚举、标签、测试数据和投影规则出现。
- 不允许以名称、ID、字符串或 10/15 特殊值决定构件类型、工期、资源或展示结果。
- 每个命中项由 D06 分类记录为“规范字段/标签/测试”或“需移除的业务分支”，最终需移除分支数为 0。
- 允许内部稳定键使用 ID；不允许把 ID 或 `"-"` 渲染为工点、桥梁、工区或幅别最终名称。

## 8. 回归门禁

```powershell
.\.venv\Scripts\python.exe -m pytest 04-demo\backend\tests -q
npm.cmd --workspace 04-demo/frontend test
npm.cmd run build
npm.cmd run verify:architecture
```

回归必须证明桥台桩基、桥墩盖梁、共享 API 契约和前端构建均未退化。
