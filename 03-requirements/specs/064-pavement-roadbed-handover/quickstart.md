# 验证指南

状态：已实施。下方样例为验收规则，实际执行结果见文末“实施证据”；客户求解时限内未找到可行计划，不宣称全项目排程已完成。

## 前提与最小测试批次

仓库根目录执行，使用现有.venv和npm依赖；后台操作严格沿用`04-demo/runtime/README.md`，不另起重复服务。

```powershell
.venv/Scripts/python.exe -m pytest 04-demo/backend/tests/test_pavement_master.py 04-demo/backend/tests/test_pavement_api.py 04-demo/backend/tests/test_pavement_generation.py 04-demo/backend/tests/test_pavement_solver.py 04-demo/backend/tests/test_pavement_contracts.py -q
node --test 04-demo/frontend/tests/pavementMaster.test.mjs 04-demo/frontend/tests/pavementWorkflow.test.mjs 04-demo/frontend/tests/pavementResults.test.mjs 04-demo/frontend/tests/contractsCompatibility.test.mjs
npm.cmd run build
```

测试使用独立临时数据库及样例配置，不自动改变客户资源和养生数据。上述相关批次通过后不重复跑全仓测试；新失败只追加相关修复验证。共享架构检查按现有脚本核对仅本次字段差异。

## 日期与范围样例

计划开始2026-09-23；四个段均有合法长度、四层、明确工效/养生/转场和可用机组：

| 段 | 路床条件 | 期望 |
| --- | --- | --- |
| A | dated，2026-10-25 | 全部核心及配套任务起点偏移≥32 |
| B | handed_over，无日期 | 起点偏移≥0，不提示缺路床日期 |
| C | pending，征地未解决 | 所有层与配套均未排程，无资源占用，清单保留原因 |
| D | dated，2026-09-10 | 不能早于计划开始日，起点偏移≥0 |

将计划开始改为2026-10-01：A下限24，B/D下限0；B的实际移交日期仍为空。给A配置SS/SF以及前置配套，均不得越过路床边界。工序与资源约束仍可把实际开始推迟。

## 必测边界

- 三态保存、刷新、Excel往返；无状态的旧有效日期兼容；无状态无日期保守待定；非法状态/日期及dated缺日期拒绝。
- 单段状态改变使任务/结果失效；陈旧版本保存409，草稿和原数据保留。
- pending不通过停用/删除层实现；再改为dated或handed_over后原有层、工效匹配、关系设置恢复使用。
- 全待定、全部停用、无主数据分别有清楚空态；全待定不调用CP-SAT。
- 直接求解pending任务拒绝；剥除客户端日期约束也不能让dated任务提前；同段任务状态矛盾拒绝。
- 固定顺序包含待定段时，只约束纳入任务的相对顺序；合法待定对象的配置不误判为失效引用。
- 已移交但其他资源/养生缺项仍报原错误；不靠自动填值完成演示。

## 当前客户数据验证

先导出当前确认版本和保存配置引用，再按用户明确映射导入一个新版本。期望25段/100层、18 dated/3 handed_over/4 pending，路床资格范围为21段84核心层与4段16层待定；原表长度、桩号、宽度9.2m及层厚密度全部保持。

逐项对比新旧快照业务字段，确认只有移交状态/说明和新版本来源元数据变化。检查工效、机组、关系、计划开始日未被覆盖。若本地数据在实施前变化，先核对真实新基线，不直接按旧行号覆盖。

在8000页面刷新查看三态，任务及结果查看未排程清单。实际客户其他必需参数缺失时，只报告已完成三态接入，不宣称客户全量计划可执行。

## 实施证据记录位置

相关命令退出结果、当前版本ID、迁移比较结果、浏览器可见结果及非本次问题记录在文末。

## 2026-09-24 规划产物检查

- `validate_docs.py`：退出0，文档链接及API事实检查通过。
- `validate_repository.py`：退出1，现有`requirements.txt changed without architecture dependency approval`问题；本批未改依赖文件。
- `validate_lifecycle_workspace.py`：退出1，仍为原有9处工作包引用缺失，位于2026年7月验证汇报和独立JSON查看器资产，不涉及064目录。
- tasks.md已做一次FR/SC/用户故事/设计决策覆盖检查，共10项，无覆盖缺口。本批仅完成文档与索引，尚未执行功能测试、客户状态迁移或上线。


## 2026-09-24 实施证据

### 实施与验收

