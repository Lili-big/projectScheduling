# 数据模型：架构治理元数据

本功能不新增业务数据库表。以下实体用于设计迁移清单、验证记录、文档索引和兼容门禁，可实现为 Markdown/JSON 清单或测试夹具。

## 1. ModuleBoundary（模块边界）

| 字段 | 含义 |
| --- | --- |
| `module_id` | 稳定模块标识，例如 `backend.scheduling.solver` |
| `name` | 中文模块名称 |
| `layer` | `api`、`application`、`domain`、`infrastructure`、`ui-app`、`ui-feature`、`shared`、`tool` |
| `owner_scope` | 业务所有权，例如综合排程、架梁专项、计划管控、AI 助手 |
| `source_paths` | 当前文件或目录列表 |
| `target_paths` | 目标文件或目录列表 |
| `public_entrypoints` | 允许外部或跨模块调用的入口 |
| `allowed_dependencies` | 允许依赖的模块/层 |
| `forbidden_dependencies` | 禁止反向依赖或内部穿透 |
| `compatibility_facade` | 旧入口及保留策略 |
| `migration_batch` | 所属迁移批次 |
| `status` | `planned`、`facade_ready`、`migrating`、`verified`、`complete` |

### 校验规则

- 每个生产文件必须归属一个主要模块边界。
- 跨业务域调用只能指向 `public_entrypoints`。
- `domain` 不得依赖 API、UI、网络客户端或本地存储实现。
- `compatibility_facade` 在本功能内不得进入删除状态。

## 2. PublicContract（公开契约）

| 字段 | 含义 |
| --- | --- |
| `contract_id` | 稳定标识 |
| `kind` | `http`、`python_import`、`typescript_import`、`command`、`config`、`storage`、`static_hosting` |
| `consumer` | 当前调用方或维护对象 |
| `baseline` | 重构前方法、路径、字段、导出或行为摘要 |
| `comparison_rule` | 精确比较、schema 比较或业务不变量比较 |
| `allowed_change` | 本功能允许的变化；默认仅内部位置变化 |
| `evidence_path` | 快照、测试或验证记录路径 |
| `status` | `captured`、`preserved`、`regressed`、`approved_change` |

### 校验规则

- `regressed` 必须阻止迁移批次完成。
- `approved_change` 需要新的规格和用户确认；本功能默认不产生该状态。
- HTTP 合同比较必须包含方法、路径、状态码、错误 `detail` 和响应 schema。

## 3. BehaviorBaseline（行为基线）

| 字段 | 含义 |
| --- | --- |
| `baseline_id` | 固定场景或用户旅程标识 |
| `input_fixture` | 可复现输入或准备步骤 |
| `scope` | 排程、架梁、计划管控、AI 助手、前端失效、构建等 |
| `invariants` | 必须保持的任务日期、资源分配、状态、诊断或交互结果 |
| `ignored_metadata` | wall time、临时 ID 等不参与等价比较的字段 |
| `command` | 验证命令 |
| `baseline_result` | 重构前结果摘要或快照 |
| `latest_result` | 当前批次结果摘要 |
| `status` | `pending`、`pass`、`fail` |

### 校验规则

- 每个迁移批次至少关联一个行为基线。
- 涉及 `solver` 或 `scenario` 的批次必须比较业务不变量，不能只检查测试进程退出码。
- `fail` 必须回退或修复，不得以“仅重构”为由忽略。

## 4. RepositoryAsset（仓库资产）

| 字段 | 含义 |
| --- | --- |
| `asset_id` | 稳定资产标识 |
| `path` | 当前路径 |
| `asset_type` | `source`、`config`、`document`、`spec`、`example`、`tool`、`deliverable`、`generated_artifact`、`local_runtime`、`runtime_log` |
| `authority` | `canonical`、`reference`、`historical`、`temporary` |
| `tracked` | 是否应纳入版本控制 |
| `regenerable` | 是否可由仓库内流程重新生成 |
| `contains_secret` | 是否可能含凭据或个人信息 |
| `target_path` | 目标路径；不迁移时与当前相同 |
| `retention_rule` | 保留、归档、取消跟踪或忽略规则 |
| `references` | 指向该资产的仓库内引用 |
| `content_hash` | 正式二进制资产迁移前后的校验值 |
| `status` | `inventoried`、`approved`、`moved`、`verified`、`archived` |

