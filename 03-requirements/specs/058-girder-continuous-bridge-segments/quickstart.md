# 快速验收：连续结构桥梁分段与线路图清晰展示

## 1. 最小验证命令

```powershell
python -m pytest 04-demo/backend/tests/test_girder_plan_simulation_topology.py 04-demo/backend/tests/test_girder_plan_simulation_validation.py 04-demo/backend/tests/test_girder_plan_simulation_api.py -q
node --test 04-demo/frontend/tests/girderPlanSimulation.test.mjs
npm.cmd run typecheck
```

如共享契约或演示镜像触发架构基线变化，再执行：

```powershell
npm.cmd run verify:architecture
```

## 2. 正常三段样例

准备一个已确认项目主数据版本，其中右幅桥梁落位为 `K1000+000～K1000+800`，上部结构依次为：

| 跨序 | 类型 | 长度 | 预制梁 |
| --- | --- | ---: | --- |
| 1 | `simple_span` | 200m | T32 10片 |
| 2 | `continuous_unit` | 300m | 无 |
| 3 | `simple_span` | 300m | T40 15片 |

验收：

1. 请求 `GET /api/girder-plan-simulation/line-graphs/{project_master_version_id}`。
2. `projection_version` 为 `girder-plan-line-graph/v3`。
3. 该幅包含 `approach_small/continuous/approach_large` 三个节点，里程分别为 `0～200/200～500/500～800` 的相对区间。
4. 两个引桥节点分别携带 T32 10片、T40 15片并为待架目标；连续节点无梁片且非待架。
5. 人工顺序选择“小里程引桥段→大里程引桥段”后，方案校验的 `expanded_routes` 必须在两者之间包含连续结构段。

## 3. 页面验收

打开“架梁计划推演”并选择泸古 1 标已确认主数据版本：

1. 左右幅仍为两条平行线路，空间对应关系不变。
2. 所有工点名称完整显示，无省略号；相邻名称交替位于两行，允许水平重叠。
3. 桥梁和隧道在线路主体只显示粗线段，无圆形桥隧图标。
4. 三段式桥梁在线路原里程范围内显示三个连续粗线段；名称明确包含三种段别。
5. 点击分段名称或诊断仍能聚焦正确对象，风险状态和完整里程提示可见。

## 4. 阻断样例

分别构造以下数据并确认线路图状态为 `blocking`：

- 连续结构缺 `span_length_m`；
- 两个连续结构区块被简支跨隔开；
- 连续结构位于桥头，缺小里程引桥；
- 结构总长比落位长度多 2 米；
- 连续结构包含启用的 `precast_beam` 构件。

每个诊断必须包含稳定 code、桥梁幅别 subject、源结构引用和修正建议。保留的整桥节点只能用于定位，生成计划按钮不可产生可确认结果。

## 5. 兼容验收

1. 普通简支桥、路基、隧道节点 ID 与 v2 相同。
2. 加载引用旧整桥目标的历史方案，方案标记为失效或校验返回无效目标，不自动增加两个引桥目标。
3. 历史运行仍可查看，但不能用 v3 当前指纹再次确认。
4. 页面和结果仍声明“不写入现有架梁专项与综合排程”。