- 已完成T001～T010。实现单段三态保存、Excel往返、权威段级投影、待定范围排除、全待定空态、直接求解日期硬边界以及任务/结果范围说明。
- `StructureModel.properties`为空时省略，用于保留没有结构层的段级状态；旧桥梁输入输出仍不增加路面字段。旧无状态有日期按dated读取，无状态无日期按pending读取，不扫描备注猜测。
- 主数据保存复用新版本及409保护；失败保留编辑草稿。待定段的结构层、工效选择和关系配置保留，恢复移交资格后重新使用。
- 受阻任务不生成日期、不分配资源；SS/SF与前置配套均受路床开工下限约束。全待定不调用求解器；全停用、空主数据保留独立空态。

### 测试和构建

- 首先添加三态/范围测试，观察到缺少三态解析、待定段仍产生任务/缺日期错误，随后实施。
- quickstart所列后端五文件批次首次执行为64通过、3失败：三个旧样例分别只给同段某层改移交日、只删某层移交日、手造配套任务未携带路床条件，均与新段级一致性规则冲突。按新契约修正样例后，针对这3例执行，3通过（退出0）。
- 新增真实主数据API混合范围样例，验证段级状态不能被组件或客户端覆盖、待定缺执行参数不阻断、其他段缺机组仍报错、直接求解拒绝pending：1通过（退出0）。后端本次覆盖共68个不同用例，全部通过。
- 全待定用例补充全停用/空主数据区别后，针对该例执行，1通过（退出0）。未重复整套测试。
- quickstart前端四文件批次：28通过（退出0）。补充受阻任务过滤和兼容断言后，task-preview与contracts两个文件14通过（其中9例已在前批）；移交保存失败草稿保留用例1通过。前端本次共34个不同用例通过。
- `npm.cmd run build`：退出0，TypeScript及Vite构建成功；仅保留已有单包超过500kB的体积警告。
- Demo API镜像仍显式拒绝路面，由既有API测试覆盖。

### 当前项目升级与回读

- 原版本：V25 / `pmv-50a66eec36624a459aaf2ead8fb91142`。
- 新版本：V26 / `pmv-975eba0fd297417586cb4798f74efd6c`。
- 通过既有Excel导入预览和版本确认接口升级，使用expected_current_version_id；未直写SQLite或改写历史快照。
- 25段、100层、总长37,435m、全部宽9.2m保持；逐项比较保留原桩号、长度、厚度、密度、层启用、备注、ID及顺序。只增加移交状态和说明（导入来源元数据随新版本更新）。
- 状态为18 dated、3 handed_over、4 pending。HTTP生成回读为21段84个核心任务纳入、4段16层受阻，生成诊断无error。
- 配置文件逐字段比较：仅pavement-project的project_data_version_id改变；工效、资源、关系、计划开始日期2026-09-23不变。旧快照与迁移前完全一致，导出Excel再读指纹匹配。
- 本地备份、映射及验证记录：`.local-data/tmp/pavement-section-update-20260924/handover-064-20260924-193432/`中的before.json、before.xlsx、config-before.json、mapping.json、import.json、after.xlsx、generated.json、evidence.json。一次性迁移脚本位于同父目录apply_handover_064.py，重复运行会因显式状态已存在而停止。

### 浏览器与实际求解

- 按runtime README重启已核实的8000后端，日志目录为`.local-data/logs/20260924-193311-178/`。
- 8000页面刷新后显示25段及可编辑的路床状态；第7/10/19段为已移交，4个受阻段显示征地、隆安地界及管线迁改原因。
- 任务视图显示“21段·84道工序”和“本次纳入21段/84个结构层·受阻4段”，第一段1790m/800m每天=3天，原FS+0/7/7关系保留。
- 浏览器按原配置实际求解：已通过路床数据校验，返回UNKNOWN，页面继续展示21/84纳入范围和4个受阻原因。现有15秒内没有找到可行计划，不等于INFEASIBLE，也没有获得可报告的施工完成日期。保留原时限、共享机组数量和硬约束，本次未扩大为求解性能优化。

### 非本次阻塞与剩余风险

- 架构捕获命令退出0；后端fixture仅同步本次新增范围字段、StructureModel可选属性及handover路由，未吸收其他漂移。前端捕获器只比较类型导出名，当前差异为此前MinimumResourceVerification/UnifiedSolveMetadata，与本次无关，保留原fixture。
- 两个architecture `--check`均退出1。残余差异已逐项核对，均为此前的task-view-display-map接口、共享机组process_id/compatible_process_ids、apply_unified_target_achievement导出、依赖哈希以及上述前端两类导出；本次三态字段不存在遗漏。
- `validate_docs.py`退出0；`validate_repository.py`退出1，仍为requirements依赖审批问题；`validate_lifecycle_workspace.py`退出1，仍为原有9处7月汇报/独立JSON查看器引用缺失。本次未修改这些资产或依赖。
- 核心三态及排程范围验收已满足；客户84任务在原15秒内求解未获可行解，不能承诺当前配置的实际工期。正式上线前仍应处理仓库现有治理问题。
