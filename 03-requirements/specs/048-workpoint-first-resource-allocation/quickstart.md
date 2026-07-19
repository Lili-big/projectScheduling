# Quickstart：工点主导资源配置与范围共享流转验收

## 1. 前置条件

- 使用当前确认的 `project_data_version_id`。
- 固定三个桥梁工点 `WP-A`、`WP-B`、`WP-C`；名称可任意，验收不得依赖名称或 ID 格式。
- 固定资源类型 `team-x`，并为三个工点各准备一个需要 `team-x`、持续 5 天且无前置的任务。
- 保存每个场景的原始 `ScenarioInput`、标准化资源池、生成的 `ScheduleInput`、求解结果、诊断和页面证据。
- 用户确认 `tasks.md` 与最新 `$speckit-analyze` 结果前，不执行实现任务。

## 2. 场景 A：工点一级维护与目录补充

操作：

1. 进入资源配置，选择 `WP-A`。
2. 核对默认资源行包含 A 当前任务可能使用的 `team-x`。
3. 将 `team-x` 设置为 `quantity=2,max_quantity=4,enabled=true`。
4. 从资源目录补充一个当前任务未自动推导的类型 `generator`。
5. 保存并重载。

预期：

- 页面一级对象是 `WP-A`，不存在“该资源适用于哪些工点”勾选。
- A 的两条本地资源记录均携带 `workpoint_id=WP-A`。
- A 的修改不改变 B/C 的本地资源或任何共享池。
- 保存返回的标准配置以稳定池 ID 定位，不依赖数组下标。

## 3. 场景 B：数量 0 与缺口阻断

配置：

- A 本地 `team-x quantity=0,max_quantity=3,enabled=true`。
- 不创建覆盖 A 的正数量共享池。

预期：

- 当前资源生成时 A 本地命名实例数为 0。
- A 的 `team-x` 任务被阻断，诊断包含 `task_id=TASK-A`、`workpoint_id=WP-A`、`resource_type=team-x` 和相关池 ID。
- 诊断原因是本地数量为 0 或没有合法候选，不得按默认充足继续。
- 增配/最少资源入口可以在上限 3 内形成建议，但建议未采纳前当前资源计划仍保持阻断状态。

## 4. 场景 C：本地数量 0、共享池补位

配置：

- B 本地 `team-x quantity=0,max_quantity=2,enabled=true`。
- 共享池 `SHARED-1`：`team-x quantity=1,max_quantity=2`，范围 `[WP-A,WP-B]`。

预期：

- B 本地实例数为 0。
- B 的任务候选只包含 `SHARED-1` 的实例，不包含 A 的本地实例。
- 当前资源生成不产生 B 的缺口阻断。

## 5. 场景 D：同类型多个重叠共享池

配置：

- `SHARED-1`：`team-x quantity=1,max_quantity=2`，范围 `[WP-A,WP-B]`。
- `SHARED-2`：`team-x quantity=2,max_quantity=3`，范围 `[WP-B,WP-C]`。

预期候选：

- A 只获得 `SHARED-1`。
- B 同时获得 `SHARED-1` 和 `SHARED-2`。
- C 只获得 `SHARED-2`。
- 两个池的实例、当前数量、上限、成本和结果统计互相独立，不按 `team-x` 合并。
- 页面、AI 编辑和结果均能按两个池 ID 分别定位。

## 6. 场景 E：共享实例互斥与零转场

配置：

- 只保留 `SHARED-1 quantity=1`，范围 `[WP-A,WP-B]`。
- A/B 任务各持续 5 天且无前置。

预期：

- 两个任务都可候选同一实例，但资源占用区间不重叠。
- 任务先后由求解器确定，输入中不存在人工顺序字段。
- 两任务资源占用跨度至少 10 天。
- 从 A 到 B 或 B 到 A 均不增加转场任务、前置、持续时间或费用。
- 配置页、生成诊断和结果均显示转场时间 0 天、转场成本 0。

## 7. 场景 F：三类数量语义按池保留

配置：

- A 本地池：`quantity=2,max_quantity=4`。
- `SHARED-1`：`quantity=1,max_quantity=3`，范围 A/B。
- `SHARED-2`：`quantity=0,max_quantity=2`，范围 B/C。

