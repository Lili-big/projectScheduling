# 数据模型：统一工点与结构物主数据

## 1. 领域边界与关系

```text
ProjectMasterVersion 1 ── * WorkPoint 1 ── * Structure 1 ── * Component
          │                     │               │                │
          │                     │               └── * StructureParameter
          │                     └── * SourceEvidence
          ├── 1 ImportBatch                         └── * ComponentParameter
          └── * VersionDiffEntry

ImportBatch 1 ── * ImportIssue
```

- `ProjectMasterVersion` 是不可变的项目主数据业务快照。
- `WorkPoint`、`Structure`、`Component` 只在所属版本内生效；跨版本以稳定业务 ID 对齐，不复用数据库行。
- 桥梁、路基、隧道等物理对象均只维护一个 `WorkPoint`；左右幅是 `Structure.side`，不是第二个工点。
- 当前排程只消费确认版本中的桥梁工点；其他工点按同一模型持久化和查询。

## 2. 表与实体

### 2.1 `project_master_versions`

| 字段 | 类型 | 约束/含义 |
|---|---|---|
| `version_id` | TEXT | PK，UUID/ULID；内部版本标识 |
| `project_id` | TEXT | 必填，项目稳定标识 |
| `version_no` | INTEGER | 必填，同项目递增且唯一 |
| `status` | TEXT | `draft`、`confirmed`、`superseded` |
| `content_fingerprint` | TEXT | 必填，规范化完整业务内容 SHA-256；同项目唯一 |
| `source_batch_id` | TEXT | 必填，FK → `import_batches.batch_id`，唯一 |
| `base_version_id` | TEXT | 可空，差异对比时的确认版本 |
| `summary_json` | TEXT | 仅保存数量、告警数等派生摘要；不保存业务对象 |
| `created_at` | TEXT | UTC ISO-8601 |
| `created_by` | TEXT | 必填 |
| `confirmed_at` | TEXT | 可空，仅确认后有值 |
| `confirmed_by` | TEXT | 可空 |

约束：

- `(project_id, version_no)` 唯一。
- `(project_id, content_fingerprint)` 唯一，保证相同内容不生成重复业务版本。
- 每个项目至多一个 `status = 'confirmed'`，通过 SQLite 部分唯一索引保证。
- `confirmed` 和 `superseded` 版本不得执行对象更新或删除；仓储层只提供整版本读取。

### 2.2 `workpoints`

| 字段 | 类型 | 约束/含义 |
|---|---|---|
| `version_id` | TEXT | PK(1)，FK → 版本，级联删除仅用于未确认草稿清理 |
| `workpoint_id` | TEXT | PK(2)，项目内稳定业务 ID |
| `workpoint_name` | TEXT | 必填 |
| `workpoint_type` | TEXT | `bridge`、`roadbed`、`tunnel`、`culvert`、`interchange`、`service_area`、`station_yard`、`access_road`、`other` |
| `alignment_code` | TEXT | 可空，线路/线别编码 |
| `start_mileage_m` | REAL | 可空，统一以米存储 |
| `end_mileage_m` | REAL | 可空，统一以米存储 |
| `sort_order` | INTEGER | 必填，非负 |
| `schedule_support` | TEXT | 派生/落库枚举：`bridge_supported`、`not_supported` |
| `remark` | TEXT | 可空 |

约束：同一版本内 `workpoint_id` 唯一；起终里程同时存在时 `end_mileage_m >= start_mileage_m`。`workpoint_name`、里程和排序不参与对象身份判断。

### 2.3 `structures`

