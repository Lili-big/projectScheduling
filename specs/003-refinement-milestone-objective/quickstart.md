# 快速验证：精排里程碑与工期目标函数调整

## 前置条件

- 已完成 `specs/003-refinement-milestone-objective/tasks.md` 中的实现任务。
- 本地 Python 和前端依赖可用。
- 不需要数据库迁移或额外环境变量。

## 验证场景 1：硬里程碑在精排中必须满足

1. 运行后端测试中硬里程碑相关用例：

   ```powershell
   python -m pytest backend/tests/test_scheduler.py -k "hard_milestone"
   ```

2. 预期结果：
   - 可满足硬里程碑的精排结果中，硬里程碑 `lateness_days = 0`。
   - 不可满足硬里程碑的精排场景不会返回硬里程碑迟延的精排主方案。
   - 固定资源快排迟延硬里程碑的既有参考排程行为仍通过。

## 验证场景 2：软控制节点迟延进入最高权重目标

1. 运行软控制节点相关测试：

   ```powershell
   python -m pytest backend/tests/test_scheduler.py -k "soft_control"
   ```

2. 预期结果：
   - 软控制节点迟延计入 `control_lateness_days`。
   - `weighted_objective` 中包含 `control_node_late` 的最高权重贡献。
   - 普通软里程碑迟延不计入 `control_node_late`。

## 验证场景 3：总工期目标不再包含软里程碑迟延

1. 运行目标函数相关测试：

   ```powershell
   python -m pytest backend/tests/test_scheduler.py -k "objective"
   ```

2. 预期结果：
   - `makespan_and_soft_milestone` 的贡献只来自总工期。
   - `soft_milestone_penalty` 仍可在目标拆解中展示为诊断。
   - `weighted_objective` 不再叠加普通软里程碑迟延罚分。

## 验证场景 4：前端和文档口径

1. 运行前端构建：

   ```powershell
   npm --prefix frontend run build
   ```

2. 执行静态搜索：

   ```powershell
   rg -n "强控节点晚点|总工期及软节点偏差|软节点允许超期，迟延天数会进入加权目标" frontend/src docs
   ```

3. 预期结果：
   - 前端目标配置显示“软控制节点迟延”和“总工期”。
   - 新版算法文档不再把软里程碑迟延写入总工期目标公式。
   - 搜索结果中不应出现旧目标项文案作为当前口径。

## 验证场景 5：格式和范围

1. 运行格式检查：

   ```powershell
   git diff --check
   ```

2. 预期结果：
   - 无尾随空白或格式错误。
   - 改动范围集中在求解器、测试、前端目标配置和算法文档。