分别验证：

1. 固定资源最短工期：实例数分别为 2、1、0。
2. 增配/资源成本：每池只在自己的 `[quantity,max_quantity]` 内搜索。
3. 固定工期最少资源：每池上界分别为 4、3、2，结果可以低于当前 `quantity`，但逐池返回。
4. 重叠范围容量下界不得把 B 的同一任务重复算作 `SHARED-1` 和 `SHARED-2` 各自的必需下界。

## 8. 场景 G：旧项目共享兼容

输入旧池：

```json
{
  "id": "legacy-shared-x",
  "type": "team-x",
  "label": "旧项目共享班组",
  "quantity": 2,
  "max_quantity": 4,
  "enabled": true,
  "authorized_workpoint_ids": ["WP-A", "WP-B"]
}
```

预期：

- 缺失 `scope_mode/workpoint_id/workpoint_overrides` 时读取为一个 `PROJECT_SHARED` 池。
- ID、2/4 数量、启用状态和 A/B 范围保持，工点拆分记录数为 0。
- 若缺少 `authorized_workpoint_ids`，则保持动态“全部当前桥梁工点”语义。
- 再次保存输出标准字段；不修改历史文件或快照原文。

## 9. 场景 H：047 legacy 独享迁移

输入：一个 `WORKPOINT_EXCLUSIVE` 旧池，全局 `quantity=1,max_quantity=3`，A 覆盖为 2/4，B 无覆盖。

预期：

- 可无损解析时生成 A=2/4、B=1/3 两条稳定工点本地记录。
- 新记录 `workpoint_id` 分别为 A/B，`workpoint_overrides=[]`。
- 未知工点、重复覆盖或 ID 冲突时整体迁移阻断，原载荷保留，不输出部分转换结果。

## 10. 场景 I：AI、计划快照与失效

- 使用 `resource_pool_id` 分别把 `SHARED-1` 和 `SHARED-2` 调整到不同数量，断言只修改目标池。
- 旧 `{team-x: quantity}` 更新在同类型多池时返回歧义错误；仅存在一个旧共享池时保持兼容。
- 资源助手、基准计划和预测快照保存两个池的完整身份与范围。
- 交换池列表顺序不改变指纹；修改任一池的 ID、工点、范围、数量、上限、状态或日历必须改变指纹。
- 指纹变化后旧任务图、求解、AI 解释、比较、预测和调整方案全部 stale，历史快照仍可查询。
- 计划调整只修改明确目标池，不按类型广播到同类型其他池。

## 11. 场景 J：页面状态与版本隔离

- 当前版本无桥梁工点：展示空态，不虚构工点。
- 共享池显式空范围：保存阻断；与“全部工点”区分。
- 快速从 V1 切换 V2 且 V1 请求晚到：V1 工点资源和共享范围提交到 V2 的次数为 0。
- 保存失败后重试：编辑内容不丢失，成功后以后端标准化返回值刷新。
- 结果页对同类型两个共享池展示两个来源池，不因标签相同而合并。

## 12. 性能与限时样例

构造中等规模样例：多个桥梁工点、至少 200 个受限任务、每种关键类型一个本地池和两个部分重叠共享池。

记录：

- 标准化与候选生成耗时；
- 命名资源、候选和可选区间数量；
- 固定资源、最少资源和成本求解状态与耗时；
- 达到现有时间预算时的 `UNKNOWN`/best-effort 行为。

不得为降低对称性引入未经确认的本地优先、池优先或人工流转顺序。

## 13. 规格阶段验证命令

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.specify\scripts\powershell\check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks
python 00-governance/repository-tools/validate_docs.py
git diff --check
```

## 14. 实施阶段建议命令

定向测试由 `tasks.md` 给出准确命令。最终 R3 统一执行本功能唯一一次全量：

```powershell
.\.venv\Scripts\python.exe -m pytest 04-demo\backend\tests -q
npm.cmd --workspace 04-demo/frontend test
npm.cmd --workspace 04-demo/frontend run typecheck
npm.cmd run build
npm.cmd run verify:architecture
python 00-governance/repository-tools/validate_docs.py
```

实施阶段先运行定向测试，各领域不重复全量与 build；完整门禁留给最终 R3。
