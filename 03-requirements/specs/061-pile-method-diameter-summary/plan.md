# 实施计划：桩基、承台与墩身结构摘要聚合

**分支/目录**：`061-pile-method-diameter-summary` | **日期**：2026-07-22 | **规格**：[spec.md](./spec.md)

**输入**：来自当前 `03-requirements/specs/061-pile-method-diameter-summary/spec.md` 的功能规格

## 概要

收紧现有 `workpointStructureSummaryProjection` 的类型专用签名：桩基只保留桩径，圆形墩身只保留截面直径，矩形/变截面墩身只保留长宽表达式；墩高、桩长和柱位不参与这些类型的摘要分组。统一尺寸文本的乘号和米单位，使承台输出 `16.5×16.5×6.0m`、圆形墩身输出 `φ1.5m`、矩形墩身输出 `2.0×1.5m`。

同时修正泸古客户主数据构建脚本对墩身截面列的读取：数值保留为 `diameter_m`，尺寸表达式保留为通用参数 `dimensions_m`。重建跟踪工作簿后，通过既有版本化导入/确认流程创建当前 Demo 项目的新主数据版本，不直接编辑数据库；资源、工期和求解器保持不变。

## 技术上下文

**语言/版本**：TypeScript 5.7、Node.js（前端）；现有 Node `.mjs` 客户数据构建脚本；Python/FastAPI 现有项目主数据导入服务（仅调用，不改代码）

**主要依赖**：React 19、Vite 6、`@oai/artifact-tool`（构建脚本既有依赖）、现有项目主数据通用参数与版本 API；不新增依赖

**存储**：跟踪的统一主数据 `.xlsx` 及检查报告；`.local-data/state/project-master.db` 中经现有 API 创建的新版本。无数据库 schema 迁移，不直接更新表行

**测试**：Node `node:test` 领域测试、构建脚本输出检查、现有项目主数据定向导入验证、TypeScript 类型检查、Vite 生产构建、`validate_docs.py`

**目标平台**：本地 FastAPI + React/Vite Demo；客户数据构建在现有 Windows 工作区执行

**项目类型**：前端领域投影＋客户数据构建与版本化导入

**性能目标**：继续对当前工点构件线性遍历；不增加网络请求或全项目详情扫描。客户工作簿仍为一次离线构建

**约束**：只改变桩基、承台和墩身摘要；不计算矩形面积；不改变墩高/桩长的排程用途；不修改 API 顶层结构、资源或求解器；保护构建脚本现有未提交线路落位改动

**规模/范围**：一个前端领域模块、一个前端测试文件、一个已有客户数据构建脚本及其三个既有生成输出、一个本地项目主数据新版本、本功能规格资产

## 生命周期归属

