# 实施计划：根目录生命周期工作区治理

**分支/目录**：`045-lifecycle-workspace-governance` | **日期**：2026-07-16 | **规格**：[spec.md](./spec.md)

**输入**：来自当前 `specs/045-lifecycle-workspace-governance/spec.md` 的功能规格

## 概要

把仓库从按技术类型分散的 `docs/`、`tools/`、`outputs/`、`backend/`、`frontend/`、`specs/` 等根目录，重构为 `00-governance` 至 `06-delivery` 的生命周期工作区。阶段内以工作包连接输入、脚本、成果和本地产物；独立 JSON 展示、泸古调研/验证、AI 案例总结和 AI PPT 等形成可单独理解的工作包。通过机器描述、根目录白名单、Agent 路由、清理分级和迁移清单保证后续任务持续自动归类。

实施只改变所有权路径和治理入口，不改变 Demo 业务行为。由于当前工作树包含 042 的大规模未提交迁移、并行 043 和用户本地文件，所有物理移动必须先生成逐资产清单，按批次取得确认并保留回退边界。

## 技术上下文

**语言/版本**：Python 3.12、Node.js 22/24、TypeScript、PowerShell 5.1、Markdown/JSON

**主要依赖**：FastAPI、React、OR-Tools、现有 npm workspace、Spec Kit、Git；不新增运行时依赖

**存储**：受跟踪源码/文档/规格/二进制，以及 `.local-data` 中的数据库、JSON 状态、日志、缓存和临时文件

**测试**：pytest、前端 Node 测试、类型检查、生产构建、架构/仓库治理测试、JSON Schema、Markdown 链接、哈希和路径兼容检查

**目标平台**：Windows 本地开发、FastAPI 单服务/Docker、Netlify 静态前端、Codex/Spec Kit 工作流

**项目类型**：根目录级单仓库治理与路径迁移

**性能目标**：目录迁移不改变冻结排程性能；治理和清理预览在当前仓库规模下 30 秒内完成

**约束**：不改变 API、共享契约、求解规则、固定样例语义和正式交付内容；不删除未确认本地资产；保留 `.agents/`、`.specify/` 和必要根配置作为兼容入口

**规模/范围**：当前至少 594 个已跟踪文件，另有 042/043 新文件、独立本地 JSON 工作区、日志、缓存和生成物；最终逐文件数量以冻结清单为准

## Constitution 检查

*门禁：Phase 0 研究前与 Phase 1 设计后均已检查。*

- [x] 用户已确认根目录生命周期、独立工作包和清理分级模型。
- [x] `spec.md` 引用了当前文档、代码、042 迁移和本地工作区事实。
- [x] 不改变排程、资源、工期、CP-SAT 或前后端契约行为。
- [x] 已声明生命周期阶段、工作包、资产类型、保留策略和主要所有者。
- [x] 迁移要求逐资产清单、清单外保护、引用更新和回退。
- [x] 本地状态、用户输入和正式成果不会被当作缓存或临时文件清理。
- [x] Constitution 已升级为 1.2.0，允许生命周期阶段成为权威所有权边界。
- [x] Spec Kit 过程文档使用中文简体。

设计后复核：无 Constitution 违反项。045 本身在过渡期仍位于根 `specs/`；只有实施门禁通过后才随规格树迁入 `03-requirements/specs/`。

## 项目结构

### 本功能文档

```text
specs/045-lifecycle-workspace-governance/
├── discovery.md
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── root-layout-contract.md
│   ├── workpackage.schema.json
│   ├── cleanup-policy.schema.json
│   └── migration-manifest.schema.json
├── checklists/requirements.md
└── tasks.md
```

### 目标仓库结构

```text
00-governance/
├── README.md
├── architecture/
├── repository-tools/
├── asset-policy/
└── history/

01-discovery/
├── README.md
├── documents/
└── workpackages/
    ├── lugu-customer-research/
    └── lugu-source-data-analysis/

02-solution-analysis/
├── README.md
├── proposals/
├── decisions/
└── workpackages/

03-requirements/
├── README.md
├── product/
├── rules/
├── templates/
├── tooling/
└── specs/

04-demo/
├── README.md
├── backend/
├── frontend/
├── examples/
├── deployment/
├── runtime/
├── tools/
├── skills/
└── standalone/
    ├── json-task-viewer/
    └── schedule-result-viewer/

05-validation/
├── README.md
├── plans/
├── reports/
└── workpackages/
    ├── json-schedule-review/
    ├── lugu-validation-material/
    └── lugu-plan-granularity/

06-delivery/
├── README.md
├── deliverables/
├── presentations/ai-ppt-system/
├── case-studies/
└── workpackages/ai-case-summary/

.agents/       # Skill 发现兼容入口
.specify/      # Spec Kit 发现兼容入口
.local-data/
├── state/
├── logs/
├── cache/
├── tmp/
├── locks/
└── archive/
```

根目录仅保留 `README.md`、`AGENTS.md`、`agent.md`、Git/环境忽略文件、根 npm workspace 入口和平台确实要求的配置。兼容入口必须在 `00-governance/asset-policy/root-compatibility.json` 登记原因和所有者。

## 当前资产到目标所有权

