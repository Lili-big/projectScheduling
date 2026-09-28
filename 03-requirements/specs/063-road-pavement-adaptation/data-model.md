# 数据模型与状态

本文件定义新增契约的约定，不表示字段已经实施。现有完整类型继续以源码为准。

## 工序关系增量（2026-09-23）

`PavementSettings.dependency_rules`默认空列表；每项为`structure_id`（null统一或实际段ID）、`predecessor_key`、`successor_key`（非空）、`relationship`（FS/SS/FF/SF）、`lag_days`（非负严格整数或null待确认）。同作用域、同前后槽位唯一；空列表保持旧输入行为。前端字段可省略以兼容旧本地配置；后端校验非法类型为422，引用/重复/未填写在生成任务时给出定位诊断。

层槽位为`layer:<component_type>:<同类序号>`，按全部实际层的sort_order排序编号（含停用层，防止停用后序号错位）；配套槽位为`<所属层槽位>/prep:<kind>:<同类序号>`，按order/id排序编号，0天步骤不成为任务节点。邻接边只包含启用层和正天数配套，N可包含中间0天配套等待。规则只作用于匹配的实际邻接边；引用已删除节点/段为error，节点仍在但停用或不邻接为warning，保留规则供用户调整。分段覆盖优先于统一。前端与后端共同使用该约定并用相同样例断言。

显式规则不会改写既有layer_conditions；生成结果按生效规则派生task.properties.wait_days（FS=N，其他类型=0）及wait_basis。未被覆盖的末层交付条件继续使用原养生/验收值。配置变动纳入现有fingerprint失效处理。统一规则和单段覆盖使用现有`save_pavement_profile`项目隔离存储。

## 1. 领域与主数据

2026-09-23：层级参数增加`density_t_m3`（正有限数，单位t/m³，未知缺省）；`PavementLayerEdit`增加可选`density_t_m3`，缺字段保持已有密度、null清空、非法值422。Excel组件列增加`param.density_t_m3`，旧段级列保留以读取历史输入但不用于新页面显示。派生吨位由净施工长度、段宽、本层厚度、本层密度计算，整数仅为显示格式。组件quantity/unit仍保留原排程长度m；新工程量显示不会把吨当作米输入工效库。密度变化参与既有快照指纹和版本保存，未启用沥青保留原停用状态。

按段编辑增量：`POST /api/project-master/versions/{version_id}/pavement-layers/initialize`（`created_by`），仅给当前版本的空路面段补5个默认组件并保存；`PUT /api/project-master/versions/{version_id}/pavement-sections/{section_id}/layers`（`created_by`，有序`layers`1～30项：`component_id`已有层ID或null，`name`，`process_type`，`thickness_m`正有限数或null，`enabled`）。都返回已保存的`ProjectMasterVersionDetail`，200成功（未变动返回当前版本），422非法值/跨段层标识/数量错误，409陈旧基线或引用冲突，404版本/施工段不存在。保存未填厚度是保存待完善主数据，不代表验收或可排程；完整性warning仍被任务生成提升为error。持久化继续使用本地SQLite；历史版本和未编辑段保留。不新增层厚/养生/资源假定。

结构层补齐接口：`POST /api/project-master/versions/{version_id}/pavement-layer-drafts`，输入 `section_ids`（唯一、非空、最多500）、`layers`（有序、1～30项，每项 `name`、`process_type` 三类之一、`thickness_m` 正有限数）、`created_by` 非空。输出复用 `ProjectMasterImportBatch`；200 返回新建或已存在的草稿，422 输入/数量无效，409 版本已变化或段已有层，404 基线不存在。新增层 ID 为段ID加 `-L01` 等顺序后缀；数量取确认净长，单位 m，参数含实际厚度与 entered 数量依据。新层来源为模板输入，原段/工点/线路落位及来源原样保留。确认/取消仍使用原接口；前端确认后重读版本，旧任务/结果依指纹失效，等待条件和资源不随模板自动填写。演示镜像对此接口返回既有不支持错误。

