# 045 生命周期工作区治理实施报告

## 1. 结论

T019 批准的 1,127 条清单动作已全部执行并验证，包含 9 条 043 规格、日志、用户输入、持久状态、缓存和临时入口。最终清单状态为 `verified`：1,017 条物理移动、110 条兼容/保留动作，源冲突、目标缺失、跟踪策略错误和清单删除动作均为 0。

仓库已形成 `00-governance` 至 `06-delivery` 七阶段根结构，并以“阶段 → 工作包 → 输入/脚本/成果 → `.local-data` 本地产物”作为后续任务的持续归类规则。README、AGENTS、agent、架构、Spec Kit、Skill、npm、后端、Docker 和 Netlify 引用均已切换到最终路径。

## 2. 资产与工作包

### 七阶段迁移

| 阶段 | 清单条目 | 主要资产 |
| --- | ---: | --- |
| `00-governance` | 55 | 架构、资产策略、治理/迁移/清理工具和历史 |
| `01-discovery` | 11 | 客户调研、来源工作簿分析和报告构建 |
| `02-solution-analysis` | 4 | 产品方向和过程方案 |
| `03-requirements` | 386 | PRD、算法规则、完整 Spec Kit 规格树 |
| `04-demo` | 497 | FastAPI、React、样例、独立展示和 Demo Skill |
| `05-validation` | 94 | JSON 评审、泸古验证、计划粒度验证 |
| `06-delivery` | 80 | 正式二进制、案例总结和 AI PPT 工具 |

### 独立工作包

已登记并通过契约校验的 9 个工作包：

- 调研：`lugu-customer-research`、`lugu-source-data-analysis`。
- Demo：`json-task-viewer`、`schedule-result-viewer`。
- 验证：`json-schedule-review`、`lugu-validation-material`、`lugu-plan-granularity`。
- 交付：`ai-case-summary`、`ai-ppt-system`。

`ai-case-summary` 保持 `orphaned`，因为当前没有可确认的唯一生成器/当前版；没有伪造生成关系。

## 3. 本地产物与清理

- `.local-data/state/`：3 条本地持久状态；后端统一通过 `04-demo/backend/app/local_paths.py` 定位。
- `.local-data/logs/`：042 的 16 条历史日志按批准动作保留在 `legacy/`；045 另迁移 58 条散落日志到 `legacy-unclassified/`；新后台日志进入按启动时间分区的目录。
- `.local-data/archive/rebuildable/`、`cache/`、`tmp/`、`locks/`：分别承载可再生成物、缓存、临时文件和锁。
- `pytest.ini` 把后续 pytest 缓存固定到 `.local-data/cache/pytest`；迁移验证期间重建的根缓存整体归档，未删除。
- 独立 JSON 工作包的 `input/`、`output/` 已精确忽略，避免客户输入和可再生成结果误提交。

最终清理预览耗时 20.658539 秒（门槛 30 秒），识别 19 个候选入口、44,545,972 个已知字节、15 个聚合大小未知入口；未知分类 0、保护候选 0、删除 0。915 个持久状态/用户输入/正式成果文件在 dry-run 前后哈希不变。

## 4. 验证结果

| 门禁 | 结果 |
| --- | --- |
| `npm.cmd run verify` | 通过；类型检查、测试、构建、包体、架构和生命周期全链路通过 |
| 后端 | 406 passed，3 skipped |
| 前端 | 40 passed；Vite 构建成功 |
| 包体 | JS 483.08 kB、CSS 93.50 kB；以当前稳定输出刷新基线并继续执行 5% 门槛 |
| 架构 | 后端/前端基线一致；57 个当前 API 操作和 153 个公开模型 schema 冻结 |
| 治理 | 最终回归 39 passed；七阶段、9 个工作包、路径/文档/依赖/仓库校验全部通过 |
| 单服务 | health、SPA 根页、静态资源、SPA fallback 全部 HTTP 200，端口 8765 已释放 |
| Netlify | 静态发布和 SPA fallback 契约 2 passed |
| Docker | Dockerfile 构建上下文/启动/样例契约通过；本机没有 Docker CLI，未执行镜像构建 |
| Spec Kit / Skill | 045 指针正确；发现 11 个项目 Skill；Demo Skill 权威入口存在 |
| 独立工作包 | JSON 任务 HTML、工程排程报告/HTML 生成成功；固定查看器 2/2 存在 |
| 差异/安全 | `git diff --check` 通过；可见工作树密钥名、根日志、根锁、旧业务根、未知生成物均为 0 |

## 5. 清单、哈希与无删除边界

- `manifest-verification.json`：1,127/1,127 verified，9 条 043，缺失/冲突/跟踪错误/删除动作均为 0。
- `manifest-hash-refresh.json`：保留批准时哈希与最终实施哈希，记录路径兼容、文档和测试的受控内容修改，不覆盖批准证据。
- 清单执行器、空壳归档器和清理工具均没有执行删除；空旧目录整体移动到 `.local-data/archive/migration-empty-shells/`。
- 依赖恢复使用 `npm install --cache .npm-cache`，npm 按锁文件安装 71 个包并清理 8 个 `node_modules` 多余缓存包。该动作只重建可再生成依赖缓存，不涉及清单业务资产、用户输入、持久状态或正式成果。

## 6. Git 视图与剩余风险

- 当前没有执行 `git add`、commit 或 push；用户也未授权这些动作。由于 `.git` 在当前沙箱只读，Git 状态显示 838 个旧路径删除、911 个新路径未跟踪和 29 个入口修改。文件级清单验证使用文件系统目标、原索引和忽略规则完成；未来提交前必须一次性暂存全部迁移范围，让 Git 识别重命名，不能只提交新路径或只提交旧路径删除。
- 根 `outputs/lugu-validation-20260715` 是批准清单要求原位保留的外部缓存目录联接。治理校验只对此给出已登记警告；后续迁移或清理需单独确认。
- Docker 镜像未在本机实构建；已有 Docker 契约测试，但发布前仍建议在安装 Docker 的环境执行 `docker build`。
- `ai-case-summary` 的生成器/唯一当前版仍未确认，继续保持孤立关系提示。

## 7. 分批回退

1. 先按 045 清单的 `rollback` 字段，将七阶段路径分批反向移动到 042 中间路径并复核 SHA-256。
2. 需要继续回到 042 前结构时，再使用 042 清单；不得跳过中间映射直接批量回滚。
3. 本地日志、状态、输入和正式二进制分别回退，禁止把本地产物混入 Git；正式文件回退前复核哈希。
4. 平台入口最后回退：npm、Docker、Netlify、Spec Kit 和 Skill 必须与物理路径同步。
5. 任一回退都不含删除；如需删除缓存或旧目录，必须取得新的明确授权。

## 8. T077 后最终清单固化

- 最终复核时间：`2026-07-17T10:41:22.140036+08:00`。
- 清单状态：`verified`；1,127/1,127 条通过，其中物理迁移 1,017 条、原位兼容/保留 110 条、043 规格 9 条。
- 1,083 个文件端点完成 SHA-256 复核；98 条批准后受控内容刷新保留在 `manifest-hash-refresh.json` 的双哈希审计链中。
- 源冲突、目标缺失、跟踪意图错误和删除动作均为 0；`delete_authorized` 仍为 `false`。
- 根 `node_modules` 是 npm 验证后重新生成的已登记、已忽略兼容缓存；批准时的原缓存实例仍完整保存在 `.local-data/cache/legacy-node-modules/node_modules`。最终校验器仅对 `root-compatibility.json` 明确登记的 `local-cache` 重建路径放行，未移动或删除该新缓存。
