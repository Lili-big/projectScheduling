# 路面接口与页面契约

## 兼容原则

以下为实施目标。沿用已有接口，新增参数均在显式 pavement 领域使用。旧请求缺省 bridge，已有响应字段、错误 detail 及状态码维持。字段定义见 [data-model.md](../data-model.md)。服务端不能只依赖前端隐藏按钮隔离不支持行为。

## HTTP 接口

工序关系增量：既有场景配置/生成/求解请求中的`pavement_settings`增加`dependency_rules`（字段见data-model）。无新路由，保存/读取仍为现有配置接口；格式非法422，业务诊断复用`PAVEMENT_REFERENCE_INVALID`、`PAVEMENT_DATA_INCOMPLETE`、`PAVEMENT_LOGIC_CYCLE`，未匹配但节点存在为warning `PAVEMENT_RELATION_UNUSED`。任务响应的PrecedenceLink沿用已有relationship/lag_days。演示镜像已有路面422拒绝分支继续适用，不扩展镜像求解能力。

| 接口 | 路面扩展 | 成功与失败 |
| --- | --- | --- |
| GET /api/project-master/template | 可选 engineering_domain=pavement，生成 1.2 路面填写示例/字段说明 | 200 XLSX；未知领域 422；无参数维持原接口 |
| POST /api/projects/{project_id}/project-master/imports | 沿用 multipart file/created_by/expected_current_version_id；支持新增类型及参数 | 沿用 ready=201、其他已创建批次=202；缺文件/格式请求错误422，大小413，版本冲突409；对象校验错误放入批次 issues |
| GET /api/project-master/imports/{batch_id} | 预览路面对象、数量和来源问题 | 200；未知批次404 |
| POST /api/project-master/versions/{version_id}/confirm | 保持版本确认；几何/排程参数未齐时通过问题分层阻止求解，不静默替值 | 200；冲突409；对象身份非法按既有阻断语义 |
| GET /api/demo-scenario | 可选 engineering_domain、project_id；pavement 返回空主数据的路面配置，不自动导入客户样例 | 200；配置损坏503；无参数保持桥梁默认 |
| GET /api/process-library | 可选 engineering_domain、project_id，pavement 只返回三类核心工艺 | 200；未知领域422 |
| PUT /api/process-library | 请求新增可选 engineering_domain、project_id；路面保存对应配置区 | 200；工效或单位非法422，写入失败503 |
| PUT /api/local-scenario-config | 请求新增领域/项目、task_overrides、pavement_settings、project_data_version_id、可选 project_start_date；路面保存独立项目区 | 200；结构错误422，失效主数据引用409，写入失败503 |
| POST /api/generate-schedule-input | ScenarioInput 新增显式领域及设置；返回任务、关系、候选资源、最早开始与 readiness | 200 GeneratedScheduleInput（业务缺项放 validation，禁止继续求解）；非法数据类型422，版本不存在404/未确认409 |
| POST /api/solve-scenario | 显式 pavement 进入固定机组路面求解；支持既有 workpoint_id 单工点选择 | 200 ScenarioSolveResult；无解/超时保留业务状态；非法策略422；版本错误按现有语义 |
| POST /api/solve | ScheduleInput 显式领域决定求解；不能绕过路面资源和 readiness 校验 | 200 ScheduleResult；结构校验422 |
| POST /api/solve-min-resources、/api/solve-resource-cost | 首版 pavement 不适用 | 422，detail.code=PAVEMENT_STRATEGY_NOT_SUPPORTED；bridge 不变 |
| 现有 AI 参数/资源助手与桥梁专项入口 | pavement 输入不调用桥梁工艺、推荐或生成链路 | 场景包含领域时422 PAVEMENT_FEATURE_NOT_SUPPORTED；不带 Scenario 的入口按关联主数据支持标识拒绝，不修改桥梁合法输入行为 |

项目主数据查询、导出继续沿用现有接口；没有当前确认版本时404供前端展示待导入，不创建虚假默认主数据。

既有比较接口如接受带 pavement_summary 的已求解结果，只比较同领域/同范围的有效结果与日期；任何会触发高级重新求解的入口首版不开放。未部署的演示镜像应明确拒绝 pavement 场景，不能以桥梁默认结果响应。

## 诊断字段与分类

沿用 ValidationMessage 的 level/code/subject_id/entity_refs/message/suggestion/details。新路面 code 必须覆盖：

- PAVEMENT_DATA_INCOMPLETE：所选段/层缺字段；
- PAVEMENT_QUANTITY_BASIS_UNCONFIRMED：净量依据未确认或冲突；
- PAVEMENT_UNIT_MISMATCH：工程量与工效单位不一致；
- PAVEMENT_LOGIC_CYCLE / PAVEMENT_REFERENCE_INVALID：循环或失效引用；
- PAVEMENT_RESOURCE_MISSING：启用层没有适用机组；
- PAVEMENT_TRANSFER_UNCONFIRMED：路面转场参数未确认；
- PAVEMENT_SCOPE_NOT_SUPPORTED：选中非路面对象或混合未支持范围；
- PAVEMENT_STRATEGY_NOT_SUPPORTED / PAVEMENT_FEATURE_NOT_SUPPORTED：明确不适用。

结构校验使用422，资源容量不足形成求解诊断，无解不冒充服务器故障。HTTP失败不清空历史成功结果；结果标记与当前输入匹配情况。

## 页面契约

| 页面 | 可观察行为 |
| --- | --- |
| 主数据 | 查看路段、幅、层、几何/净量、移交及来源；空态引导下载模板，冲突行可定位；新版本确认后关联场景失效 |
| 工艺工效 | 三类工艺与每套机组单位；支持层级选用工效方案，展示施工天数计算依据；零/负工效拦截 |
| 工艺逻辑 | 展示结构层链及配套工作、等待和可用日期；将固定顺序与显示排序区分；真实项目缺参数时提示待完善 |
| 关键机组 | 三类独立机组数量、适用范围与转场天数；数量可0但不能得到缺资源的有效计划；不显示无关钻机/模板规则 |
| 任务 | 按段/幅/层组织，配套作业标记资源未约束；不把道路任务显示成墩台构件 |
| 结果 | 施工、养生等待、转场可区分；施工末日与后续可用日期区分；机组路线、来源、可行/最优/失败状态可查 |
| 导航与保存 | pavement 下默认主流程，隐藏不适用模块和无可用功能的分组（含折叠导航状态）；保存后重新打开恢复本项目路面配置；bridge 历史场景不受覆盖 |

不要求新增地图或复杂可视化，复用现有任务表、甘特及资源结果，只增加理解新语义所需字段和区间。

## 自动契约验收

- 旧 bridge payload 往返与已有响应保持兼容；新增字段缺省不改变原稳定指纹。
- 新字段从页面→请求→存储→读取→生成→求解→展示完整往返。
- 在路面输入缺少必要值时，通过直接 HTTP 调用也不能绕过校验。
- Excel 1.0/1.1 与 1.2 可分别读取；同 ID/同输入导入保留原版本一致性语义。
- 更新架构基线前对比并解释全部本次字段差异；不吞并已知 requirements 哈希问题或无关路由差异。