| 对象 | 新增/扩展字段 | 校验和兼容 |
| --- | --- | --- |
| ScenarioInput、ScheduleInput | engineering_domain: bridge/pavement；缺省 bridge | 旧领域缺省字段不进入旧 dump；不根据名称推断 |
| ProjectMasterWorkpoint | workpoint_type 增 pavement，schedule_support 增 pavement_supported | 保留所有旧类型；一个工点可包含多个施工段 |
| ProjectMasterStructure | structure_type=pavement_section，structure_category=pavement；side 使用现有 left/right/none | 同工点不同段/幅身份独立；有左右幅数据不得用 none 合并 |
| ProjectMasterComponent | granular_base / cement_stabilized_base / asphalt_course | component_id 表示实际层，sort_order 决定显示层序；实际施工先后需生成显式关系 |

施工段参数复用 ParameterValue：`start_chainage`、`end_chainage`（原始文本）、`construction_length_m`、`width_m`、`roadbed_available_date`（ISO 日期）、`quantity_basis_confirmed`（boolean）、`quantity_basis_note`。线路前缀与标准数值里程可同时保留，不能用其差值覆盖确认净长度。

用户于2026-09-22确认段级统计字段：`water_stable_thickness_m`（number，m）和 `water_stable_density_t_m3`（number，t/m3）；本机15段初始化为0.76与2.38，并形成V4。水稳工程量是页面派生值：construction_length_m × width_m × water_stable_thickness_m × water_stable_density_t_m3，单位t，显示两位小数，不另存重复数量。旧版本缺参保持空值；Excel模板、导出和再次导入保留这两个参数。该段级字段与实际分层的 `thickness_m` 相互独立。

结构层参数：`thickness_m`、`quantity_basis`（entered/geometric）、`quantity_basis_note`；quantity/unit 沿用既有构件字段，单位标准化为 m/m2/m3/t。cm 输入在预览中显示换算，保存后统一 m。

任务数量规则：长度→m；长度×宽度→m2；长度×宽度×厚度→m3。任务的t数量仍接受明确输入；主数据页面段级水稳吨位依上述确认公式统计，不自动写入任务。人工数量与几何量差异必须展示、说明并确认；缺失所选单位的必要尺寸时不能猜测。

稳定 ID 由用户主数据或原导入机制提供，不随名称、排序号、工效变化。层序或路段变更仍复用现有 diff/版本机制；不原地覆盖已确认历史。

## 2. 工艺与资源

ProcessTemplate、ProductivityOption 保持原结构；三类核心 process 的 component_type 对应上述三类层，quantity_source 使用确认 quantity，units_per_day 表示每套机组的综合工效。已有 TaskOverride.productivity_option_id 用于层级选择。

ResourcePool / Resource 新增可选 `transfer_days`（整数>=0；旧桥梁缺省不改变原语义）。路面三类 type 为 `granular_paving_crew`、`water_stable_paving_crew`、`asphalt_paving_crew`；不互为候选。正式可求解路面场景必须显式确认转场数值，不能依赖桥梁兼容缺省值。

quantity 是可用机组套数，可为 0 以准确表达现场状态；启用任务无可用候选时返回资源缺失。首版路面关键池必须 LIMITED。授权工点范围复用既有字段，层的作业位置由 pavement_section 稳定 ID 和幅别构成，不只看工点 ID。

## 3. PavementSettings

作为 ScenarioInput 的可选 typed 字段，类型定义进入 `contracts/pavement.py`，前端镜像进入 `contracts/pavement.ts`。

- `layer_conditions[]`：component_id、wait_days（非负整数）、accepted_available_date（可空，表示没有额外晚于最小等待的计划日期条件）、basis_note（来源/人工确认说明）。待确认项目值不可以空值自动转零。
- `ancillary_steps[]`：id、structure_id、before_component_id、kind（prime/seal/tack/other_preparation）、name、duration_days（整数>=0）、wait_after_days（整数>=0）、available_date（可空）、order、basis_note。
- `fixed_sequences[]`：process_type、component_ids（无重复有序列表）。只有用户明确指定“固定施工顺序”才使用，主数据 sort_order 不自动复制过来。
- `input_kind`：customer/demo，demo 在界面和结果明确标识。