### 校验规则

- `deliverable` 不得因可疑扩展名或位于 `outputs/` 被自动删除。
- `generated_artifact` 只有在显式 allowlist 中才可跟踪。
- `local_runtime` 和 `contains_secret=true` 不得进入版本控制。
- `runtime_log` 必须位于 `.local-data/logs/` 且不得进入版本控制；既有根日志只允许执行逐文件确认后的本地移动。
- 二进制正式交付物迁移后 `content_hash` 必须一致。
- `approved` 只表示用户已对逐文件清单完成二次明确确认；规划阶段的类别级同意不能代替该状态。

## 5. DocumentationEntry（文档条目）

| 字段 | 含义 |
| --- | --- |
| `document_id` | 稳定文档标识 |
| `title` | 标题 |
| `path` | 当前路径 |
| `category` | `entry`、`architecture`、`product`、`engineering`、`validation`、`research`、`archive` |
| `audience` | 首次使用者、维护者、研发、产品、客户等 |
| `status` | `current`、`draft`、`superseded`、`historical`、`missing_source` |
| `authority_scope` | 对哪些事实具有权威性 |
| `source_of_truth` | 代码、配置、规格或其他文档 |
| `superseded_by` | 替代文档，可空 |
| `maintenance_triggers` | 哪类代码/配置变更要求同步更新 |
| `broken_references` | 失效引用及分类 |

### 校验规则

- `README.md`、`agent.md` 和 `docs/README.md` 必须为 `current`。
- `superseded` 文档必须指向替代项或说明缺失来源。
- 入口文档不能把 `draft` 或 `historical` 内容描述为当前实现。

## 6. MigrationBatch（迁移批次）

| 字段 | 含义 |
| --- | --- |
| `batch_id` | `B0`～`B6` |
| `scope` | 本批文件、模块和资产范围 |
| `preconditions` | 必须先通过的基线和前置批次 |
| `compatibility_actions` | façade、重导出、路径映射等 |
| `verification_records` | 本批验证记录集合 |
| `rollback_plan` | 回退边界和方式 |
| `approval_required` | 是否需要用户对逐文件资产清单二次确认 |
| `approval_evidence` | 确认记录；不适用时说明原因 |
| `status` | `planned`、`baseline_ready`、`in_progress`、`verified`、`complete`、`rolled_back`、`blocked` |

### 状态转换

```text
planned -> baseline_ready -> in_progress -> verified -> complete
                              |              |
                              +-> blocked    +-> rolled_back
```

- 只有全部关键 `VerificationRecord` 通过后才能进入 `verified`。
- `approval_required=true` 且缺少 `approval_evidence` 时不得进入 `in_progress`。
- `complete` 不代表可以删除兼容层。
- 如果发现算法、API 或业务规则变化，批次进入 `blocked` 并返回规格澄清。

## 7. VerificationRecord（验证记录）

| 字段 | 含义 |
| --- | --- |
| `verification_id` | 唯一标识 |
| `batch_id` | 所属迁移批次 |
| `check_type` | 测试、构建、契约、性能、链接、卫生、人工旅程、视觉对比 |
| `command_or_steps` | 命令或可复现步骤 |
| `expected` | 期望结果 |
| `actual` | 实际结果摘要 |
| `evidence` | 日志、快照、截图或哈希路径 |
| `critical` | 是否为阻断门禁 |
| `status` | `pending`、`pass`、`fail`、`not_run` |

### 校验规则

- `critical=true` 的记录不得以 `not_run` 完成本批。
- 人工视觉检查不能替代类型检查、构建或契约测试；自动测试也不能替代关键 CSS 页面视觉对比。
