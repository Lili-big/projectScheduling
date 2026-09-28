# 验证指南：自动任务清单与统一工序链

实施完成；用户已确认10项任务。客户主数据和持久配置未改变，实际证据见下方实施记录。

## 实施记录（2026-09-24）

用户明确确认执行后，check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks执行一次，正确定位066；未启动子代理，未改客户配置或合并064。

### 代码与行为

- generation/pavement.py、solver/strategies/pavement.py：层间显式关系替代历史等待、保留非末层日期；排除末层养生/验收，不生成readiness。无中间任务时不生成跳层捷径。直接求解旧末层载荷给出重生成诊断，HTTP入口沿用422；新结果目标为earliest_construction_finish，完成日使用实际施工末日。
- LogicTab.tsx、domain/pavement.ts、domain-editors.css：统一关系链与分段覆盖；移除整块重复养生和末尾输入，保留已有非末层验收日期与折叠的配套/跨段配置。
- domain/pavement.ts、scenarioWorkflow.ts、Workspace.tsx：当前主数据形成行骨架，后端结果提供工期；独立预览按250ms合并请求，全项目范围，序号/指纹防过期响应，错误显式重试；不自动保存或求解。
- TaskViewWorkspace.tsx及样式：一张分段折叠表、真实工效方案选择、缺项行和关系状态、保存入口；移除模拟页手动生成入口。scheduleResults/presenter.ts及ScheduleResultsWorkspace.tsx使用施工完成口径，旧结果明确标识历史。
- 浏览器980px窗口发现既有导航height:100vh导致内容被挤出视口。仅在domain-editors.css追加路面作用域的窄屏高度/滚动修正；截图已确认工序链和任务表可见，桥梁样式不变。

### 自动验证

- 定义的三个后端测试文件：首次49通过、1失败；失败是新增API用例假定空readiness_conditions一定序列化，实际合同省略空字段。改为读取默认空数组后仅重跑该用例，1通过。合计50个唯一用例通过，未重复全量运行。
- 定义的四个前端测试文件：首次22通过。追加正/零天配套、固定引用、循环投影的必要覆盖后，仅重跑pavementTaskPreview.test.mjs，4通过；合计23个唯一用例通过。
- npm.cmd run build：首次TypeScript可选字段访问失败，补齐可选访问后通过；窄屏CSS调整后再次构建通过。保留既有Vite大于500kB的包体提示，未引入依赖或做无关拆包。
- git diff --check（本次相关已跟踪源码）：退出0；仅行尾格式提示，无空白错误。
- 交付文档校验validate_docs.py退出0。仓库验证器退出1，仍为原有requirements.txt缺架构依赖审批；生命周期验证器退出1，仍为原有7月资料/standalone查看器的9个missing-workpackage-reference。均与规划基线相同，不涉及本轮源码、依赖或新测试归属，记录为非核心既有失败，不扩展处理。
- 关键验收覆盖：25段100任务75边；1790/800=3、1790/1000=2；显式5天不叠加旧7天；四种关系有效；验收日期仍约束；单层/末层无条件可求解；旧载荷诊断；完成日期与末层里程碑无额外一天；065共享机组容量/转场回归通过。

### 真实服务与浏览器

- 核实原后端31404及其8000监听子进程10244的命令后，按runtime脚本定向重启；新启动PID40608，日志.local-data/logs/20260924-185202-121/backend.out.log与backend.err.log；health正常，8000已服务最新构建。
- 当前确认版本pmv-50a66eec36624a459aaf2ead8fb91142：真实API返回25段、100任务、75关系，首段四层均3天、FS+0/7/7，readiness为空。末层养生不再报缺项。
- 浏览器首次进入任务页自动显示全部任务；首段收起后四行消失。第1段关系临时改FS+5，任务表同步而第2段保持FS+7。工效库临时新增1000m/天方案，任务行选用后首段碎石由3天自动变2天，其他层仍3天。
- 未保存任何测试编辑；刷新丢弃临时方案/分段覆盖，最终停留工艺逻辑页，FS+0/7/7恢复。截图确认无下方重复养生表、无末层输入，其他配置默认收起。
- 测试前后scheduler-config.json SHA256均为50C257BB0461632145BAE6C36F2AED81065E8AB544A3978AFD1C37B414EC3782。主数据版本未变化。

### 验收限制

真实项目仍有7段无明确路床日期，对应7项主数据诊断及28条任务级诊断，另有零数量碎石资源池提示；本轮没有填写假日期，也未声称已完成真实项目全量求解。完整输入求解、共享资源和日期口径由合成案例证明；064路床三态仍独立待实施。

## 自动验证（实施后一个批次）

在仓库根目录执行：