每个启用结构层有显式条件记录，包括碎石或沥青的零等待确认。accepted_available_date 只是计划输入，不是现场验收合格证；用户确认输入后其含义为“预计/已知最早具备条件日”。

同一个 before_component_id 的配套步骤按 order 链接；上层固有前置条件必须满足后才能开始其最早配套步骤。如未来要表达与水稳养生并行的特殊工法，需另行明确，首版不自动推断。

## 4. 生成任务与终端条件

StructureType 增 pavement_section；ComponentType 增三类核心层及 `pavement_preparation`，后者仅用于配套任务，不属于第四类核心工效。

Task 增可选 `pavement_context`：source_component_id（核心层为本层，配套为其关联层）、position_id、task_kind（construction/preparation）、process_type、quantity_basis、input_kind；零值默认不改变桥梁序列化。

核心施工任务使用原计算天数，机组候选按工艺匹配；正天数配套任务无主机组分配并标记辅助资源未约束；0 天步骤只转接关系和等待，不创建违反 Task 最少 1 天的对象。

ScheduleInput 增可选 `readiness_conditions[]`：id、terminal_task_id、source_component_id、wait_days、available_offset。每个启用施工段终端必须有一项；最后的零天配套条件继续传递到该事件，不丢失。

日期规则：施工 [s,e) 对应第 s+1 至 e 天；finish_date=P+e-1；ready_offset=max(e+wait_days, available_offset)，ready_date=P+ready_offset。wait=0 不增加项目耗时，ready_date 与施工末日可能相差一个日历日期，这是边界，不额外增加目标值。

最早开工继续使用 TaskExecutionConstraint；FS lag 和已确认顺序继续使用 PrecedenceLink。循环、自环、找不到层/任务、跨项目引用全部阻断求解。

## 5. 结果与状态

ScheduleResult 增可选 `pavement_summary`：

- input_kind、input_fingerprint、project_data_version_id；
- construction_finish_offset/date、ready_offset/date；
- `readiness[]`（按段/幅/末层）；
- `wait_intervals[]`（来源层、起止、原因，不占主资源）；
- `transfers[]`（resource_id、from_task_id、to_task_id、from_position_id、to_position_id、start_offset、end_offset）；
- resource_assumptions（配套班组/养生管理资源未约束）。

原 Task/ResourceAllocation 继续表达施工作业，转场不伪装成增加工程量的施工任务。所有新结果字段在桥梁结果中为空/省略，不改变桥梁原目标的日期口径。

UI 状态使用现有请求状态再映射为：待导入→待完善→可生成→已生成→求解中→结果；输入修改后结果过期。INFEASIBLE / UNKNOWN / MODEL_INVALID 按原状态码保留，并由 diagnostics 区分数据缺失、真实无解、限时或程序失败；不能只显示“延期”。

## 6. 持久化与失效

SQLite 继续存通用工点、结构、构件、参数，不引入平行表组；更新定义版本和类型字典时保留旧行，不重算旧版本稳定指纹。定义参数的实际持久化/导出要有回读测试。

本地配置 schema 升至 `local-scheduler-config/v5`，仍接受旧版；添加 `pavement_profiles[project_id]`，保存 process_library、task_overrides、resource_pools、pavement_settings、project_data_version_id 和 project_start_date，原桥梁顶层字段保留。project_start_date 为可选 ISO 日期，用于恢复用户编辑的计划开始日期；旧配置缺省保持原行为。路面加载只合并本领域确认配置，不补桥梁工艺。

输入指纹包含领域、主数据版本、层数量、工效选择、条件、配套步骤、固定顺序、机组范围/数量/转场；任何这些字段变化都使任务/结果/比较/下游引用失效。历史成果可查看但不可作为当前方案复用。