| 字段 | 类型 | 约束/含义 |
|---|---|---|
| `version_id` | TEXT | PK(1) |
| `structure_id` | TEXT | PK(2)，项目内稳定业务 ID |
| `workpoint_id` | TEXT | FK → 同版本 `workpoints` |
| `structure_name` | TEXT | 必填 |
| `structure_category` | TEXT | 通用枚举：`substructure`、`superstructure`、`earthwork`、`tunnel_body`、`drainage`、`ancillary`、`other` |
| `structure_type` | TEXT | 结构类型代码；由定义目录校验，如 `bridge_pier`、`simple_span`、`continuous_unit` |
| `side` | TEXT | `left`、`right`、`shared`、`none` |
| `section_code` | TEXT | 可空，桥梁排程工区稳定编码 |
| `section_name` | TEXT | 可空，展示名称 |
| `control_level` | TEXT | 可空，受控层级或重要性 |
| `sort_order` | INTEGER | 必填，非负 |
| `remark` | TEXT | 可空 |

约束：父工点必须存在于同一版本；同一版本内 `structure_id` 唯一。桥梁中要求区分幅别的结构类型只允许 `left` 或 `right`；共用桥台、共用基础等明确共用对象允许 `shared`；`none` 只用于幅别不适用的非桥结构。

### 2.4 `structure_parameters`

| 字段 | 类型 | 约束/含义 |
|---|---|---|
| `version_id` | TEXT | PK(1) |
| `structure_id` | TEXT | PK(2)，FK → 同版本结构物 |
| `parameter_code` | TEXT | PK(3)，由参数定义目录校验 |
| `value_type` | TEXT | `text`、`number`、`integer`、`boolean`、`date` |
| `text_value` | TEXT | 与类型互斥 |
| `number_value` | REAL | 与类型互斥 |
| `boolean_value` | INTEGER | `0/1`，与类型互斥 |
| `unit` | TEXT | 可空，按参数定义校验 |
| `sort_order` | INTEGER | 参数展示顺序 |

用途：保存跨径、支座范围、联跨表达式、主墩、节段数量等结构类型特有参数。不得把这些值整体塞入一个 JSON 单元格；仓储中也保持逐参数可查询。

### 2.5 `components`

| 字段 | 类型 | 约束/含义 |
|---|---|---|
| `version_id` | TEXT | PK(1) |
| `component_id` | TEXT | PK(2)，项目内稳定业务 ID |
| `structure_id` | TEXT | FK → 同版本 `structures` |
| `component_name` | TEXT | 必填 |
| `component_type` | TEXT | 构件类型代码，如桩基、承台、墩柱、盖梁、梁片、节段 |
| `quantity` | REAL | 必填，`>= 0` |
| `unit` | TEXT | 必填，由构件定义校验 |
| `enabled` | INTEGER | `0/1`，是否参与任务生成 |
| `sort_order` | INTEGER | 必填，非负 |
| `remark` | TEXT | 可空 |

约束：父结构物必须存在于同一版本；同一版本内 `component_id` 唯一。工程量为零允许保存，但需按参数定义决定是否产生告警或跳过任务。

### 2.6 `component_parameters`

字段与 `structure_parameters` 相同，主键改为 `(version_id, component_id, parameter_code)`，用于直径、长度、混凝土方量、梁型等构件特有参数。

### 2.7 定义目录

| 表 | 作用 | 关键字段 |
|---|---|---|
| `workpoint_type_definitions` | 工点类型全集与排程支持状态 | `type_code`、`display_name`、`schedule_support`、`active` |
| `structure_type_definitions` | 结构类型、所属类别、适用工点和幅别规则 | `type_code`、`category`、`allowed_workpoint_types`、`side_rule` |
| `component_type_definitions` | 构件类型与合法单位 | `type_code`、`allowed_structure_types`、`allowed_units` |
| `parameter_definitions` | 参数类型、单位、必填性和适用对象 | `owner_kind`、`owner_type`、`parameter_code`、`value_type`、`unit`、`required` |

定义目录由代码内种子数据初始化并带 `definition_version`。历史主数据版本记录使用当时的代码值，即使某类型后续停用也必须可读；`active = 0` 仅禁止新导入。

### 2.8 `import_batches`