```powershell
.venv/Scripts/python.exe -m pytest 04-demo/backend/tests/test_pavement_generation.py 04-demo/backend/tests/test_pavement_api.py 04-demo/backend/tests/test_pavement_solver.py -q
node --test --test-concurrency=1 04-demo/frontend/tests/pavementTaskPreview.test.mjs 04-demo/frontend/tests/pavementWorkflow.test.mjs 04-demo/frontend/tests/pavementResults.test.mjs 04-demo/frontend/tests/contractsCompatibility.test.mjs
npm.cmd run build
```

新增pavementTaskPreview.test.mjs由实施任务创建。仅对实际失败或新修改重跑相关验证；不启动桥梁全量浏览器性能测试。

## 最小场景

1. 25段各4个启用层，统一三条前置FS+0/7/7：API输出100核心任务、75关系；页面首次进入即显示全部，原模拟页无须先点生成。
2. 1790m、800m/天显示3天；改选1000m/天方案自动2天；核对实际method和方案覆盖、主数据继承以及非首个默认工艺，显示与后端一致。
3. 全部四种关系及分段覆盖，修改后只改变相关行；正天数配套进入正确位置，0天配套只影响条件；固定跨段前置显示来源段，不缩写成误导的同段关系。
4. 单位错误、失效方案及缺失层保留待完善行；未确认间歇不得显示FS+0，缺项中间层不得被跳过形成假确定关系；路床和层间关系错误保留而不隐藏已算工期，末层养生不再报缺项。
5. 用可控Promise让请求A晚于B返回，最终仅B展示；同指纹结果复用，离页响应不提交；失败可重试且不无限重试。自动预览前后持久文件内容不变，已有求解结果仍按指纹过期。
6. 统一/分段关系在同一工序链维护，无下方养生天数或批量输入。历史无显式规则的非末层7天可见；改为FS+5只约束5天，显式null仍待确认；保留已有非末层验收日期，FS/SS/FF/SF和正/零天配套不会被隐藏条件改成另一种关系。
7. 最小四层完整案例与单层段均无末层条件也可求解；历史末层7天和更晚验收日期不改变新生成施工完成；不产生readiness和末尾等待。仍明确执行跨段边、共享机组和转场。
8. 直接旧输入含末层readiness/非零条件时得到重生成诊断；新生成输入通过直接求解与场景求解结果一致。末层完成里程碑、plan_finish_date使用含末日的finish_date，不多一天；旧目标结果保留为历史并要求重算。缺失中间层不导致错误推断末层后放行求解。

## 浏览器验收

按04-demo/runtime/README.md更新实际服务和构建；先核对未保存状态。刷新并进入任务视图，核对25组/100核心任务、列宽、折叠及第一段3天和FS+0/7/7。临时改选方案验证更新后恢复原选择，除用户已有明确修改外不保存测试数据。检查保存入口及失败/重试行为，可用自动测试证明失败场景以免破坏客户数据。

同时检查工艺逻辑只显示一条可维护链，无重复养生块及末尾输入；统一/分段切换可用，配套和固定顺序仍可找到。当前FS+0/7/7不因删除输入改变；临时修改后恢复，不保存测试值。

真实项目尚缺路床条件时，明确区分任务准备可见与完整排程可用；不填造日期。末层缺项不再是排程阻断原因。

## 规划检查

2026-09-24规划批次实际记录：

- validate_docs.py：退出0，documentation links and API facts: OK (14 documents)。
- validate_repository.py：退出1，requirements.txt changed without architecture dependency approval；与064/065记录一致，本次未改依赖。
- validate_lifecycle_workspace.py：退出1，仍为7月验证资料及standalone/json-task-viewer的9条missing-workpackage-reference；无本功能新增目录违规。
- 原规划为7项任务；本轮修订为10项，覆盖10项FR、7项SC、三故事验收和D1—D12，无待澄清关键语义。最新检查结果在下方记录。
- 已只读调用真实生成API核对基线：25段、100任务、75关系，第1段四层均1790m/800m每天=3天，关系FS+0/7/7。只写规划文档，尚未修改业务代码、运行实施测试或更新客户配置。

本轮修订完成检查（2026-09-24）：

- validate_docs.py退出0：documentation links and API facts: OK (14 documents)。
- 定向检查退出0：7份成果的本地链接有效，T001—T010唯一且连续；10项FR、7项SC、D1—D12均映射到任务，任务源码路径全部在plan范围内。
- 人工一致性核对：三故事验收均有实施/验证任务；US1三项、US2两项、US3三项、共享验证两项，按依赖串行实施；移除了末层约束不变等旧口径，无新增覆盖缺口。
- 本轮只修订本目录七份文档及规格索引；未运行实施测试、修改源码、重启服务或改客户配置。仓库级既有依赖/生命周期问题未涉及，沿用上方记录，不重复运行无关验证。