- **规格归属引用**：[`spec.md#生命周期归属`](./spec.md#生命周期归属)
- **实施路径**：
  - `04-demo/frontend/src/domain/resources.ts`
  - `04-demo/frontend/tests/resourceWorkpointScope.test.mjs`
  - `01-customer-validation/泸古1标/validation-results/_scripts/build_lugu_project_master.mjs`
  - `01-customer-validation/泸古1标/validation-results/泸古TJ-1标统一工点及桥梁结构物导入数据.xlsx`
  - `01-customer-validation/泸古1标/validation-results/泸古TJ-1标统一主数据_mapping-report.json`
  - `01-customer-validation/泸古1标/validation-results/泸古TJ-1标统一工点及桥梁结构物导入数据.xlsx.inspect.ndjson`
  - `.local-data/state/project-master.db`（local-only persistent-state，仅经版本 API 新增版本）

## Constitution 检查

*Phase 0 前检查：通过；Phase 1 设计后复核：通过。*

- 用户已明确矩形截面展示长×宽而非面积；无剩余阻断业务歧义。
- `spec.md` 已引用用户截图、feature 057、当前主数据、构建脚本和原始桥梁工作簿证据。
- 输入字段、输出文本、单位、签名、缺失/冲突、变截面表达式、历史版本和验收样例均可测试。
- `dimensions_m` 通过既有通用参数模型传递，不增加 API 顶层字段或数据库列；其页面语义由本功能契约明确。
- 资源影响、工期影响和求解影响均明确为无；桩长与墩高仍保留给既有排程逻辑，只从结构摘要签名中排除。
- 客户数据补齐采用生成新工作簿和版本化导入，不直接修改持久表或覆盖旧版本。
- 构建脚本已有未提交的线路空间对应组改动必须逐行保留；实施只在其基础上增加截面字段处理。
- 规格、客户输出、Demo 代码和本地状态各自保持既有生命周期主归属，不复制第二份权威资产。
- 不新增依赖、目录、兼容层或与本功能无关的重构。

## 项目结构

### 本功能文档

```text
03-requirements/specs/061-pile-method-diameter-summary/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── lower-structure-summary-ui-contract.md
└── tasks.md
```

### 生命周期与源码结构（仓库根目录）

```text
01-customer-validation/泸古1标/validation-results/
├── _scripts/build_lugu_project_master.mjs       # 保留矩形/变截面尺寸
├── 泸古TJ-1标统一工点及桥梁结构物导入数据.xlsx
├── 泸古TJ-1标统一主数据_mapping-report.json
└── 泸古TJ-1标统一工点及桥梁结构物导入数据.xlsx.inspect.ndjson

04-demo/frontend/
├── src/domain/resources.ts                      # 类型专用摘要签名与格式化
└── tests/resourceWorkpointScope.test.mjs        # 聚合、单位、诊断和非回归测试

.local-data/state/project-master.db              # 既有版本 API 创建新版本
```

**结构决策**：页面继续只消费 `resources.ts` 的纯派生 `displayText`，不在 React 层二次聚合。客户构建脚本负责把原始截面单元格无损映射为通用参数：数值→`diameter_m`，尺寸表达式→`dimensions_m`。通用项目主数据解析器已经接受任意 `param.*`，前端合同也已使用 `dimensions_m`，因此无需修改后端 API、数据库 schema 或前端公共类型。

## Phase 0：研究结论

- 当前拆行原因是桩长、墩高、`form` 等全部非工艺参数都进入签名；修正点位于前端领域投影而非页面循环。
- 当前承台尺寸是无单位文本 `form="16.5*16.5*6.0"`，应识别尺寸前缀、规范化乘号并只追加一个末尾 `m`，保持 `6.0` 文本精度。
- 原始“永宁河特大桥”表的墩身截面列既有数字，也有 `3.0*3.0`、`3.0*4.0`、`8.0*6.0/4.0`；现有 `numeric()` 对后者返回空，造成当前版本 80 个墩身缺少直径且没有长宽参数。
- 最小无损修复是在已有客户构建脚本增加尺寸表达式解析并输出 `param.dimensions_m`；位置与高度继续保留，供其他页面和排程使用。
- 当前确认版本不能从前端恢复已丢失值，必须用重建工作簿创建新版本；版本化导入可保留旧版本并避免原地数据修改。
- 页面未改 DOM 或样式，核心证据使用领域测试和新版本数据检查，不重复受 CDP 环境影响的浏览器门禁。

详见 [research.md](./research.md)。

## Phase 1：数据与界面契约

- [data-model.md](./data-model.md) 定义米制尺寸表达式、墩身截面标识、类型专用摘要键及原始数据到通用参数的映射。
- [lower-structure-summary-ui-contract.md](./contracts/lower-structure-summary-ui-contract.md) 固化桩基、承台、圆形/矩形/变截面墩身的分组、格式、诊断、导入和非回归边界。
- [quickstart.md](./quickstart.md) 提供三类摘要、原始矩形截面保留、新版本导入与既有业务非回归的验收步骤。

## 计划实现顺序

1. 在 `resourceWorkpointScope.test.mjs` 先固定桩基不同桩长合并、承台末尾单位、圆形墩身不同高度/位置合并、矩形长宽分组和缺失/冲突诊断。
2. 在 `resources.ts` 增加类型专用摘要参数选择和尺寸表达式格式化，确保签名与文案共用同一规范化结果。
3. 在现有客户构建脚本的未提交线路落位修改基础上，增加墩身截面分类与 `param.dimensions_m` 输出；不得回退或重写已有改动。
4. 重新生成跟踪工作簿、映射报告和检查文件，核对所有非空墩身截面均落入 `diameter_m` 或 `dimensions_m`。
5. 先在隔离临时状态验证工作簿导入无阻断错误；再通过现有 API 为当前 Demo 项目创建并确认新版本，记录旧/新版本 ID，不直接编辑数据库。
6. 运行一次风险匹配的定向验证批次；修正本功能相关失败，对有证据表明无关且不影响核心目标的问题记录后继续。

## 复杂度跟踪

无 Constitution 违反项。实施跨越客户数据构建与前端领域层，是恢复当前数据中已丢失矩形尺寸的最小完整链路；不扩展公共 API 或求解模型。