| 字段 | 类型 | 约束/含义 |
|---|---|---|
| `batch_id` | TEXT | PK |
| `project_id` | TEXT | 必填 |
| `status` | TEXT | `uploaded`、`validating`、`blocked`、`ready`、`confirmed`、`cancelled`、`failed`、`unchanged` |
| `file_name` | TEXT | 原始文件名 |
| `file_sha256` | TEXT | 原始文件身份；不作为业务幂等唯一依据 |
| `content_fingerprint` | TEXT | 校验成功后生成的规范化业务指纹 |
| `expected_current_version_id` | TEXT | 上传时看到的当前版本，用于乐观并发 |
| `created_version_id` | TEXT | 可空，FK → 版本且 `ON DELETE SET NULL`；`ready/confirmed` 批次关联所创建版本 |
| `existing_version_id` | TEXT | 可空；只有 `unchanged` 批次引用已有相同业务版本 |
| `cancelled_version_id` | TEXT | 可空；取消 `ready` 批次时保存被清理草稿的原版本 ID，仅用于审计，不设外键 |
| `created_at` / `created_by` | TEXT | 审计字段 |
| `completed_at` | TEXT | 可空 |
| `cancelled_at` / `cancelled_by` | TEXT | 可空；取消已上传批次时填写 |
| `cancel_reason` | TEXT | 可空，取消说明 |
| `failure_message` | TEXT | 可空，系统级失败摘要 |

阻断导入只保存批次、问题、来源和必要的规范化暂存摘要，不创建无效 `ProjectMasterVersion`。

### 2.9 `import_issues`

| 字段 | 类型 | 约束/含义 |
|---|---|---|
| `issue_id` | TEXT | PK |
| `batch_id` | TEXT | FK → 导入批次 |
| `severity` | TEXT | `error`、`warning` |
| `issue_code` | TEXT | 稳定错误代码 |
| `sheet_name` | TEXT | 工作表名称 |
| `row_no` | INTEGER | 可空；文件级问题无行号 |
| `field_name` | TEXT | 可空 |
| `object_kind` / `object_id` | TEXT | 可空，能识别对象时填写 |
| `message` | TEXT | 用户可读说明 |
| `suggestion` | TEXT | 可空，修正建议 |

### 2.10 `source_evidence`

每个工点、结构物、构件及参数均可关联来源位置：`version_id`、`object_kind`、`object_id`、`parameter_code`、`batch_id`、`sheet_name`、`row_no`、`column_name`。它满足不打开 Excel 即可追溯来源的要求，不保存原始业务快照副本。

### 2.11 `version_diff_entries`

| 字段 | 含义 |
|---|---|
| `diff_id` | PK |
| `version_id` | 草稿版本 |
| `base_version_id` | 对比的确认版本，可空（首次导入） |
| `object_kind` | `workpoint`、`structure`、`component`、`parameter` |
| `object_id` | 稳定业务 ID |
| `change_type` | `added`、`modified`、`deleted`、`unchanged` |
| `field_name` | 字段级差异；对象级新增/删除可空 |
| `before_value` / `after_value` | 规范化展示值 |
| `blocking_reference` | 是否因计划/实绩引用阻断确认 |

差异以稳定 ID 对齐，按规范化值比较。删除父对象时仍逐级生成可汇总的删除差异，便于页面显示影响数量。

## 3. 状态转换

### 3.1 导入批次

```text
uploaded → validating → blocked
                     ↘ ready → confirmed
                     ↘ unchanged
                     ↘ failed
blocked/ready → cancelled
```

- `blocked`：存在业务校验错误；当前确认版本保持不变，用户重新上传新批次修正。
- `failed`：文件损坏、数据库事务失败等系统级错误。
- `ready`：已事务性创建不可变 `draft` 版本，可查看差异和告警。
- `unchanged`：本次上传已保存独立批次，但通过 `existing_version_id` 引用已有相同业务版本，不创建新的 `ProjectMasterVersion`。
- `cancelled`：用户取消 `blocked/ready` 批次；批次、问题和取消审计保留。若原状态为 `ready`，在同一事务中把原 `created_version_id` 复制到 `cancelled_version_id`、删除未确认版本及其业务行并由外键把 `created_version_id` 置空，当前确认版本不变。
- `confirmed`：关联草稿已成功确认。

