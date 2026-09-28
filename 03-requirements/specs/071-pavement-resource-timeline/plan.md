# 实施计划：单机资源时间图与沥青恢复

**目录**：071-pavement-resource-timeline | **日期**：2026-09-27 | **规格**：[spec.md](./spec.md)  
**状态**：厚度校验和最新用户批注授权的资源时间图均已完成并验证，累计8/9任务；底部精简T005b暂缓。不新建或切换Git分支，保护现有未提交修改。

## 概要与技术上下文

使用现有Python/FastAPI/OR-Tools与TypeScript/React19前端。厚度校验修订已完成，本轮新增资源时间视图，结果底部精简暂缓。没有新依赖、HTTP字段或存储结构。历史沥青恢复验收为19段95任务；用户随后停用全部沥青，当前19段76任务，图按同次输入中的实际资源ID生成，适用于多个实际机组。

生命周期沿用[规格归属](./spec.md#生命周期归属)。主数据与配置属本地持久状态；同次结果投影属前端内存，验证证据归.local-data/logs/。历史V32与V51保留，不做全库回滚。

## Constitution检查

设计前/后均通过：来源与验收明确；长度厚度例外按计量单位定义，不按名称硬编码；所有输入输出与降级口径见data-model及contracts；无CP-SAT目标改动或新增持久字段；指标不作求解目标。资产沿用合法目录，数据不清理。实施门禁为用户确认tasks及一致性结果。

## 设计决策

### D1 已授权的数据操作与长度校验

19个在用段各追加一层沥青，V51保存；厚度密度为空。现有配置已保存FS+7及沥青转场1天，工效1000m/天原值已回读；数量0与停用仍保留给用户自行维护。证据目录.local-data/logs/20260927-210701-restore-asphalt/，不重复数据操作。

修改app/project_master/validation.py的pavement_quantity_errors：单位m时跳过厚度计算校验，不使用厚度取值；其余单位不改，宽度与长度既有检查保留。几何m的数量一致性须仅依据有效净长，不能因少了厚度而跳过比较。此函数已被主数据投影、生成器、直接求解共享，无需改共享协议或绕过错误。更新把“按米缺厚度”固定为错误的相关测试，改用缺净长继续证明必要缺项拒绝，其他单位仍拒绝非法厚度。

### D2 时间投影

扩展pavementViewModel.ts导出buildResourceTimeline；不增加通用图表抽象。输入仅同次result/generated，结果资源由已分配ID与generated中启用资源并集组成，禁止读取当前scenario来解释历史结果。空资源给出空态，未分配任务不硬塞给机组。

时间以[start,end)自然日偏移计算。图轴从计划0日到所有有效任务最大结束边界/可信施工完成偏移，等待不延长资源占用。每行分析期为该机组首作业开始至末作业结束；轴上期外部分仅称“作业期外”。先排序、检测重叠，再对有效作业/转场分别取并集，计算占用补集；正常数据作业+转场+期间空闲=分析期，作业率=作业天数/分析期。

转场必须匹配资源及相邻前后任务、位于两者间、偏移有效，不与作业重叠。同已知位置或本次资源明确transfer_days=0可确认零转场；其他缺记录的间隙为信息不足。重叠/越界/缺记录时保留作业事实、提示局部问题，转场/空闲结论降级为“—”，不能静默假定0；无效时间或作业重叠时利用率也为“—”。工艺等待不作为资源占用来源。

### D3 资源横道及交互

新增PavementResourceTimeline.tsx，位于施工任务表图和机组施工顺序之间，标题“机组作业与空闲”。默认每套资源一行，共用日期轴；可筛选单机。左侧显示名称与作业率，右侧显示作业/转场/空闲时间片，下面显示当前资源汇总与所选时间片详情。最长空闲提供定位入口；作业显示段/工序，转场显示前后任务，空闲显示前后作业和事实日期，不生成原因诊断或窝工评级。

沿用dateAt、现有样式令牌和内部滚动模式；左列及刻度粘顶/冻结，短片用独立点击热点而不改变真实宽度。图例、可读文字和button aria-label支持键盘，条块焦点可见。稳定选择key使用资源ID+片类型+源任务ID，实时更新后仍存在则保留，失效时回退。条日期最后一天按end-1展示。

### D4 结果精简与错误承接（T005b暂缓）

ScheduleResultsWorkspace.tsx移除输入来源和计算耗时details；顶部进度/状态仍保留。Workspace.tsx路面分支移除底部数据与排程诊断块，筛选level=error移至求解工具栏附近简短alert展示，不隐藏失败。重复info/warning不再放到底部；必要移交前提在原日期表，原始响应/任务视图诊断与桥梁分支不改。无方案提示指向上方待处理项，不留下“查看已删除诊断”的指引。

## 精确修改边界

- 04-demo/backend/app/project_master/validation.py：单位m厚度可空、几何数量校验。
- 04-demo/backend/tests/test_pavement_master.py、test_pavement_generation.py、test_pavement_layer_template.py、test_pavement_solver.py、test_pavement_api.py：受影响既有断言及生成/求解/未知吨位的验收。
- 04-demo/frontend/src/features/scheduleResults/pavementViewModel.ts、ScheduleResultsWorkspace.tsx、styles.css；新增同目录PavementResourceTimeline.tsx。
- 04-demo/frontend/src/app/Workspace.tsx：路面错误承接；不重构桥梁部分。
- 04-demo/frontend/tests/pavementVisualization.test.mjs、pavementResults.test.mjs：投影不变量和组件静态渲染。现有测试装载器只做新组件依赖适配。
- 本目录设计产物、03-requirements/specs/README.md、agent.md、04-demo/README.md。

研究见[research.md](./research.md)，派生字段见[data-model.md](./data-model.md)，UI及校验口径见[contracts/resource-timeline.md](./contracts/resource-timeline.md)，最小验证见[quickstart.md](./quickstart.md)。

.specify/scripts/powershell/update-agent-context.ps1在仓库不存在（Test-Path=False）；不创建替代脚本，在agent.md手动记规划状态。

## 验证与复杂度

定向pytest和两组前端Node测试各一次，前端build一次，真实页面检查恢复/错误与合成或只读历史结果时间片。真实数量0时不为验收修改用户资源、不假造95任务已求解。只有新改动/失败才重跑相关部分。创建规格运行仓库/生命周期/文档检查，历史缺陷分类保留。无复杂度例外；不引入图表库、自动续算或后台任务。
