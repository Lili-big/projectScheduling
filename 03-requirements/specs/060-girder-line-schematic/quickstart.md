# 验证指南：架梁双幅线路示意图优化

## 前置条件

- 工作目录：仓库根目录。
- Python 3.14、Node.js 24 和前端依赖已安装。
- 不修改或清理 `.local-data/` 中的用户状态。
- 泸古项目已确认主数据版本可用于浏览器验收时，可额外执行第 4 节；自动化测试不依赖该本地状态。

## 1. 后端三段投影与反例回归

```powershell
python -m pytest 04-demo/backend/tests/test_girder_plan_simulation_topology.py -q
```

预期结果：

- 结构累计长度与线路落位长度不同的连续梁仍生成三段节点。
- 不存在 `BRIDGE_SEGMENT_LENGTH_MISMATCH` 诊断。
- 左右幅分别使用本幅结构比例，三段顺序与结构引用稳定。
- 缺失长度、多连续区块、缺失引桥和连续结构预制梁冲突反例仍阻断。

## 2. 前端线路示意契约

```powershell
Set-Location 04-demo/frontend
node --test tests/girderPlanSimulation.test.mjs
npm.cmd run typecheck
npm.cmd run build
```

预期结果：

- ZK/K 只形成两条主线。
- AK/BK/B1K 进入互通支线层，不与主线工点重叠。
- 路基是普通细线，桥梁和隧道是不同粗线区段，梁场在线路外。
- 单幅缺失工点无占位框，名称支持错行、省略和悬浮全称。
- 不存在人工连接选择入口和长度差异提示。

## 3. 相关后端与兼容验证

```powershell
python -m pytest 04-demo/backend/tests -q -k "girder_plan_simulation"
```

预期结果：现有线路图、方案、校验、运行、指纹和失效测试保持通过；性能样例仍满足单次不超过 10 秒。

## 4. 泸古项目浏览器验收

按照 `04-demo/runtime/README.md` 的现有方式启动或复用本地 Demo，打开“架梁计划推演”，选择当前已确认泸古主数据版本。

检查项：

1. 两河口大桥和永宁河特大桥左右幅均出现三段示意，共 12 个稳定节点。
2. 页面不再显示 4 条 `BRIDGE_SEGMENT_LENGTH_MISMATCH`。
3. 当前项目若仍显示阻断，只允许来自 `MILEAGE_OVERLAP`、`LINE_GRAPH_GAP` 或其他本功能范围外诊断；不得把这些诊断误报为本功能已解决。
4. ZK/K 主线保持连续；渠坝互通 AK/BK/B1K 节点在支线层清晰可辨。
5. 梁场新增后在线路外显示，位置与部署节点或中心里程一致。
6. 缩放到常用桌面宽度时优先看到全线总览；长名称省略后悬浮可见全称。

## 5. 完成边界

- 自动化验证通过不等同于项目浏览器验收完成。
- 本功能不消除范围外的里程重叠、线路断点或缺失主数据诊断。
- 页面示意分段不得作为工程测量、施工放样或设计里程依据。