### 3.2 主数据版本

```text
draft → confirmed → superseded
```

- `draft → confirmed` 必须校验：批次无错误、告警已被确认、`expected_current_version_id` 仍匹配、删除不存在不可失效的实绩引用。
- 确认在一个数据库事务内完成：锁定项目版本序列、原确认版本转 `superseded`、草稿转 `confirmed`、记录确认人/时间、发出下游失效事件。
- 草稿取消可物理删除其业务行，但必须保留 `import_batches` 和审计记录；确认版本永不物理删除。

## 4. 旧版本数据结构映射

旧实现只提供语义和回归基准，不作为新仓储输入，也不执行数据迁移或双写。

| 旧模型语义 | 新模型归属 | 说明 |
|---|---|---|
| `ProjectModel.bridges[] / ProjectBridge` | `WorkPoint(workpoint_type=bridge)` | 一座桥一条工点记录 |
| `GirderWorkPoint` | `WorkPoint` 或由 `workpoint_id + side` 派生的路线节点 | 不再独立持久化第二份工点 |
| `WorkSection` | `Structure.section_code/section_name + side` | 排程适配时重新分组 |
| `StructureModel` | `Structure(category=substructure)` | 墩台等作为结构物 |
| `UpperStructureComponent` | `Structure(category=superstructure)` | 简支跨、现浇联、连续联统一为结构物类型 |
| `ComponentModel` | `Component + ComponentParameter` | 工程量/单位为核心列，类型特有属性逐参数保存 |
| `ProjectDataVersion` | `ProjectMasterVersion` | 沿用不可变版本语义，不沿用 JSON 快照存储 |

## 5. 排程投影

`ProjectMasterScheduleAdapter` 只接受 `confirmed` 版本：

1. 过滤 `workpoint_type = bridge`，按 `sort_order, workpoint_id` 生成 `ProjectBridge`。
2. 按 `section_code + side` 生成 `WorkSection`；缺少桥梁必填分组时返回明确诊断，不猜测工区。
3. 下部结构物生成 `StructureModel`，其构件生成 `ComponentModel`。
4. 简支跨、现浇梁联、连续梁/连续刚构联生成 `UpperStructureComponent`，保留跨径、支座范围、联跨表达式、主墩和节段参数。
5. `ScenarioInput` 和下游共享对象继续使用 `project_data_version_id` 指向确认版本，完整排程输入继续使用现有 `input_fingerprint`；不新增 `project_master_version_id/project_master_fingerprint`。非桥工点进入“当前不参与桥梁排程”诊断，不生成任务。
6. 任务、求解结果、方案比较和专项状态保存版本引用；确认新版本后，结构指纹变化的派生结果标为 `stale`，需重新生成或重新校验。

## 6. 索引、事务与恢复

- 索引：`workpoints(version_id, workpoint_type, sort_order)`、`structures(version_id, workpoint_id, side, sort_order)`、`components(version_id, structure_id, sort_order)`、`import_issues(batch_id, severity, sheet_name, row_no)`、`version_diff_entries(version_id, change_type, object_kind)`。
- 数据库连接启用 `PRAGMA foreign_keys = ON`、`journal_mode = WAL`、`busy_timeout`；schema 使用 `PRAGMA user_version` 升级。
- 解析可在事务外完成；创建草稿版本、关系数据、来源证据与差异必须在同一事务中提交。任何异常整体回滚，批次单独标记失败。
- 启动时只检查 schema 与仓储可用性，不扫描或导入旧 JSON。数据库不存在时创建空 schema，页面显示“尚未建立首个主数据版本”。