| 当前资产 | 目标所有权 |
| --- | --- |
| `docs/architecture`、`tools/repo-governance`、路径迁移记录 | `00-governance` |
| `docs/research`、`outputs/lugu-report-*`、泸古调研报告构建器 | `01-discovery` 工作包 |
| 长期目标、产品中枢、LLM+CP-SAT、MVP 方案 | `02-solution-analysis` |
| 页面 PRD、算法/规则需求、`specs/` | `03-requirements` |
| `backend`、`frontend`、`examples`、Demo 镜像、运行工具 | `04-demo` |
| `local-json-task-review` 可复用工具 | `04-demo/standalone` |
| 真实 JSON 评审输入/结果、验证文档、`outputs/lugu-validation-*` | `05-validation` 工作包 |
| 正式交付物、AI 案例、奖项申报、AI PPT | `06-delivery` |
| `artifacts`、根 `logs`、工具缓存和临时锁 | `.local-data` 分级目录或登记的外部缓存 |

## 兼容与迁移策略

1. **双路径过渡**：先让根命令、Spec Kit 定位和治理检查能够识别目标路径，再执行物理移动；过渡完成后移除旧路径回退分支。
2. **根 npm 入口保留**：根 `package.json`/锁文件继续作为统一命令入口，workspace 改为 `04-demo/frontend`。
3. **Demo 入口更新**：后端命令改用 `--app-dir 04-demo/backend`；Docker、Netlify、单服务脚本和测试夹具同步调整。
4. **Spec Kit 过渡**：`.specify` 保留根入口，脚本先支持根 `specs` 与 `03-requirements/specs`，迁移后把活动目录切换到新位置并验证所有 skill。
5. **Skill 过渡**：通用 `speckit-*` 留在 `.agents/skills`；项目业务 Skill 的权威内容迁入阶段目录，发现目录保留最小入口和链接验证。
6. **历史内容保护**：规格内容、编号和旧路径引用原文不批量修改；通过治理历史映射解释物理路径变化。
7. **清单外保护**：042/043、未跟踪 Excel/DOCX、用户 JSON 和清单冻结后新增文件默认不移动。

## 实施阶段

### Phase 0：基线与清单设计

- 冻结 Git 状态、根目录、受跟踪文件、未跟踪/忽略资产、SHA-256、路径引用和运行入口。
- 生成逐资产迁移候选，并把资产标为迁移、兼容保留、清单外保护或待分类。
- 识别活动进程、锁文件、持久状态、用户输入、正式成果和孤立成果。

### Phase 1：治理骨架

- 创建七个阶段入口、根导航、阶段契约和工作包契约。
- 创建资产分类、根兼容入口、清理策略和迁移清单 Schema。
- 先写失败优先治理测试，尚不移动现有业务资产。

### Phase 2：工作包收敛

- 建立 JSON 展示、JSON 结果评审、泸古调研、泸古验证、计划粒度验证、AI 案例总结和 AI PPT 工作包。
- 将可复用脚本、批准样例、正式成果和本地产物分别登记。
- 无法绑定生成脚本的 AI 案例成果标记 `orphaned`，保留且不阻塞其他包。

### Phase 3：迁移审批门禁

- 生成完整机器清单和人类可读摘要，逐条包含路径、哈希、跟踪策略、引用、保留等级和回退。
- 按治理、调研/方案、需求/规格、Demo、验证、交付、本地资产分批汇总。
- 用户未明确确认前，不执行任何新增物理移动或清理。

### Phase 4：分批物理迁移

1. 迁移治理、调研和方案资产。
2. 迁移需求文档和完整规格树，更新 Spec Kit 活动路径。
3. 迁移 Demo 代码、样例、运行/部署工具，更新根命令。
4. 迁移验证工作包及其可复用脚本/批准结果。
5. 迁移交付、AI 案例和演示工具。
6. 仅按单独批准清单移动本地 JSON、日志、缓存和生成物；不自动删除。

### Phase 5：引用、治理与清理入口

- 更新 README、AGENTS、agent、当前文档、脚本、配置、测试和 Skill 路径。
- 增加后续任务归类门禁、工作包 Schema 校验和根目录白名单。
- 提供默认 dry-run 的清理入口，输出类别、大小、原因和建议动作。

### Phase 6：验证与收敛

- 校验迁移清单、哈希、跟踪状态、链接、历史映射和清单外资产。
- 运行后端、前端、架构、文档、Docker/Netlify、Spec Kit、Skill 和性能门禁。
- 运行 `$speckit-converge`，形成完成报告和批次回退说明。

## 复杂度跟踪

| 复杂度 | 必要性 | 未采用更简单方案的原因 |
| --- | --- | --- |
| 物理移动后端、前端和规格树 | 用户要求根目录阶段即真实所有权 | 只增加索引会继续保留两套目录语义，重复 044 的误解 |
| `.agents`/`.specify` 兼容入口 | Codex 和 Spec Kit 需要固定发现点 | 直接移动会导致当前工作流失效 |
| 迁移与清理双重确认 | 当前工作树和本地资产复杂 | 一次性批量移动或删除无法保护用户未提交资产 |
| 工作包机器描述 | 后续任务必须自动归类 | 仅靠 README 无法稳定阻止结构回退 |
