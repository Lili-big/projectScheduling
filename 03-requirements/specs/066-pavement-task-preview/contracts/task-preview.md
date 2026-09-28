# 任务自动准备合同

## 现有API

POST /api/generate-schedule-input，body为当前完整ScenarioInput，任务页不传workpoint_id以覆盖整个项目。project_data_version_id仍须属于当前项目且已确认；工效、依赖及其他配置来自当前内存场景。

响应沿用GeneratedScheduleInput：schedule_input.tasks提供分解、工程量和duration_days；precedence_links提供关系；validation提供缺项；solve_scope为ALL。不新增字段、端点、状态码或数据库。

业务validation为error时仍可展示其中有效的计算结果，不等于求解可行。HTTP 409/422/503或网络失败按现有错误含义展示，可重试；保留当前主数据骨架，旧数值不可冒充当前。预览不调用/api/solve或/api/solve-scenario，也不调用保存API。

## 页面合同

| 字段 | 展示来源/行为 |
| --- | --- |
| 施工段 | 主数据段分组，可折叠；当前默认25组 |
| 工序 | 启用结构层或正天数配套步骤；缺项行仍保留 |
| 计量工程量 | Task.quantity及properties.unit；当前按施工长度m，不取材料吨数 |
| 工效方案 | 对应实际工艺的选项，可选择覆盖；失效项不静默替换 |
| 工效 | Task.properties中的实际值与单位，按每套机组 |
| 工期（天） | Task.duration_days；缺失则待完善，不加养生/转场，不除以机组数量 |
| 前置工序 | 层内名称；跨段引用带施工段名称，允许多条 |
| 逻辑关系 | FS/SS/FF/SF + N天；N未确认时显示待确认；来源区分统一/分段等 |

首次进页自动加载。当前输入变化自动更新；250ms作为防抖实现建议，不是业务等待时间。进入别的页签不强制跳回任务页。使用最新请求与输入指纹双重核对，禁止慢的旧响应覆盖新结果。失败只有显式重试或新输入触发新请求。

本页保存工效选择使用现有PUT /api/local-scenario-config及原dirty/error处理；保存中避免重复提交，失败不丢编辑。统一关系在工艺逻辑页维护，此表只读表达。

## 算法及边界

工期仍由现有后端规则计算。当前计量方式：duration=max(1,ceil(quantity/productivity))；单位必须相配且值有效。例如1790m÷800m/天为3天，改1000m/天为2天。关系中的7天技术间歇单独约束，不并入施工工期。

正天数配套使用既有固定工期；零天配套仅作为条件。路线、同机互斥、转场、路床约束不变；末层不再追加养生/验收等待，求解目标取最早施工完成。未知间歇、无效工效、失效/循环关系不作为0天或有效边自动修复。生成器因缺项跳过层时，页面保留该层并核对已知层序，不能显示伪造跳层关系。

空项目或无启用层显示配置主数据入口/提示，不自动补层。路床待完善不阻止查看已知任务；064三态规则仍待独立实施。桥梁、演示镜像及持久历史保持原行为；路面求解语义按以下合同调整，不新增端点。

## 统一工序链

工艺逻辑页只在关系行编辑层间类型与N，保留统一/分段范围。分段规则优先于统一规则，再回退旧非末层养生条件；显式null是待确认，不回退旧值。历史等待在链中显示并可通过编辑关系接管，不自动迁移或删除原条件。显式FS+N仅使用N一次，非FS沿用本身逻辑，不另叠FS等待。

删除下方施工段养生表及批量填写入口，删除末层养生输入和引导。已有非末层验收日期仍约束下道工序，在相应分段关系行的可选条件内维护，更新日期保留原wait_days/basis_note；不新增必填日期。配套步骤和指定跨段施工顺序留在默认收起的其他配置中。

## 末尾场景排除与接口兼容

本轮新生成输入的readiness_conditions为空；按主数据启用层序识别末层，其旧wait_days/accepted_available_date不参与生成，末层缺少wait_basis不报错。历史配置继续存储，不因预览或生成被清理。单层施工段也不要求养生条件；跨段明确配置的前置边仍执行。

直接/api/solve对携带旧readiness_conditions或非零末层等待/验收边界的输入沿用HTTP 422校验响应，明确提示“请按当前工序链重新生成任务”；底层求解函数返回MODEL_INVALID。新生成的输入与/api/solve-scenario一致。拒绝旧口径有诊断，不静默丢弃直接请求的限制。

结果不生成末层readiness或等待区间。最小化max(task.end)，objective_breakdown.objective=earliest_construction_finish；objective_days是该边界的天数，plan_finish_date采用construction_finish_date=start_date+max(end)-1。既有ready_offset/date保持原边界含义作为兼容字段，本轮页面不以它们表示可交付日期。末层完成里程碑以任务finish_date为准；非末层日期限制不变。旧目标/含readiness的结果保留历史并提示重新求解，不改写历史。
