# AI PPT System

这是一个面向企业级软件产品汇报的 AI PPT 生成系统。它的核心不是让脚本替代大模型，而是把当前 Codex 对话的理解能力和本地稳定渲染流程组合起来。

## 工作包契约

### 目的

把结构化演示规格稳定渲染为 PPTX、HTML、PDF、PNG 和 Marp 成果，并把工具源码与本地生成物分开管理。

### 输入

- `input/outline.md`：业务大纲。
- `specs/slide_spec.json`：所有渲染器的唯一结构化输入。

### 运行

在本目录执行 `npm.cmd run all`；从仓库根目录可使用 `npm.cmd --prefix .\06-delivery\presentations\ai-ppt-system run all`。

### 成果

结构化规格保留在 `specs/`；渲染结果统一写入 `.local-data/archive/rebuildable/ai-ppt-system/output/`。

### 跟踪与保留

工具、模板、素材、输入和结构化规格跟踪；依赖与渲染结果属于 ignored/rebuildable，不进入交付源码目录。

## 工作方式

1. 在 Codex 对话里说明主题、听众、场景、目标、页数、风格和素材。
2. Codex 根据当前对话生成或修正 `specs/slide_spec.json`。
3. 本地脚本读取 `slide_spec.json`，输出 PPTX、HTML、PDF、PNG 和 Marp Markdown。
4. `check-layout` 检查内容密度和基础版式问题，Codex 再根据报告继续优化。

## 快速开始

```powershell
cd D:\codex_workspace\排程算法\06-delivery\presentations\ai-ppt-system
npm.cmd install
npx.cmd playwright install chromium
npm.cmd run all
```

完成后查看：

- `.local-data/archive/rebuildable/ai-ppt-system/output/pptx/deck.pptx`
- `.local-data/archive/rebuildable/ai-ppt-system/output/react/index.html`
- `.local-data/archive/rebuildable/ai-ppt-system/output/pdf/deck.pdf`
- `.local-data/archive/rebuildable/ai-ppt-system/output/png/slide-01.png`
- `.local-data/archive/rebuildable/ai-ppt-system/output/marp/slides.md`
- `.local-data/archive/rebuildable/ai-ppt-system/output/checks/layout-report.json`

## Codex 调用方式

可以在 Codex 对话框输入：

```text
使用 $ai-ppt-system，根据当前对话生成一份企业汇报 PPT。
```

或者：

```text
调用 $ai-ppt-system，读取 input/outline.md，生成可编辑 PPTX，并检查版式。
```

当需要大模型理解模板、判断页面类型、压缩文案或修正版式时，不要在脚本里调用外部 API，直接让当前 Codex 对话读取 `input/outline.md`、`specs/slide_spec.json` 和 `.local-data/archive/rebuildable/ai-ppt-system/output/checks/layout-report.json` 后修改结构化文件。

## 公司 PPT 模板

默认输出不使用公司模板，保持原有商务风格。

当提示词明确要求使用公司 PPT 模板时，在 `specs/slide_spec.json` 的 `deck` 下写入：

```json
{
  "template": {
    "id": "company",
    "variant": "light"
  }
}
```

- `variant: "light"`：使用公司模板标准版，作为未指定深浅时的默认值。
- `variant: "dark"`：使用公司模板投屏版，适合用户明确要求深色、暗色或投屏版。
- 如果提示词没有提到公司 PPT 模板，不要写 `deck.template`。

## 目录说明

- `input/outline.md`：原始大纲和业务输入。
- `specs/slide_spec.json`：结构化中间格式，是所有渲染器的唯一数据源。
- `templates/`：各 slide type 的模板说明。
- `themes/business.css`：Marp 与商务风格参考主题。
- `assets/company-template/`：公司 PPT 模板原文件及 PPTX 渲染器使用的背景、Logo 资源。
- `scripts/`：结构化、渲染、导出、版式检查脚本。
- `.local-data/archive/rebuildable/ai-ppt-system/output/`：所有本地生成结果，默认不跟踪。可用 `AI_PPT_OUTPUT_DIR` 临时覆盖输出目录。

## 常用命令

```powershell
npm.cmd run spec
npm.cmd run marp
npm.cmd run react
npm.cmd run pptx
npm.cmd run export:pdf
npm.cmd run export:png
npm.cmd run check
npm.cmd run verify
npm.cmd run all
```

可选 Marp 导出：

```powershell
npm.cmd run marp:pdf
npm.cmd run marp:pptx
```

## 内容约束

- 一页一个核心观点。
- 标题不超过 18 个中文字符。
- 每页正文不超过 3 个要点。
- 每条要点不超过 24 个中文字符。
- 不使用大段完整段落。
- 风格商务、克制、清晰。
- 优先表达业务价值，不堆技术术语。
