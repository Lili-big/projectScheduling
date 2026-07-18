# Quickstart：工点级资源配置验收

## 1. 前置条件

- 使用当前确认的 `project_data_version_id`。
- 固定两个桥梁工点 `WP-A`、`WP-B`；名称可任意，验收不得依赖名称。
- 每个场景保存原始 `ScenarioInput`、生成的 `ScheduleInput`、求解结果和页面证据。
- 实施前必须先由用户确认 `tasks.md` 与 analyze 结果。

## 2. 场景 A：工点独享与继承

输入片段：

```json
{
  "id": "pool-drill",
  "type": "rotary_drill",
  "label": "旋挖钻",
  "resource_mode": "LIMITED",
  "scope_mode": "WORKPOINT_EXCLUSIVE",
  "quantity": 1,
  "max_quantity": 3,
  "authorized_workpoint_ids": ["WP-A", "WP-B"],
  "workpoint_overrides": [
    {"workpoint_id": "WP-A", "quantity": 2, "max_quantity": 4}
  ]
}
```

预期：固定资源生成 `WP-A=2`、`WP-B=1` 个实例；每个实例 eligible 只含自身；A/B 任务跨工点候选为 0；B 来源为 inherited，默认充足诊断为 0。

## 3. 场景 B：项目共享串行与转场 0 天

输入：共享池 `quantity=1,max_quantity=2`，获准 A/B；A/B 各有一个 5 天任务且无前置。

预期：

- `ScheduleInput.resources` 只有一个固定资源实例；
- A/B 两任务都能候选该实例，但资源分配区间不重叠；
- 两任务资源占用跨度至少 10 天，跨工点额外转场为 0 天；
- 配置页和结果页均出现统一 0 天提示；
- 名称、ID 格式或特殊数量分支命中 0。

## 4. 场景 C：三类数量语义

有效池 `quantity=3,max_quantity=5`：

1. 固定资源求最短工期：断言资源实例数为 3。
2. 增配建议：断言所有候选容量在 3～5。
3. 固定工期最少资源：构造 2 个实例可行的目标，断言推荐可为 2，`current_quantity=3`，不被抬高。
4. 全仓扫描新增字段，断言 `min_quantity` 为 0 个新增命中。

## 5. 场景 D：受限资源缺失与显式 UNLIMITED

- D1：任务需要 `rotary_drill`，资源池已启用、`LIMITED` 且正上限，但其工点不在获准范围。预期生成/求解阻断，不出现默认充足成功结果。
- D2：同资源池显式 `resource_mode=UNLIMITED`。预期不展开命名资源，任务按统一默认充足语义处理并有说明。
- D3：同资源池显式停用或上限为 0。预期沿用既有默认充足 warning，并与继承状态区分。
- D4：工点无 override。预期继承全局受限值，行为不同于 D2/D3。

## 6. 场景 E：旧配置兼容

输入旧池只含现有字段，无 `scope_mode/authorized_workpoint_ids/workpoint_overrides`。

预期：读取为项目共享、全部当前桥梁工点、无覆盖；固定资源数量和现有全项目互斥结果保持；再次保存输出标准字段；不修改旧文件原文，不调用项目特例迁移脚本。

## 7. 场景 F：版本、空态与错误

- 当前版本无桥梁工点：资源页展示空态，禁止虚构工点。
- override 引用旧版本 ID：后端 422 或等价阻断，页面保留输入并提示。
- 快速从版本 V1 切 V2 且 V1 请求晚到：V1 工点/覆盖提交次数为 0。
- 保存失败后点击重试：输入不丢失，成功后以返回标准配置刷新。

## 8. 场景 G：AI 与持久化失效

- 共享池：旧 `resource_updates` 能更新项目共享数量且不改变作用域。
- 独享池：旧 map 输入被拒绝；结构化更新只修改指定工点。
- AI 不得新增资源类型/工点或改变获准范围。
- 修改任一作用域语义后，任务图、求解、AI 解释、方案对比和计划快照当前性全部失效；新指纹不同。

## 9. 建议验证命令

```powershell
python -m pytest 04-demo/backend/tests
npm.cmd --workspace 04-demo/frontend test
npm.cmd --workspace 04-demo/frontend run typecheck
npm.cmd --workspace 04-demo/frontend run build
npm.cmd run verify:architecture
python 00-governance/repository-tools/validate_docs.py
```

实施任务应先运行定向测试，再由 D06 按 tasks 指定的风险门禁独立复核；不重复无关全量测试。
