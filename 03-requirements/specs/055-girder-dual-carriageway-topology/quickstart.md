# 快速验证：架梁双幅线路拓扑

## 前置条件

- 已按功能 055 完成实现。
- 本地使用仓库推荐的 Python 3.12、Node.js 22，并已安装现有依赖。
- 不修改用户提供的源 Excel；验收读取其 `架梁通道（3片）` 工作表作为关系证据。

## 场景 A：项目主数据线路落位往返

1. 生成新版项目主数据模板，确认包含可选“线路关系”工作表。
2. 写入以下最小数据：一个同时具有左右幅的 `ZK/K` 主线工点；右幅 `AK` 节点；左幅 `BK` 节点；两个左右节点共享同一 `spatial_group_id`。
3. 导入、导出并再次解析。

**预期结果**：

- 路线落位字段和来源证据往返一致。
- 旧 1.0 模板不含“线路关系”表时仍可解析，`route_placements=[]`。
- 同工点同幅重复、终点小于起点或未知工点引用产生对象级导入错误。

## 场景 B：泸古语义生成两条线路

1. 选择一个已确认项目版本，其中主线工点具有左右幅结构，互通节点分别带 `AK/BK/B1K` 前缀。
2. 打开“架梁计划推演”。
3. 检查项目线路图及诊断。

**预期结果**：

- 页面只显示“左幅（ZK）”与“右幅（K）”两行。
- `AK/BK/B1K` 显示在对应节点上，不生成新行。
- 左右主线节点按共享空间组纵向对齐；单侧节点不会挤乱另一侧后续节点。
- 旧项目版本使用兼容投影时显示证据提示，但不再因左右平行或跨前缀区间产生 `MILEAGE_OVERLAP`。

## 场景 C：真实重叠和同行不连通

1. 在同一左幅、同一 `ZK` 前缀创建两个显式重叠区间。
2. 创建同一空间组的左、右节点，但不配置人工连接。
3. 重新生成线路图。

**预期结果**：

- 左幅真实重叠生成一个对象级 `MILEAGE_OVERLAP` 阻断诊断。
- 左右同行节点之间没有自动通行边。
- 用户确认横向连接后才出现带确认审计的人工边。

## 场景 D：既有方案兼容与失效

1. 使用 v1 投影创建包含梁场、人工桥梁顺序和计算结果的方案。
2. 升级到 v2 投影并加载同一方案。
3. 重新选择无法唯一定位的梁场部署并保存新版本，然后重算。

**预期结果**：

- 可唯一映射的桥梁幅别顺序保持不变。
- 旧运行标记为失效，历史快照仍可查询。
- 新梁场配置保存 `deployment_node_id`，新运行指纹包含 v2 投影并可生成结果。

## 最小验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest `
  04-demo\backend\tests\test_project_master_workbook.py `
  04-demo\backend\tests\test_project_master_repository.py `
  04-demo\backend\tests\test_girder_plan_simulation_topology.py `
  04-demo\backend\tests\test_girder_plan_simulation_api.py -q

node --test 04-demo\frontend\tests\girderPlanSimulation.test.mjs
npm.cmd --workspace 04-demo/frontend run typecheck
npm.cmd --workspace 04-demo/frontend run build
```

**通过标准**：全部命令退出码为 0，场景 A～D 的预期结果均可观察；现有架梁专项相关测试保持通过。
