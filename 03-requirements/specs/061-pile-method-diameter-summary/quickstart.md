# 快速验收：桩基、承台与墩身结构摘要聚合

## 前置条件

- 当前工点详情可被 `workpointStructureSummaryProjection` 读取。
- 工艺库包含旋挖钻、承台施工和爬模施工等测试工艺。
- 当前客户原始桥梁工作簿可供既有构建脚本读取。
- 当前 Demo 项目主数据更新必须走现有版本化导入/确认流程。

## 场景 1：桩基忽略桩长

输入同一工点：旋挖钻、桩径 1.5m、不同桩长，数量分别为 8 根和 12 根。

预期只有：

```text
旋挖钻-φ1.5m×20根
```

不得出现桩长；不同工艺或桩径仍分别显示。

## 场景 2：承台尺寸保留单位

输入 6 个 `form="16.5*16.5*6.0"` 的承台。

预期：

```text
承台施工-16.5×16.5×6.0m×6个
```

只追加一个 `m`，并保留 `6.0` 的源文本精度。

## 场景 3：圆形墩身忽略高度与位置

输入 10 根爬模施工、直径 1.5m，但 `height_m` 和 `form`（内柱/外柱）不同的墩身。

预期只有：

```text
爬模施工-φ1.5m×10根
```

## 场景 4：矩形墩身按长宽聚合

输入 5 根爬模施工、`dimensions_m="2.0*1.5"`、高度和位置不同的墩身。

预期只有：

```text
爬模施工-2.0×1.5m×5根
```

不得计算 `3.0m²`；`2.0*1.8` 必须形成另一项。

## 场景 5：原始矩形截面无损进入主数据

重建泸古统一主数据工作簿，并核对原始墩身截面列：

- 单值 `1.5` 输出 `param.diameter_m=1.5`；
- `3.0*4.0` 输出 `param.dimensions_m="3.0*4.0"`；
- `8.0*6.0/4.0` 输出 `param.dimensions_m="8.0*6.0/4.0"`；
- 所有非空源截面必须映射或产生明确诊断，静默丢失数为 0。

先使用隔离临时状态完成导入预检。预检无阻断错误后，再通过现有 API 为当前 Demo 项目创建并确认新版本；记录旧、新版本 ID，禁止直接编辑数据库。

## 场景 6：非回归

- 柱系梁、桩系梁和盖梁继续使用现有完整参数分组。
- 桩长、墩高和位置仍保存在项目主数据中并供既有排程使用。
- 资源数量、建议、启用状态、共享资源和求解结果不因只读摘要改变。

## 定向验证命令

```powershell
node --test 04-demo/frontend/tests/resourceWorkpointScope.test.mjs
npm.cmd --prefix 04-demo/frontend run typecheck
npm.cmd --prefix 04-demo/frontend run build
python 00-governance/repository-tools/validate_docs.py
git diff --check -- 03-requirements/specs/061-pile-method-diameter-summary 01-customer-validation/泸古1标/validation-results/_scripts/build_lugu_project_master.mjs 04-demo/frontend/src/domain/resources.ts 04-demo/frontend/tests/resourceWorkpointScope.test.mjs
```

客户工作簿构建和版本导入命令按既有脚本与 API 执行，实际命令、源/输出摘要、旧/新版本 ID 和退出结果记录在 `tasks.md` 实施记录中。相关失败必须修正后复验；有明确证据表明无关且不影响核心目标的问题可记录为剩余风险，不扩大排查范围。
