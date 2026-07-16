# 数据模型：生命周期工作区治理

## 生命周期阶段 LifecycleStage

| 字段 | 说明 |
| --- | --- |
| `id` | `00-governance`～`06-delivery` 的稳定编号名称 |
| `purpose` | 阶段解决的问题 |
| `entry_criteria` / `exit_criteria` | 进入和退出条件 |
| `authoritative_asset_types` | 本阶段拥有的资产类型 |
| `workpackages` | 工作包 ID 列表 |
| `next_stages` | 相邻或允许流转的阶段 |

约束：阶段 ID 全仓库唯一；每个阶段必须有 README 和工作包索引。

## 工作包 WorkPackage

| 字段 | 说明 |
| --- | --- |
| `id` | 阶段内唯一、稳定的 kebab-case 标识 |
| `stage` | 唯一主要生命周期阶段 |
| `purpose` | 独立业务目的 |
| `status` | `active`、`historical`、`orphaned`、`archived` |
| `inputs` | 输入资产与来源 |
| `entrypoints` | 可执行脚本或命令 |
| `results` | 生成或维护的成果 |
| `owner` | 主要维护者或 Agent 工作流 |
| `tracking_policy` | Git 跟踪策略：`tracked`、`ignored`、`local-only` |
| `retention_policy` | 默认保留等级和生命周期处置规则 |
| `related_workpackages` | 跨阶段引用，不复制资产 |

状态流转：`active -> historical -> archived`；无法确认生成关系时可进入 `orphaned`，补齐证据后回到 `active` 或 `historical`。

## 资产 Asset

| 字段 | 说明 |
| --- | --- |
| `path` | 当前仓库相对路径 |
| `asset_type` | 文档、代码、脚本、输入、样例、结果、交付物、日志、缓存等 |
| `stage` | 唯一主要阶段 |
| `workpackage` | 可选工作包 |
| `retention_class` | 七类保留等级之一 |
| `tracking_policy` | `tracked`、`ignored`、`local-only` |
| `sha256` | 迁移和正式成果校验值 |
| `source_relation` | `generated-by`、`input-to`、`references` 或 `unknown` |

约束：业务资产必须有阶段；正式二进制必须有哈希；`persistent-state`、`user-input`、`formal-output` 不得自动删除。

## 迁移条目 MigrationEntry

| 字段 | 说明 |
| --- | --- |
| `id` | 稳定迁移编号 |
| `source` / `target` | 旧、新路径 |
| `stage` / `workpackage` | 目标所有权 |
| `action` | `git-move`、`local-move`、`compatibility-entry`、`keep` |
| `sha256` | 移动前后校验 |
| `references` | 当前引用和历史引用 |
| `retention_class` | 迁移后的保留等级 |
| `rollback` | 单条回退动作 |
| `status` | `draft`、`prechecked`、`approved`、`moved`、`verified`、`rolled-back` |

## 清理候选 CleanupCandidate

| 字段 | 说明 |
| --- | --- |
| `path` | 候选路径 |
| `retention_class` | 清理类别 |
| `size_bytes` | 文件或目录大小 |
| `reason` | 归类依据 |
| `recommended_action` | 保留、归档、可清理、需确认 |
| `active_process_check` | 日志/锁是否完成进程检查 |
| `protected` | 是否禁止删除 |

清理状态：`discovered -> previewed -> approved -> cleaned`；默认停在 `previewed`。

## 兼容入口 CompatibilityEntry

记录必须留在根目录或固定发现路径的入口，包括路径、原因、业务所有者、目标路径和移除条件。兼容入口不得拥有重复业务内容。
