# Quickstart：验证现浇连续梁联级班组占用

## 前置条件

- 已安装后端依赖和 OR-Tools。
- 仓库根目录为 `D:\codex_workspace\排程算法`。
- 本功能实现后再执行以下验证；当前规格阶段不要求通过。

## 验证 1：连续梁任务仍能生成

目标：确认连续梁任务拆分和既有逻辑未被破坏。

命令：

```powershell
python -m pytest backend/tests/test_scheduler.py -k "continuous_beam_upper_structures_generate_t_groups_and_closure_logic or continuous_beam_left_and_right_standard_segments_solve_synchronously"
```

期望：
- 连续梁 0 号块、标准段、边跨连续段、合龙段仍按原粒度生成。
- 左右悬臂标准段同步测试继续通过。

## 验证 2：1 个连续梁班组跨联串行

目标：确认 `quantity = 1` 时跨联不能并行。

建议测试：
- 构造左幅和右幅各一联、下部结构均具备开工条件的场景。
- 将 `cast_in_place_continuous_beam_team.quantity` 设置为 1。
- 执行固定资源排程。

期望：
- `continuous_beam_team_spans.span_count >= 2`。
- 同一连续梁班组下任意两个联级占用窗口不重叠。
- 诊断不提示联内任务缺少资源。

## 验证 3：2 个连续梁班组允许两联并行

目标：确认 `quantity = 2` 时最多两联可并行。

建议测试：
- 沿用验证 2 的场景。
- 将 `cast_in_place_continuous_beam_team.quantity` 设置为 2。
- 执行固定资源排程。

期望：
- 左幅联和右幅联可分配到不同连续梁班组。
- 联级占用窗口允许重叠。
- 任意时刻并行占用的连续梁联数不超过 2。

## 验证 4：联内任务不因连续梁班组互斥

目标：确认同一联内任务不被班组任务级互斥强制串行。

建议测试：
- 使用包含左右悬臂标准段的连续梁场景。
- 检查同一联内左右标准段仍能同日开始和完成。
- 检查同一联内无直接工艺冲突的任务不会只因同属一个班组而错开。

期望：
- 联内并行行为由工艺逻辑决定。
- 联级班组占用只影响跨联等待。

## 验证 5：前端类型和结果展示兼容

命令：

```powershell
npm.cmd run build --prefix frontend
```

期望：
- 前端类型检查通过。
- 旧结果缺少 `continuous_beam_team_spans` 时不报错。
- 新结果能显示或至少保留联级资源归属信息，不把联内任务误判为资源缺失。

## 验证 6：回归范围

命令：

```powershell
python -m pytest backend/tests/test_scheduler.py
```

期望：
- 非连续梁资源互斥、同结构同工序、桩基墩组、里程碑和固定资源主链路测试继续通过。
