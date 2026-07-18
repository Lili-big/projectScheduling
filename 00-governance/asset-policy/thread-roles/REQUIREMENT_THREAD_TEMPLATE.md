# 单需求主责 Thread 初始化模板

本模板用于创建真实需求的主责 Thread。主 Thread 在整个工作项中保持唯一 DRI，并按需加载本目录中的能力契约；Subagent 只承担主 Thread 划定的临时子任务。

```yaml
work_id: "<唯一需求或规格编号>"
title: "<用户可识别的需求名称>"
objective: "<一句话可验证目标>"
source_paths: ["<调研、决策、PRD、规则、spec 或缺陷证据路径>"]
acceptance: ["<用户可观察或机器可验证的验收条件>"]
risk_level: "low | medium | high | release-gate"
lane: "fast | standard | formal"
required_capabilities: ["<L02 | L03 | L06 | D01 ... D07>"]
allowed_paths: ["<允许修改的路径；未知时先完成范围澄清>"]
excluded: ["<明确不做的事项>"]
validation: ["<应运行的最小验证命令>"]
user_confirmation_gates: ["<没有则写 none>"]
close_conditions:
  - "acceptance_met"
  - "validation_recorded"
  - "remaining_risks_reported"
```

## 主 Thread 启动动作

1. 读取根目录 `AGENTS.md`、`registry.yaml`、项目手册和需求来源。
2. 声明资产归属，确认 `WORK_ID`、范围、验收、风险和执行通道。
3. 完整读取 `required_capabilities` 对应契约；这些能力在当前 Thread 内生效，不触发跨 Thread 交接。
4. 根据任务图决定是否使用 Subagent。并行写任务应为每个 Subagent 指定互不重叠的 `allowed_paths`；共享文件串行处理或使用隔离 Worktree。
5. 主 Thread 汇总所有结果、核验实际 diff、运行最终门禁并完成用户交付。

## 收口记录

```yaml
work_id: "<与初始化一致>"
status: "completed | blocked | cancelled"
changed_paths: ["<实际变更路径；无变更写 none>"]
validation_results:
  - command: "<实际命令>"
    result: "PASS | FAIL"
evidence_paths: ["<机器可读结果、报告、截图或日志路径>"]
subagent_summary: ["<子任务与结果；未使用写 none>"]
remaining_risks: ["<没有则写 none>"]
decision_needed: "<没有则写 none>"
```
