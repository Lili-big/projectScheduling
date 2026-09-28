# 研究与设计决策

日期：2026-09-26。没有新增依赖或待外部调研的阻塞问题；以下复用本任务已核实的证据。

| 决策 | 选择及理由 | 已评估替代方案 |
|---|---|---|
| D1 初解方式 | 三种确定性贪心规则，统一数值校验后选最短完整计划 | 继续纯CP-SAT不能解决无首解回退；用户选择了组合算法 |
| D2 优化方式 | AddHint＋合法工期上界，原模型继续搜索 | 固定初解路线会失去跨段穿插优化；本轮不新增ALNS/局部搜索 |
| D3 预算与界面 | 共用原总预算，一次同步返回；记录内部阶段耗时 | 流式/后台展示需新增会话状态和接口，用户尚未要求 |
| D4 结果状态 | 计划状态与优化状态分离；合法初解可作为FEASIBLE | 将CP-SAT UNKNOWN直接作为整体结果会丢失已存在计划 |
| D5 兼容范围 | 数值校验保留四关系、多机组、锁定、里程碑和配套；贪心失败可冷启动 | 只接受单机组FS会缩减既有能力；贪心失败不能证明无解 |
| D6 模型优化 | 仅证明安全的FS逆向/后置逆向边剪枝，原全局约束保留 | 广泛按DAG删边会误伤SS/FF/SF和跨机组场景 |
| D7 可测性 | 真实100任务性能＋小样例确切工期＋受控超时状态 | 只看总体耗时或只看求解状态不能证明首解/回退正确 |
| D8 不变边界 | 数据、机组、工效、目标、历史结果、桥梁保持 | 不通过减任务、增资源或放宽养生达到性能指标 |

## 已核实的公开依据

- [约100任务、带切换的CP-SAT性能案例](https://stackoverflow.com/questions/78249305/or-tools-cp-model-performance-for-flexible-job-shop-scheduling-with-transitions)：30组、每组3—5工序、8机器；作者报告首次出解曾500秒。属于开发者复现实验，不是公路项目性能保证。
- [Laurent Perron的已采纳答复](https://stackoverflow.com/a/78249465)：建议先编写贪心首解再提示CP-SAT，指出顺序相关setup的中等规模问题也很难证明最优。
- [ALNS资源受限项目排程示例](https://alns.readthedocs.io/en/latest/examples/resource_constrained_project_scheduling_problem.html)：90作业4资源，先构造计划再优化；本轮只参考生成器思想，不引入ALNS依赖或其局部搜索流程。
- [OR-Tools官方单机setup/release/due示例](https://github.com/google/or-tools/blob/stable/examples/python/single_machine_scheduling_with_setup_release_due_dates_sat.py)：可参考区间、路线及边界建模，不将其中特殊无空闲等假设复制为本项目业务规则。

## 当前代码证据

现有策略直接调用Solve、单worker、无提示；结果转换直接读取solver值，因此需要提取数值候选统一转换。资源路线模块提供assignment/arc但首尾变量尚未对外收集。前端hasPlan依赖整体FEASIBLE/OPTIMAL及pavement_summary，故仅向stats塞入初解而不生成完整结果不能满足回退展示。

当前未获得搜索详细日志，不能把稠密连接宣称为唯一性能根因；实施会分别记录初解、建模和优化耗时。本轮不改变线程数，以便测出初解引导的实际增益。

