import fs from "node:fs";
import path from "node:path";
import { escapeHtml, readSpec, resolveProject, writeText } from "./shared.ts";

const spec = readSpec();

type Details = Record<string, any>;
type Slide = (typeof spec.slides)[number];

const esc = (value: unknown) => escapeHtml(String(value ?? ""));
const array = <T = any>(value: unknown): T[] => (Array.isArray(value) ? value : []);
const assetDataCache = new Map<string, string>();

function assetDataUri(relativePath: string) {
  const normalized = relativePath.replace(/\\/g, "/");
  const cached = assetDataCache.get(normalized);
  if (cached) return cached;
  const absolutePath = resolveProject(...normalized.split("/"));
  const extension = path.extname(absolutePath).toLowerCase();
  const mime = extension === ".jpg" || extension === ".jpeg" ? "image/jpeg" : "image/png";
  const uri = `data:${mime};base64,${fs.readFileSync(absolutePath).toString("base64")}`;
  assetDataCache.set(normalized, uri);
  return uri;
}

function isEngineeringCase(slide: Slide) {
  return String(slide.layout ?? "").startsWith("engineering-case-");
}

function sectionFor(slide: Slide) {
  if (slide.page === 1) return "OPENING";
  if (slide.page <= 3) return "WHY SDD";
  if (slide.layout === "application-section") {
    if (slide.details?.tone === "engineering") return "ENGINEERING APPLICATION";
    if (slide.details?.tone === "future") return "SUMMARY & NEXT STEP";
    return "PRODUCT APPLICATION";
  }
  if (isEngineeringCase(slide)) return "ENGINEERING PRACTICE";
  if (slide.layout === "integrated-collaboration" || slide.layout === "traceability-gaps") return "HANDOFF";
  if (slide.page <= 11 || slide.layout === "pm-minimal-input" || slide.layout === "quadrant-collaboration") return "PRODUCT PRACTICE";
  return "NEXT STAGE";
}

function toneFor(slide: Slide) {
  if (slide.page === 1 || slide.layout === "integrated-collaboration") return "mixed";
  if (slide.page === 2) return "shared";
  if (slide.layout === "application-section") {
    if (slide.details?.tone === "engineering") return "engineering";
    if (slide.details?.tone === "future") return "future";
    return "product";
  }
  if (slide.page === 3 || isEngineeringCase(slide)) return "engineering";
  if (slide.page <= 11 || slide.layout === "pm-minimal-input" || slide.layout === "quadrant-collaboration") return "product";
  if (slide.layout === "traceability-gaps") return "shared";
  return "future";
}

function tags(items: unknown, className = "tag-row") {
  return `<div class="${className}">${array(items)
    .map((item) => `<span class="fit-check">${esc(item)}</span>`)
    .join("")}</div>`;
}

function simpleList(items: unknown, className = "plain-list") {
  return `<ul class="${className}">${array(items)
    .map((item) => `<li class="fit-check">${esc(item)}</li>`)
    .join("")}</ul>`;
}

function renderCover(slide: Slide) {
  const d = (slide.details ?? {}) as Details;
  const bridge = (d.bridge ?? {}) as Details;
  const renderEngine = (engine: Details, tone: string) => `<div class="engine engine-${tone} layout-item">
    <div class="engine-head">
      <strong class="fit-check">${esc(engine.title)}</strong>
      <span class="fit-check">${esc(engine.subtitle)}</span>
    </div>
    <div class="engine-loop">
      <svg class="engine-loop-arrows" viewBox="0 0 280 240" preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <marker id="engine-arrow-${tone}" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
            <path d="M0,0 L7,3.5 L0,7 Z"></path>
          </marker>
        </defs>
        <path d="M72 18 C116 2 170 2 210 22"></path>
        <path d="M257 66 C272 105 267 151 235 181"></path>
        <path d="M207 219 C160 236 105 232 68 210"></path>
        <path d="M23 175 C7 134 12 83 45 50"></path>
      </svg>
      ${array(engine.nodes)
        .map(
          (node, index) =>
            `<div class="engine-node fit-check" data-index="${index + 1}">${esc(node)}</div>`
        )
        .join("")}
      <div class="engine-core" aria-hidden="true">AI</div>
    </div>
  </div>`;

  return `<div class="cover-layout">
    <div class="cover-copy">
      <h1 class="fit-check">${esc(slide.title)}</h1>
      ${tags(slide.points, "cover-tags")}
    </div>
    <div class="cover-visual">
      ${renderEngine(d.product ?? {}, "product")}
      <div class="cover-bridge layout-item">
        <div class="bridge-role-row">
          <span class="fit-check">${esc(bridge.from)}</span>
          <span class="fit-check">${esc(bridge.to)}</span>
        </div>
        <div class="bridge-arrow" aria-hidden="true"></div>
        <div class="bridge-drop" aria-hidden="true"></div>
        <div class="bridge-file">
          <small class="fit-check">${esc(bridge.label)}</small>
          <strong class="fit-check">${esc(bridge.artifact)}</strong>
        </div>
      </div>
      ${renderEngine(d.rd ?? {}, "engineering")}
    </div>
  </div>`;
}

function renderVibeToSddOverview(d: Details) {
  const vibe = (d.vibe ?? {}) as Details;
  const decision = (d.decision ?? {}) as Details;
  const sdd = (d.sdd ?? {}) as Details;

  return `<div class="vibe-sdd-layout">
    <div class="vibe-panel layout-item">
      <div class="vibe-panel-title fit-check">${esc(vibe.title)}</div>
      <div class="vibe-flow">
        ${array(vibe.flow)
          .map(
            (item, index, items) =>
              `<div class="vibe-flow-node fit-check">${esc(item)}</div>${index < items.length - 1 ? '<i aria-hidden="true">→</i>' : ""}`
          )
          .join("")}
      </div>
      <div class="vibe-pain-title fit-check">${esc(vibe.pain_title)}</div>
      <div class="vibe-pain-list">
        ${array(vibe.pains)
          .map((item, index) => `<div><span>${String(index + 1).padStart(2, "0")}</span><strong class="fit-check">${esc(item)}</strong></div>`)
          .join("")}
      </div>
    </div>
    <div class="vibe-decision layout-item">
      <span class="fit-check">${esc(decision.label)}</span>
      <i aria-hidden="true">→</i>
      <strong class="fit-check">${esc(decision.value)}</strong>
    </div>
    <div class="sdd-definition-panel layout-item">
      <div class="sdd-definition-title fit-check">${esc(sdd.title)}</div>
      <div class="sdd-definition-quote fit-check">${esc(sdd.definition)}</div>
      <div class="sdd-principles">
        ${array<Details>(sdd.principles)
          .map(
            (item, index) => `<div class="sdd-principle">
              <span>${String(index + 1).padStart(2, "0")}</span>
              <strong class="fit-check">${esc(item.title)}</strong>
              <p class="fit-check">${esc(item.detail)}</p>
            </div>`
          )
          .join("")}
      </div>
    </div>
  </div>
  <div class="vibe-sdd-summary layout-item fit-check">${esc(d.summary)}</div>`;
}

function renderSddToolsTable(d: Details) {
  const columns = array(d.columns);
  return `<div class="sdd-tools-wrap">
    <table class="sdd-tools-table layout-item">
      <thead>
        <tr>${columns.map((column) => `<th class="fit-check">${esc(column)}</th>`).join("")}</tr>
      </thead>
      <tbody>
        ${array<Details>(d.rows)
          .map(
            (row) => `<tr>
              <td class="fit-check">${esc(row.dimension)}</td>
              ${array(row.values)
                .map((value) => `<td class="fit-check">${esc(value)}</td>`)
                .join("")}
            </tr>`
          )
          .join("")}
      </tbody>
    </table>
    <div class="sdd-tool-selections">
      ${array<Details>(d.selections)
        .map(
          (item) => `<div class="sdd-tool-selection ${esc(item.tone)} layout-item">
            <span class="fit-check">${esc(item.owner)}</span>
            <strong class="fit-check">${esc(item.tool)}</strong>
            <p class="fit-check">${esc(item.reason)}</p>
          </div>`
        )
        .join("")}
    </div>
  </div>`;
}

function renderOneLineAiGap(d: Details) {
  const lanes = array<Details>(d.lanes);
  return `<div class="one-line-layout">
    <div class="one-line-lanes">
      ${lanes
        .map(
          (lane) => `<div class="one-line-lane ${esc(lane.tone)} layout-item">
            <div class="one-line-role fit-check">${esc(lane.role)}</div>
            <div class="one-line-flow">
              <div class="one-line-node input">
                <span>输入</span>
                <strong class="fit-check">${esc(lane.input)}</strong>
              </div>
              <i aria-hidden="true">→</i>
              <div class="one-line-node agent">
                <span>AI</span>
                <strong class="fit-check">${esc(lane.agent)}</strong>
              </div>
              <i aria-hidden="true">→</i>
              <div class="one-line-node output">
                <span>输出</span>
                <strong class="fit-check">${esc(lane.output)}</strong>
              </div>
            </div>
            <div class="one-line-benefit fit-check">${esc(lane.benefit)}</div>
          </div>`
        )
        .join("")}
    </div>
    <div class="one-line-gap-title"><span>局部速度提升</span><b>≠</b><strong>可控交付</strong></div>
    <div class="one-line-gaps">
      ${array<Details>(d.gaps)
        .map(
          (gap, index) => `<div class="one-line-gap layout-item">
            <span>${String(index + 1).padStart(2, "0")}</span>
            <strong class="fit-check">${esc(gap.title)}</strong>
            <p class="fit-check">${esc(gap.detail)}</p>
          </div>`
        )
        .join("")}
    </div>
  </div>
  <div class="one-line-summary layout-item fit-check">${esc(d.summary)}</div>`;
}

function renderSddModeShift(d: Details) {
  const renderMode = (mode: Details, tone: string) => `<div class="sdd-mode ${tone} layout-item">
    <div class="sdd-mode-title fit-check">${esc(mode.title)}</div>
    <div class="sdd-mode-core fit-check">${esc(mode.core)}</div>
    <div class="sdd-mode-items">
      ${array(mode.items)
        .map((item, index) => `<div><span>${String(index + 1).padStart(2, "0")}</span><strong class="fit-check">${esc(item)}</strong></div>`)
        .join("")}
    </div>
  </div>`;
  const choice = (d.choice ?? {}) as Details;

  return `<div class="sdd-shift-layout">
    <div class="sdd-shift-modes">
      ${renderMode(d.before ?? {}, "before")}
      <div class="sdd-shift-arrow layout-item">
        <span>研发模式升级</span>
        <i aria-hidden="true">→</i>
      </div>
      ${renderMode(d.after ?? {}, "after")}
    </div>
    <div class="sdd-shift-table layout-item">
      ${array<Details>(d.shifts)
        .map(
          (shift) => `<div class="sdd-shift-row">
            <span class="fit-check">${esc(shift.dimension)}</span>
            <b class="fit-check">${esc(shift.from)}</b>
            <i aria-hidden="true">→</i>
            <strong class="fit-check">${esc(shift.to)}</strong>
          </div>`
        )
        .join("")}
    </div>
    <div class="sdd-choice layout-item">
      <strong class="fit-check">${esc(choice.title)}</strong>
      <div>
        ${array(choice.items)
          .map((item) => `<span class="fit-check">${esc(item)}</span>`)
          .join("")}
      </div>
    </div>
  </div>
  <div class="sdd-shift-summary layout-item fit-check">${esc(d.summary)}</div>`;
}

function renderDualLoops(d: Details) {
  const renderLoop = (loop: Details) => `<div class="loop-panel ${esc(loop.tone)} layout-item">
    <div class="loop-title fit-check">${esc(loop.title)}</div>
    <div class="loop-track">
      ${array(loop.nodes)
        .map(
          (node, index) => `<div class="loop-step">
            <span class="loop-index">${String(index + 1).padStart(2, "0")}</span>
            <strong class="fit-check">${esc(node)}</strong>
          </div>`
        )
        .join("")}
    </div>
    <div class="loop-return" aria-hidden="true"><span>持续迭代</span></div>
  </div>`;

  return `<div class="dual-loop-layout">
    ${renderLoop(d.product ?? {})}
    <div class="current-handoff layout-item">
      <span>当前交接</span>
      <strong class="fit-check">${esc(d.handoff)}</strong>
      <i aria-hidden="true"></i>
    </div>
    ${renderLoop(d.rd ?? {})}
  </div>
  <div class="conclusion-strip layout-item fit-check">${esc(d.conclusion)}</div>`;
}

function renderIntegratedCollaboration(d: Details) {
  const renderLoop = (loop: Details, tone: string) => `<div class="collab-loop ${tone} layout-item">
    <div class="collab-loop-title fit-check">${esc(loop.title)}</div>
    <div class="collab-loop-track">
      ${array(loop.nodes)
        .map(
          (node, index, items) =>
            `<div class="collab-loop-step fit-check">${esc(node)}</div>${
              index < items.length - 1 ? '<div class="collab-step-arrow" aria-hidden="true"></div>' : ""
            }`
        )
        .join("")}
    </div>
    <div class="collab-return" aria-hidden="true"><span>持续迭代</span></div>
  </div>`;
  const handoff = (d.handoff ?? {}) as Details;

  return `<div class="collab-overview">
    <div class="collab-loops">
      ${renderLoop(d.product_loop ?? {}, "product")}
      <div class="collab-handoff layout-item">
        <div class="collab-handoff-roles">
          <span class="fit-check">${esc(handoff.from)}</span>
          <span class="fit-check">${esc(handoff.to)}</span>
        </div>
        <div class="collab-handoff-arrow" aria-hidden="true"></div>
        <div class="collab-handoff-card">
          <small class="fit-check">${esc(handoff.label)}</small>
          <strong class="fit-check">${esc(handoff.artifact)}</strong>
          ${handoff.meaning ? `<span class="fit-check">${esc(handoff.meaning)}</span>` : ""}
        </div>
      </div>
      ${renderLoop(d.rd_loop ?? {}, "engineering")}
    </div>
    <div class="collab-spaces">
      ${array<Details>(d.spaces)
        .map(
          (space) => `<div class="collab-space ${esc(space.tone)} layout-item">
            <div class="collab-space-title fit-check">${esc(space.title)}</div>
            <div class="collab-space-items">
              ${array<Details>(space.items)
                .map(
                  (item) => `<div class="collab-space-item">
                    <span class="fit-check">${esc(item.label)}</span>
                    <strong class="fit-check">${esc(item.value)}</strong>
                  </div>`
                )
                .join("")}
            </div>
          </div>`
        )
        .join("")}
    </div>
    <div class="collab-conclusion layout-item fit-check">${esc(d.conclusion)}</div>
  </div>`;
}

function renderProductAgentOperatingModel(d: Details) {
  const manager = (d.manager ?? {}) as Details;
  const harness = (d.harness ?? {}) as Details;
  const agent = (d.agent ?? {}) as Details;
  const model = (agent.model ?? {}) as Details;
  const skill = (agent.skill ?? {}) as Details;
  const tools = (agent.tools ?? {}) as Details;
  const renderCapability = (item: string) => `<span class="fit-check">${esc(item)}</span>`;
  const renderEngineCard = (item: Details, tone: string) => `<div class="agent-engine-card ${tone} layout-item">
    <strong class="fit-check">${esc(item.title)}</strong>
    <p class="fit-check">${esc(item.description)}</p>
    <div class="agent-engine-items">${array(item.items).map(renderCapability).join("")}</div>
  </div>`;

  return `<div class="agent-model-body">
    <div class="agent-system">
      <div class="agent-manager-row layout-item">
        <div class="agent-manager-heading">
          <strong class="fit-check">${esc(manager.title)}</strong>
          <span class="fit-check">${esc(manager.subtitle)}</span>
        </div>
        <div class="agent-manager-items">
          ${array(manager.items).map(renderCapability).join("")}
        </div>
      </div>
      <div class="agent-governance-link" aria-hidden="true"><span></span></div>
      <div class="agent-harness layout-item">
        <div class="agent-harness-header">
          <div>
            <strong class="fit-check">${esc(harness.title)}</strong>
            <span class="fit-check">${esc(harness.subtitle)}</span>
          </div>
          <div class="agent-harness-capabilities">
            ${array(harness.capabilities).map(renderCapability).join("")}
          </div>
        </div>
        <div class="agent-orchestrator">
          <div class="agent-orchestrator-header">
            <div>
              <strong class="fit-check">${esc(agent.title)}</strong>
              <span class="fit-check">${esc(agent.subtitle)}</span>
            </div>
            <div class="agent-process">
              ${array(agent.process)
                .map(
                  (item, index, items) =>
                    `${renderCapability(item)}${index < items.length - 1 ? '<i aria-hidden="true"></i>' : ""}`
                )
                .join("")}
            </div>
          </div>
          <div class="agent-engine-grid">
            ${renderEngineCard(model, "model")}
            ${renderEngineCard(skill, "skill")}
            ${renderEngineCard(tools, "tools")}
          </div>
        </div>
        <div class="agent-system-relationship">
          <strong>运行关系</strong>
          ${array(agent.relationship)
            .map(
              (item, index, items) =>
                `<span class="fit-check">${esc(item)}</span>${index < items.length - 1 ? '<i aria-hidden="true">→</i>' : ""}`
            )
            .join("")}
        </div>
      </div>
    </div>
    <div class="agent-model-principles">
      <div class="agent-principles-title">工作边界</div>
      ${array<Details>(d.principles)
        .map(
          (item, index) => `<div class="agent-principle layout-item">
            <span>${String(index + 1).padStart(2, "0")}</span>
            <strong class="fit-check">${esc(item.title)}</strong>
            <p class="fit-check">${esc(item.text)}</p>
          </div>`
        )
        .join("")}
    </div>
  </div>
  <div class="agent-result-chain">
    <div class="agent-result-label">结果链</div>
    ${array(d.result_chain)
      .map(
        (item, index, items) =>
          `<div class="agent-result-node layout-item fit-check">${esc(item)}</div>${
            index < items.length - 1 ? '<div class="agent-result-arrow" aria-hidden="true"></div>' : ""
          }`
      )
      .join("")}
  </div>`;
}

function renderApplicationSection(d: Details, slide: Slide) {
  const tone = d.tone === "engineering" ? "engineering" : d.tone === "future" ? "future" : "product";
  const stages = array(d.stages);
  return `<div class="application-section-layout application-section-${tone}">
    <div class="application-section-orbit" aria-hidden="true"></div>
    <div class="application-section-index" aria-hidden="true">${esc(d.index)}</div>
    <div class="application-section-copy">
      <h1>${esc(slide.title)}</h1>
      <div class="application-section-subtitle fit-check">${esc(slide.message)}</div>
      <p class="application-section-statement fit-check">${esc(d.statement)}</p>
    </div>
    <div class="application-section-flow">
      ${stages
        .map(
          (stage, index) => `<div class="application-section-stage layout-item">
            <span>${String(index + 1).padStart(2, "0")}</span>
            <strong class="fit-check">${esc(stage)}</strong>
          </div>${index < stages.length - 1 ? '<i aria-hidden="true"></i>' : ""}`
        )
        .join("")}
    </div>
  </div>`;
}

function renderProjectFrameworkMap(d: Details) {
  return `<div class="project-framework-map">
    <div class="project-framework-main">
      <div class="project-tree-panel layout-item">
        <div class="project-panel-title">目录结构</div>
        <div class="project-tree">
          ${array(d.tree)
            .map((line) => `<div class="fit-check">${esc(line)}</div>`)
            .join("")}
        </div>
      </div>
      <div class="project-mapping-panel layout-item">
        <div class="project-panel-title">区域职责</div>
        <div class="project-mapping-head">
          <span>区域</span>
          <span>回答的问题</span>
        </div>
        ${array<Details>(d.mappings)
          .map(
            (item) => `<div class="project-mapping-row">
              <strong class="fit-check">${esc(item.area)}</strong>
              <span class="fit-check">${esc(item.question)}</span>
            </div>`
          )
          .join("")}
      </div>
    </div>
    <div class="project-governance-assets">
      ${array<Details>(d.governance)
        .map(
          (item) => `<div class="project-governance-card layout-item">
            <strong class="fit-check">${esc(item.name)}</strong>
            <span class="fit-check">${esc(item.meaning)}</span>
          </div>`
        )
        .join("")}
    </div>
    <div class="project-framework-summary layout-item fit-check">${esc(d.summary)}</div>
  </div>`;
}

function renderPracticeSopMap(d: Details) {
  let stepNumber = 0;
  return `<div class="practice-sop-map">
    <div class="practice-sop-stages">
      ${array<Details>(d.stages)
        .map(
          (stage) => `<div class="practice-sop-stage ${esc(stage.tone)} layout-item">
            <div class="practice-stage-head">
              <span>${esc(stage.index)}</span>
              <strong class="fit-check">${esc(stage.title)}</strong>
            </div>
            ${stage.gate ? `<div class="practice-stage-gate fit-check">${esc(stage.gate)}</div>` : '<div class="practice-stage-gate empty"></div>'}
            <div class="practice-stage-steps">
              ${array(stage.steps)
                .map((step) => {
                  stepNumber += 1;
                  return `<div class="practice-stage-step layout-item">
                    <span>${String(stepNumber).padStart(2, "0")}</span>
                    <strong class="fit-check">${esc(step)}</strong>
                  </div>`;
                })
                .join("")}
            </div>
            <div class="practice-stage-artifact fit-check">${esc(stage.artifact)}</div>
          </div>`
        )
        .join("")}
    </div>
    <div class="practice-sop-summary layout-item fit-check">${esc(d.summary)}</div>
  </div>`;
}

function renderEvidenceRequirementTable(d: Details) {
  return `<div class="evidence-requirement-layout">
    <div class="evidence-analysis-table">
      <div class="evidence-table-head">
        <span>SOP</span>
        <span>核心动作</span>
        <span>注意事项与坑</span>
      </div>
      ${array<Details>(d.rows)
        .map(
          (row) => `<div class="evidence-table-row layout-item">
            <strong class="fit-check">${esc(row.sop)}</strong>
            <span class="fit-check">${esc(row.action)}</span>
            <span class="risk fit-check">${esc(row.risk)}</span>
          </div>`
        )
        .join("")}
    </div>
    <div class="evidence-case-grid">
      ${array<Details>(d.cases)
        .map(
          (item) => `<div class="evidence-case layout-item">
            <strong class="fit-check">${esc(item.project)}</strong>
            <span class="fit-check">${esc(item.evidence)}</span>
          </div>`
        )
        .join("")}
    </div>
    <div class="evidence-summary layout-item fit-check">${esc(d.summary)}</div>
  </div>`;
}

function renderSpeckitToDemo(d: Details) {
  const gateIndex = Number(d.gate_index ?? -1);
  return `<div class="speckit-demo-layout">
    <div class="speckit-pipeline">
      ${array(d.pipeline)
        .map(
          (item, index, items) =>
            `<div class="speckit-pipeline-node ${index === gateIndex ? "gate" : ""} layout-item">
              <span>${String(index + 1).padStart(2, "0")}</span>
              <strong class="fit-check">${esc(item)}</strong>
            </div>${index < items.length - 1 ? '<div class="speckit-pipeline-arrow" aria-hidden="true"></div>' : ""}`
        )
        .join("")}
    </div>
    <div class="speckit-demo-body">
      <div class="speckit-actions">
        ${array<Details>(d.actions)
          .map(
            (action, index) => `<div class="speckit-action layout-item">
              <div class="speckit-action-title"><span>0${index + 1}</span><strong class="fit-check">${esc(action.title)}</strong></div>
              ${simpleList(action.items, "speckit-action-list")}
            </div>`
          )
          .join("")}
      </div>
      <div class="speckit-pitfalls layout-item">
        <div class="speckit-pitfall-title">避坑区</div>
        ${array(d.pitfalls)
          .map((item) => `<div class="speckit-pitfall fit-check">${esc(item)}</div>`)
          .join("")}
      </div>
    </div>
    <div class="speckit-demo-summary layout-item fit-check">${esc(d.summary)}</div>
  </div>`;
}

function renderValidationFeedbackDelivery(d: Details) {
  return `<div class="validation-delivery-layout">
    <div class="validation-delivery-columns">
      <div class="validation-column layout-item">
        <div class="validation-column-title">三级验证</div>
        ${array<Details>(d.validation)
          .map(
            (item, index) => `<div class="validation-level">
              <span>${String(index + 1).padStart(2, "0")}</span>
              <strong class="fit-check">${esc(item.level)}</strong>
              <p class="fit-check">${esc(item.items)}</p>
            </div>`
          )
          .join("")}
      </div>
      <div class="feedback-column layout-item">
        <div class="feedback-column-title">Demo反馈分流</div>
        ${array(d.feedback)
          .map((item) => `<div class="feedback-route-line fit-check">${esc(item)}</div>`)
          .join("")}
      </div>
      <div class="delivery-column layout-item">
        <div class="delivery-column-title">研发交付包</div>
        ${array(d.delivery)
          .map((item, index) => `<div class="delivery-package-line"><span>0${index + 1}</span><strong class="fit-check">${esc(item)}</strong></div>`)
          .join("")}
      </div>
    </div>
    <div class="validation-evolution">
      ${array<Details>(d.evolution)
        .map(
          (item) => `<div class="evolution-case layout-item">
            <div class="evolution-case-main">
              <span class="evolution-kind fit-check">${esc(item.label)}</span>
              <div class="evolution-route"><strong class="fit-check">${esc(item.from)}</strong><span aria-hidden="true">→</span><strong class="fit-check">${esc(item.to)}</strong></div>
            </div>
            <p class="fit-check">${esc(item.meaning)}</p>
          </div>`
        )
        .join("")}
    </div>
  </div>`;
}

function renderSkillCapabilityStack(d: Details) {
  return `<div class="skill-capability-layout">
    <div class="skill-level-stack">
      ${array<Details>(d.levels)
        .map(
          (level, index) => `<div class="skill-level level-${index + 1} layout-item">
            <div class="skill-level-title"><span>0${index + 1}</span><strong class="fit-check">${esc(level.title)}</strong></div>
            <div class="skill-level-items">
              ${array(level.items)
                .map((item) => `<span class="fit-check">${esc(item)}</span>`)
                .join("")}
            </div>
          </div>`
        )
        .join("")}
    </div>
    <div class="skill-routing-panel">
      <div class="skill-route-block layout-item">
        <div class="skill-block-title">Agent路由</div>
        ${array(d.routes)
          .map((item) => `<div class="skill-route-line fit-check">${esc(item)}</div>`)
          .join("")}
      </div>
      <div class="skill-quality-block layout-item">
        <div class="skill-block-title">合格Skill必须说明</div>
        <div class="skill-quality-grid">
          ${array(d.quality)
            .map((item) => `<span class="fit-check">${esc(item)}</span>`)
            .join("")}
        </div>
      </div>
    </div>
  </div>
  <div class="skill-capability-summary layout-item fit-check">${esc(d.summary)}</div>`;
}

function renderPmMinimalInput(d: Details) {
  return `<div class="pm-input-layout">
    <div class="pm-minimum-inputs">
      <div class="pm-input-title">四项最小输入</div>
      ${array(d.inputs)
        .map(
          (item, index) => `<div class="pm-input-card layout-item">
            <span>${String(index + 1).padStart(2, "0")}</span>
            <strong class="fit-check">${esc(item)}</strong>
          </div>`
        )
        .join("")}
    </div>
    <div class="pm-trigger-prompts">
      <div class="pm-prompt-title">自然语言触发语</div>
      <div class="pm-prompt-grid">
        ${array(d.prompts)
          .map((item) => `<div class="pm-prompt-bubble layout-item fit-check">${esc(item)}</div>`)
          .join("")}
      </div>
    </div>
  </div>
  <div class="pm-input-principle layout-item fit-check">${esc(d.principle)}</div>`;
}

function renderQuadrantCollaboration(d: Details) {
  const axis = (d.axis ?? {}) as Details;
  return `<div class="quadrant-collab-layout">
    <div class="quadrant-coordinate">
      <div class="quadrant-coordinate-title-y fit-check">${esc(axis.y)}</div>
      <div class="quadrant-coordinate-plot">
        <div class="quadrant-coordinate-axis-x" aria-hidden="true"></div>
        <div class="quadrant-coordinate-axis-y" aria-hidden="true"></div>
        <span class="quadrant-coordinate-label ai-unknown fit-check">${esc(axis.x_left)}</span>
        <span class="quadrant-coordinate-label ai-known fit-check">${esc(axis.x_right)}</span>
        <span class="quadrant-coordinate-label pm-known fit-check">${esc(axis.y_top)}</span>
        <span class="quadrant-coordinate-label pm-unknown fit-check">${esc(axis.y_bottom)}</span>
        <span class="quadrant-coordinate-origin">任务</span>
        ${array<Details>(d.quadrants)
          .map(
            (item) => `<article class="quadrant-card coord-card ${esc(item.tone)} layout-item">
              <div class="quadrant-card-head">
                <span>${esc(item.icon)}</span>
                <strong class="fit-check">${esc(item.code)} ${esc(item.title)}</strong>
              </div>
              <p class="quadrant-collab fit-check"><b>协作</b>${esc(item.collaboration)}</p>
              <p class="quadrant-case fit-check"><b>案例</b>${esc(item.case)}</p>
              <p class="quadrant-risk fit-check"><b>风险</b>${esc(item.risk)}</p>
            </article>`
          )
          .join("")}
      </div>
      <div class="quadrant-coordinate-title-x fit-check">${esc(axis.x)}</div>
    </div>
    <div class="quadrant-migration">
      <div class="quadrant-migration-label">象限迁移</div>
      ${array<Details>(d.migration)
        .map(
          (item, index, items) => `<div class="quadrant-migration-step ${esc(item.tone)} layout-item">
            <strong class="fit-check">${esc(item.code)} ${esc(item.title)}</strong>
            <span class="fit-check">${esc(item.detail)}</span>
          </div>${index < items.length - 1 ? '<i aria-hidden="true">→</i>' : ""}`
        )
        .join("")}
    </div>
  </div>`;
}

function renderEngineeringCasePillars(d: Details) {
  return `<div class="eng-pillar-grid">
    ${array<Details>(d.pillars)
      .map(
        (pillar, index) => `<div class="eng-pillar-card tone-${index + 1} layout-item">
          <span class="fit-check">${esc(pillar.layer)}</span>
          <strong class="fit-check">${esc(pillar.title)}</strong>
          <p class="fit-check">${esc(pillar.question)}</p>
          <ul>
            ${array(pillar.items).map((item) => `<li class="fit-check">${esc(item)}</li>`).join("")}
          </ul>
        </div>`
      )
      .join("")}
  </div>
  <div class="eng-case-claim layout-item fit-check"><b>真实案例</b>${esc(d.claim)}</div>`;
}

function renderEngineeringCaseRules(d: Details) {
  return `<div class="eng-rules-layout">
    <div class="eng-rules-statement layout-item">
      <strong class="fit-check">${esc(d.statement)}</strong>
      <p class="fit-check">${esc(d.context)}</p>
      <div class="fit-check"><b>持续积累：</b>${esc(d.loop)}</div>
    </div>
    <div class="eng-rule-stack">
      ${array<Details>(d.rules)
        .map(
          (rule, index) => `<div class="eng-rule-row layout-item">
            <span>${String(index + 1).padStart(2, "0")}</span>
            <strong class="fit-check">${esc(rule.name)}</strong>
            <p class="fit-check">${esc(rule.text)}</p>
          </div>`
        )
        .join("")}
    </div>
  </div>`;
}

function renderEngineeringCaseSkills(d: Details) {
  return `<div class="eng-skill-definition layout-item fit-check"><b>Skill不是一条Prompt：</b>${esc(d.definition)}</div>
  <div class="eng-skill-groups">
    ${array<Details>(d.groups)
      .map(
        (group, groupIndex) => `<div class="eng-skill-group ${groupIndex === 1 ? "domain" : ""} layout-item">
          <div class="eng-skill-group-title">
            <strong class="fit-check">${esc(group.title)}</strong>
            <span class="fit-check">${esc(group.label)}</span>
          </div>
          <div class="eng-skill-stack">
            ${array<Details>(group.items)
              .map(
                (item) => `<div class="eng-skill-row">
                  <strong class="fit-check">${esc(item.name)}</strong>
                  <p class="fit-check">${esc(item.text)}</p>
                </div>`
              )
              .join("")}
          </div>
        </div>`
      )
      .join("")}
  </div>
  <div class="eng-skill-outcomes">
    ${array<Details>(d.outcomes)
      .map((item) => `<div class="layout-item"><strong class="fit-check">${esc(item.title)}</strong><span class="fit-check">${esc(item.text)}</span></div>`)
      .join("")}
  </div>`;
}

function renderEngineeringCaseImage(d: Details) {
  return `<div class="eng-evidence-image layout-item">
    <img src="${assetDataUri(String(d.asset))}" alt="${esc(d.alt)}" />
  </div>
  ${d.caption ? `<div class="eng-evidence-caption layout-item fit-check">${esc(d.caption)}</div>` : ""}`;
}

function renderEngineeringCaseArtifacts(d: Details) {
  return `<div class="eng-artifact-flow">
    ${array<Details>(d.artifacts)
      .map(
        (item, index, items) => `<div class="eng-artifact layout-item">
          <span>${String(index + 1).padStart(2, "0")}</span>
          <strong class="fit-check">${esc(item.title)}</strong>
          <p class="fit-check">${esc(item.text)}</p>
        </div>${index < items.length - 1 ? '<i aria-hidden="true">→</i>' : ""}`
      )
      .join("")}
  </div>
  <div class="eng-artifact-evidence">
    ${array<Details>(d.evidence)
      .map((item) => `<div class="layout-item"><strong class="fit-check">${esc(item.title)}</strong><p class="fit-check">${esc(item.text)}</p></div>`)
      .join("")}
  </div>`;
}

function renderEngineeringCaseAccumulation(d: Details) {
  return `<div class="eng-accumulation-layout">
    <div class="eng-asset-list">
      ${array<Details>(d.assets)
        .map(
          (item) => `<div class="eng-asset-line layout-item">
            <strong class="fit-check">${esc(item.value)}</strong>
            <span class="fit-check">${esc(item.text)}</span>
          </div>`
        )
        .join("")}
      <div class="eng-flywheel layout-item fit-check">${esc(d.flywheel)}</div>
    </div>
    <div class="eng-maturity-panel layout-item">
      <div class="eng-maturity-title fit-check">${esc(d.maturity_title)}</div>
      ${array<Details>(d.maturity)
        .map(
          (item, index) => `<div class="eng-maturity-line">
            <span>${String(index + 1).padStart(2, "0")}</span>
            <strong class="fit-check">${esc(item.title)}</strong>
            <p class="fit-check">${esc(item.text)}</p>
          </div>`
        )
        .join("")}
    </div>
  </div>`;
}

function renderWorkspaceComparison(d: Details) {
  const columns = array<string>(d.columns);
  return `<div class="workspace-map">
    <div class="workspace-head">
      <div></div>
      <div class="product fit-check">${esc(columns[0])}</div>
      <div class="shared fit-check">${esc(columns[1])}</div>
      <div class="engineering fit-check">${esc(columns[2])}</div>
    </div>
    ${array<Details>(d.rows)
      .map(
        (row) => `<div class="workspace-row layout-item">
          <div class="row-label fit-check">${esc(row.label)}</div>
          <div class="row-value product fit-check">${esc(row.product)}</div>
          <div class="row-value shared fit-check">${esc(row.shared)}</div>
          <div class="row-value engineering fit-check">${esc(row.engineering)}</div>
        </div>`
      )
      .join("")}
  </div>
  <div class="boundary-line layout-item fit-check">${esc(d.boundary)}</div>`;
}

function renderFlowNode(step: Details, tone: string) {
  return `<div class="flow-node ${tone} layout-item">
    <span>${esc(step.index)}</span>
    <strong class="fit-check">${esc(step.title)}</strong>
    <small class="fit-check">${esc(step.artifact)}</small>
  </div>`;
}

function renderSnakeFlow(d: Details, tone: string) {
  return `<div class="role-line ${tone} layout-item">
    <span>执行主体</span>
    <strong class="fit-check">${esc(d.role)}</strong>
  </div>
  <div class="staged-flow ${tone}">
    <div class="flow-row flow-row-four">
      ${array<Details>(d.first_row)
        .map((step, index, items) => `${renderFlowNode(step, tone)}${index < items.length - 1 ? '<div class="flow-arrow" aria-hidden="true"></div>' : ""}`)
        .join("")}
    </div>
    <div class="flow-gate layout-item">
      <span aria-hidden="true"></span>
      <strong class="fit-check">${esc(d.gate)}</strong>
      <span aria-hidden="true"></span>
    </div>
    <div class="flow-row flow-row-three">
      ${array<Details>(d.second_row)
        .map((step, index, items) => `${renderFlowNode(step, tone)}${index < items.length - 1 ? '<div class="flow-arrow" aria-hidden="true"></div>' : ""}`)
        .join("")}
    </div>
  </div>
  <div class="completion-line ${tone} layout-item fit-check">${esc(d.completion)}</div>`;
}

function renderProductEvidence(d: Details) {
  return `<div class="product-evidence-layout">
    <div class="metric-rail">
      ${array<Details>(d.metrics)
        .map(
          (metric) => `<div class="metric-line layout-item">
            <strong class="fit-check">${esc(metric.value)}</strong>
            <div>
              <b class="fit-check">${esc(metric.label)}</b>
              <span class="fit-check">${esc(metric.note)}</span>
            </div>
          </div>`
        )
        .join("")}
    </div>
    <div class="transformation-list">
      <div class="transformation-label">工作方式发生了什么变化</div>
      ${array<Details>(d.transformations)
        .map(
          (item) => `<div class="transformation layout-item">
            <div class="transform-pair">
              <span class="fit-check">${esc(item.from)}</span>
              <i aria-hidden="true">→</i>
              <strong class="fit-check">${esc(item.to)}</strong>
            </div>
            <p class="fit-check">${esc(item.meaning)}</p>
          </div>`
        )
        .join("")}
    </div>
  </div>
  <div class="boundary-alert layout-item fit-check">${esc(d.boundary)}</div>`;
}

function renderEngineeringEffect(d: Details) {
  const renderColumn = (data: Details, className: string) => `<div class="effect-column ${className} layout-item">
    <strong class="fit-check">${esc(data.title)}</strong>
    ${simpleList(data.items, "effect-list")}
  </div>`;

  return `<div class="effect-pipeline">
    ${renderColumn(d.input ?? {}, "input")}
    <div class="pipeline-arrow" aria-hidden="true"></div>
    ${renderColumn(d.controls ?? {}, "controls")}
    <div class="pipeline-arrow" aria-hidden="true"></div>
    ${renderColumn(d.output ?? {}, "output")}
  </div>
  <div class="effect-meanings">
    ${array(d.effects)
      .map((item, index) => `<div class="meaning-line layout-item"><span>0${index + 1}</span><strong class="fit-check">${esc(item)}</strong></div>`)
      .join("")}
  </div>
  <div class="feedback-split">
    ${array(d.feedback)
      .map((item) => `<span class="fit-check">${esc(item)}</span>`)
      .join("")}
  </div>`;
}

function renderHandoff(d: Details) {
  return `<div class="handoff-layout">
    <div class="handoff-product">
      <div class="column-caption product">产品输出</div>
      ${array<Details>(d.product_groups)
        .map(
          (group) => `<div class="handoff-group layout-item">
            <strong class="fit-check">${esc(group.title)}</strong>
            <span class="fit-check">${array(group.items).map(esc).join(" · ")}</span>
          </div>`
        )
        .join("")}
    </div>
    <div class="handoff-folder layout-item">
      <div class="folder-tab"></div>
      <strong class="fit-check">${esc(d.folder?.title)}</strong>
      ${array(d.folder?.files)
        .map((file) => `<span class="fit-check">${esc(file)}</span>`)
        .join("")}
    </div>
    <div class="handoff-engineering">
      <div class="column-caption engineering">研发转化</div>
      <div class="engineering-steps">
        ${array(d.engineering_steps)
          .map((step, index, items) => `<div class="engineering-step layout-item"><b>${String(index + 1).padStart(2, "0")}</b><span class="fit-check">${esc(step)}</span></div>${index < items.length - 1 ? '<i aria-hidden="true">→</i>' : ""}`)
          .join("")}
      </div>
    </div>
  </div>
  <div class="handoff-feedback">
    ${array<Details>(d.feedback)
      .map(
        (item) => `<div class="feedback-route ${esc(item.tone)} layout-item">
          <strong class="fit-check">${esc(item.label)}</strong>
          <span aria-hidden="true">→</span>
          <p class="fit-check">${esc(item.route)}</p>
        </div>`
      )
      .join("")}
  </div>`;
}

function renderTraceability(d: Details) {
  const gapAfter = new Set(array<number>(d.gap_after));
  const nodes = array<Details>(d.nodes);
  return `<div class="trace-chain">
    ${nodes
      .map(
        (node, index) => `<div class="trace-node ${esc(node.tone)} layout-item fit-check">${esc(node.label)}</div>${
          index < nodes.length - 1 ? `<div class="trace-link ${gapAfter.has(index) ? "gap" : ""}" aria-hidden="true"></div>` : ""
        }`
      )
      .join("")}
  </div>
  <div class="break-grid">
    ${array(d.breaks)
      .map((item, index) => `<div class="break-item layout-item"><span>0${index + 1}</span><p class="fit-check">${esc(item)}</p></div>`)
      .join("")}
  </div>
  <div class="outcome-line">
    ${array(d.outcome)
      .map((item, index) => `<span class="${index === 2 ? "negative" : "positive"} fit-check">${esc(item)}</span>`)
      .join("")}
  </div>`;
}

function renderTargetState(d: Details) {
  const active = Number(d.active_status ?? 0);
  return `<div class="identity-bar">
    ${array<Details>(d.identity)
      .map((item) => `<div class="identity-field layout-item"><span class="fit-check">${esc(item.label)}</span><strong class="fit-check">${esc(item.value)}</strong></div>`)
      .join("")}
  </div>
  <div class="status-rail">
    ${array(d.statuses)
      .map(
        (status, index) => `<div class="status-step ${index < active ? "done" : index === active ? "active" : ""} layout-item">
          <i>${String(index + 1).padStart(2, "0")}</i>
          <span class="fit-check">${esc(status)}</span>
        </div>`
      )
      .join("")}
  </div>
  <div class="asset-lanes">
    ${array<Details>(d.asset_lanes)
      .map(
        (lane) => `<div class="asset-lane ${esc(lane.tone)} layout-item">
          <strong class="fit-check">${esc(lane.title)}</strong>
          <div>${array(lane.items)
            .map((item) => `<span>${esc(item)}</span>`)
            .join("")}</div>
        </div>`
      )
      .join("")}
  </div>
  <div class="target-summary layout-item fit-check">${esc(d.summary)}</div>`;
}

function renderUnifiedSpecTarget(d: Details) {
  const product = (d.product ?? {}) as Details;
  const spec = (d.spec ?? {}) as Details;
  const engineering = (d.engineering ?? {}) as Details;
  const renderStages = (stages: unknown, tone: string) =>
    array(stages)
      .map(
        (stage, index) => `<div class="unified-stage ${tone} layout-item">
          <span>${String(index + 1).padStart(2, "0")}</span>
          <strong class="fit-check">${esc(stage)}</strong>
        </div>`
      )
      .join("");

  return `<div class="unified-spec-layout">
    <div class="unified-spec-main">
      <section class="unified-side product">
        <div class="unified-side-head">
          <span>${esc(product.eyebrow)}</span>
          <strong class="fit-check">${esc(product.title)}</strong>
          <p class="fit-check">${esc(product.subtitle)}</p>
        </div>
        <div class="unified-stage-grid">${renderStages(product.stages, "product")}</div>
        <div class="unified-responsibility fit-check">${esc(product.responsibility)}</div>
      </section>
      <div class="unified-forward product-to-spec" aria-hidden="true"><span>→</span><small>交付</small></div>
      <section class="unified-core">
        <div class="unified-core-eyebrow fit-check">${esc(spec.eyebrow)}</div>
        <strong class="unified-core-title fit-check">${esc(spec.title)}</strong>
        <p class="unified-core-subtitle fit-check">${esc(spec.subtitle)}</p>
        <div class="unified-artifacts">
          ${array(spec.artifacts)
            .map((item) => `<span class="layout-item fit-check">${esc(item)}</span>`)
            .join("")}
        </div>
        <div class="unified-identity fit-check">${esc(spec.identity)}</div>
      </section>
      <div class="unified-forward spec-to-engineering" aria-hidden="true"><span>→</span><small>驱动</small></div>
      <section class="unified-side engineering">
        <div class="unified-side-head">
          <span>${esc(engineering.eyebrow)}</span>
          <strong class="fit-check">${esc(engineering.title)}</strong>
          <p class="fit-check">${esc(engineering.subtitle)}</p>
        </div>
        <div class="unified-stage-grid">${renderStages(engineering.stages, "engineering")}</div>
        <div class="unified-responsibility fit-check">${esc(engineering.responsibility)}</div>
      </section>
    </div>
    <div class="unified-feedback layout-item">
      <span class="feedback-loop" aria-hidden="true">↶</span>
      <strong>验证回填</strong>
      <p class="fit-check">${esc(d.feedback)}</p>
    </div>
    <div class="unified-conclusion layout-item fit-check">${esc(d.conclusion)}</div>
  </div>`;
}

function renderNextStagePlan(d: Details) {
  const startingPoint = (d.starting_point ?? {}) as Details;
  return `<div class="improvement-plan-layout">
    <div class="improvement-plan-start">
      <div class="improvement-plan-start-label fit-check">${esc(startingPoint.label)}</div>
      <div class="improvement-plan-current-flow">
        ${array(startingPoint.flow)
          .map(
            (item, index, items) =>
              `<span class="layout-item fit-check">${esc(item)}</span>${index < items.length - 1 ? '<i aria-hidden="true">→</i>' : ""}`
          )
          .join("")}
      </div>
      <div class="improvement-plan-issues">
        ${array(startingPoint.issues)
          .map((item) => `<span class="fit-check">${esc(item)}</span>`)
          .join("")}
      </div>
    </div>
    <div class="improvement-plan-tracks">
      ${array<Details>(d.tracks)
        .map(
          (track) => `<article class="improvement-plan-track ${esc(track.tone)} layout-item">
            <div class="improvement-plan-track-head">
              <span>${esc(track.index)}</span>
              <div>
                <strong class="fit-check">${esc(track.title)}</strong>
                <p class="fit-check">${esc(track.goal)}</p>
              </div>
            </div>
            <div class="improvement-plan-modules">
              ${array<Details>(track.modules)
                .map(
                  (item) => `<div class="improvement-plan-module">
                    <strong class="fit-check">${esc(item.title)}</strong>
                    <p class="fit-check">${esc(item.detail)}</p>
                  </div>`
                )
                .join("")}
            </div>
            <div class="improvement-plan-track-output">
              <small>阶段产出</small>
              <strong class="fit-check">${esc(track.deliverable)}</strong>
            </div>
          </article>`
        )
        .join("")}
    </div>
    <div class="improvement-plan-roadmap">
      <div class="improvement-plan-roadmap-label">推进路径</div>
      ${array<Details>(d.roadmap)
        .map(
          (item, index, items) => `<div class="improvement-plan-roadmap-step layout-item">
            <small class="fit-check">${esc(item.phase)}</small>
            <strong class="fit-check">${esc(item.title)}</strong>
            <p class="fit-check">${esc(item.detail)}</p>
          </div>${index < items.length - 1 ? '<i aria-hidden="true">→</i>' : ""}`
        )
        .join("")}
    </div>
    <div class="improvement-plan-conclusion layout-item fit-check">${esc(d.conclusion)}</div>
  </div>`;
}

function renderSwimlane(d: Details) {
  const phases = array(d.phases);
  return `<div class="swimlane-wrap">
    <div class="swimlane-grid" style="--phase-count:${phases.length}">
      <div class="swim-corner">角色 / 阶段</div>
      ${phases.map((phase) => `<div class="phase-head fit-check">${esc(phase)}</div>`).join("")}
      ${array<Details>(d.lanes)
        .map(
          (lane) => `<div class="lane-role ${esc(lane.tone)} fit-check">${esc(lane.role)}</div>
          ${array(lane.cells)
            .map((cell) => `<div class="lane-cell ${esc(lane.tone)} layout-item fit-check">${esc(cell)}</div>`)
            .join("")}`
        )
        .join("")}
    </div>
    <div class="gate-row">
      ${array<Details>(d.gates)
        .map((gate) => `<span class="fit-check" style="--gate-after:${Number(gate.after)}">${esc(gate.label)}</span>`)
        .join("")}
    </div>
  </div>
  <div class="swim-feedback">
    ${array(d.feedback)
      .map((item) => `<span class="fit-check">${esc(item)}</span>`)
      .join("")}
  </div>`;
}

function renderBuildAssets(d: Details) {
  const renderTree = (tree: Details, tone: string) => `<div class="asset-tree ${tone} layout-item">
    <strong class="fit-check">${esc(tree.title)}</strong>
    ${array(tree.files)
      .map((file, index, items) => `<div class="tree-file fit-check">${index === items.length - 1 ? "└─" : "├─"} ${esc(file)}</div>`)
      .join("")}
  </div>`;

  return `<div class="control-plane layout-item">
    <strong>共同控制面</strong>
    ${array(d.control_fields)
      .map((field) => `<span class="fit-check">${esc(field)}</span>`)
      .join("")}
  </div>
  <div class="asset-space">
    ${renderTree(d.product ?? {}, "product")}
    <div class="shared-assets">
      ${array<Details>(d.shared)
        .map((item) => `<div class="shared-file layout-item"><strong class="fit-check">${esc(item.name)}</strong><span class="fit-check">${esc(item.meaning)}</span></div>`)
        .join("")}
    </div>
    ${renderTree(d.engineering ?? {}, "engineering")}
  </div>
  <div class="capability-layer layout-item">
    <strong>可复用能力层</strong>
    ${array(d.capabilities)
      .map((item) => `<span class="fit-check">${esc(item)}</span>`)
      .join("")}
  </div>
  <div class="build-summary fit-check">${esc(d.summary)}</div>`;
}

function renderCompletion(d: Details) {
  return `<div class="scope-note layout-item fit-check">${esc(d.scope)}</div>
  <div class="completion-layout">
    <div class="milestone-path">
      ${array(d.milestones)
        .map(
          (item, index, items) => `<div class="milestone layout-item">
            <span>${String(index + 1).padStart(2, "0")}</span>
            <strong class="fit-check">${esc(item)}</strong>
          </div>${index < items.length - 1 ? '<div class="milestone-link" aria-hidden="true"></div>' : ""}`
        )
        .join("")}
    </div>
    <div class="criteria-list">
      <div class="criteria-title">完成必须同时满足</div>
      ${array(d.criteria)
        .map((item) => `<div class="criterion layout-item"><i>✓</i><span class="fit-check">${esc(item)}</span></div>`)
        .join("")}
    </div>
  </div>
  <div class="decision-outcomes">
    ${array<Details>(d.outcomes)
      .map((item, index) => `<div class="decision ${index === 0 ? "pass" : index === 1 ? "adjust" : "stop"} layout-item"><strong class="fit-check">${esc(item.status)}</strong><span class="fit-check">${esc(item.action)}</span></div>`)
      .join("")}
  </div>
  <div class="closing-line fit-check">${esc(d.closing)}</div>`;
}

function renderGeneric(slide: Slide) {
  return `<div class="generic-layout">${slide.points
    .map((point, index) => `<div class="generic-point layout-item"><span>0${index + 1}</span><strong class="fit-check">${esc(point)}</strong></div>`)
    .join("")}</div>`;
}

function renderBody(slide: Slide) {
  const d = (slide.details ?? {}) as Details;
  switch (slide.layout) {
    case "cover-dual-engine":
      return renderCover(slide);
    case "application-section":
      return renderApplicationSection(d, slide);
    case "vibe-to-sdd-overview":
      return renderVibeToSddOverview(d);
    case "sdd-tools-table":
      return renderSddToolsTable(d);
    case "one-line-ai-gap":
      return renderOneLineAiGap(d);
    case "sdd-mode-shift":
      return renderSddModeShift(d);
    case "dual-loops":
      return renderDualLoops(d);
    case "integrated-collaboration":
      return renderIntegratedCollaboration(d);
    case "product-agent-operating-model":
      return renderProductAgentOperatingModel(d);
    case "project-framework-map":
      return renderProjectFrameworkMap(d);
    case "practice-sop-map":
      return renderPracticeSopMap(d);
    case "evidence-requirement-table":
      return renderEvidenceRequirementTable(d);
    case "speckit-to-demo":
      return renderSpeckitToDemo(d);
    case "validation-feedback-delivery":
      return renderValidationFeedbackDelivery(d);
    case "skill-capability-stack":
      return renderSkillCapabilityStack(d);
    case "pm-minimal-input":
      return renderPmMinimalInput(d);
    case "quadrant-collaboration":
      return renderQuadrantCollaboration(d);
    case "engineering-case-pillars":
      return renderEngineeringCasePillars(d);
    case "engineering-case-rules":
      return renderEngineeringCaseRules(d);
    case "engineering-case-skills":
      return renderEngineeringCaseSkills(d);
    case "engineering-case-image":
    case "engineering-case-image-focus":
      return renderEngineeringCaseImage(d);
    case "engineering-case-artifacts":
      return renderEngineeringCaseArtifacts(d);
    case "engineering-case-accumulation":
      return renderEngineeringCaseAccumulation(d);
    case "workspace-comparison":
      return renderWorkspaceComparison(d);
    case "snake-flow-product":
      return renderSnakeFlow(d, "product");
    case "product-evidence":
      return renderProductEvidence(d);
    case "snake-flow-engineering":
      return renderSnakeFlow(d, "engineering");
    case "engineering-effect":
      return renderEngineeringEffect(d);
    case "handoff-package":
      return renderHandoff(d);
    case "traceability-gaps":
      return renderTraceability(d);
    case "target-state":
      return renderTargetState(d);
    case "unified-spec-target":
      return renderUnifiedSpecTarget(d);
    case "next-stage-plan":
      return renderNextStagePlan(d);
    case "operating-swimlane":
      return renderSwimlane(d);
    case "build-assets":
      return renderBuildAssets(d);
    case "completion-standard":
      return renderCompletion(d);
    default:
      return renderGeneric(slide);
  }
}

const slides = spec.slides
  .map((slide, index) => {
    const isCover = slide.layout === "cover-dual-engine";
    const isChapter = slide.layout === "application-section";
    const isImageFocus = slide.layout === "engineering-case-image-focus";
    const isClosing = slide.layout === "completion-standard";
    const shell = isCover || isChapter
      ? renderBody(slide)
      : isImageFocus
        ? `<header class="engineering-image-focus-header">
            <h1 class="fit-check">${esc(slide.title)}</h1>
          </header>
          <div class="engineering-image-focus-main">${renderBody(slide)}</div>`
      : `<header class="slide-header">
          <h1 class="fit-check">${esc(slide.title)}</h1>
          <p class="slide-message fit-check">${esc(slide.message)}</p>
        </header>
        <div class="slide-main">${renderBody(slide)}</div>`;
    return `<section class="slide tone-${toneFor(slide)} ${isCover ? "cover" : ""} ${isChapter ? "application-section-slide" : ""} ${isImageFocus ? "engineering-image-focus-slide" : ""} ${isClosing ? "closing" : ""}${index === 0 ? " active" : ""}" data-page="${slide.page}" data-layout="${esc(slide.layout ?? "generic")}" aria-hidden="${index === 0 ? "false" : "true"}">
      <div class="page-grid" aria-hidden="true"></div>
      <div class="accent-bar" aria-hidden="true"></div>
      ${shell}
      <footer><b>${String(slide.page).padStart(2, "0")}</b></footer>
    </section>`;
  })
  .join("\n");

const html = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${esc(spec.deck.title)}</title>
  <style>
    :root {
      --scale: 1;
      --navy: #071827;
      --navy-2: #0d273b;
      --ink: #10263b;
      --muted: #607287;
      --paper: #f4f7f9;
      --white: #ffffff;
      --line: #d7e1e8;
      --product: #2d67d5;
      --product-soft: #e6eefc;
      --engineering: #0d9386;
      --engineering-soft: #dff2ee;
      --shared: #f0a13b;
      --shared-soft: #fff1dd;
      --danger: #d95b4e;
      --danger-soft: #fce8e5;
      --future: #6758d6;
      --future-soft: #ece9fb;
    }
    * { box-sizing: border-box; }
    html, body { width: 100%; height: 100%; }
    body {
      margin: 0;
      overflow: hidden;
      background: #020a11;
      color: var(--ink);
      font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", Arial, sans-serif;
      -webkit-font-smoothing: antialiased;
    }
    .deck {
      position: relative;
      width: 100vw;
      height: 100vh;
      overflow: hidden;
      background:
        radial-gradient(circle at 14% 24%, rgba(45, 103, 213, .16), transparent 28%),
        radial-gradient(circle at 84% 74%, rgba(13, 147, 134, .14), transparent 30%),
        #020a11;
    }
    .slide {
      position: absolute;
      left: 50%;
      top: 50%;
      width: 1280px;
      height: 720px;
      padding: 42px 64px 44px;
      overflow: hidden;
      page-break-after: always;
      background: var(--paper);
      opacity: 0;
      visibility: hidden;
      pointer-events: none;
      transform: translate(-50%, -48%) scale(calc(var(--scale) * .975));
      transition: opacity .28s ease, transform .36s cubic-bezier(.2,.8,.2,1), visibility .28s;
      box-shadow: 0 34px 100px rgba(0,0,0,.36);
    }
    .slide.active {
      opacity: 1;
      visibility: visible;
      pointer-events: auto;
      transform: translate(-50%, -50%) scale(var(--scale));
    }
    .page-grid {
      position: absolute;
      inset: 0;
      opacity: .3;
      background-image:
        linear-gradient(rgba(16,38,59,.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(16,38,59,.035) 1px, transparent 1px);
      background-size: 56px 56px;
      mask-image: linear-gradient(90deg, transparent, black 22%, black 100%);
    }
    .accent-bar {
      position: absolute;
      left: 0;
      top: 0;
      width: 10px;
      height: 100%;
      background: var(--shared);
    }
    .tone-product .accent-bar { background: var(--product); }
    .tone-engineering .accent-bar { background: var(--engineering); }
    .tone-shared .accent-bar { background: linear-gradient(180deg, var(--product), var(--shared), var(--engineering)); }
    .tone-future .accent-bar { background: linear-gradient(180deg, var(--future), var(--shared)); }
    .slide-header {
      position: relative;
      z-index: 2;
      height: 106px;
    }
    .section-label {
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1;
      font-weight: 800;
      letter-spacing: 1.8px;
    }
    .tone-product .section-label { color: var(--product); }
    .tone-engineering .section-label { color: var(--engineering); }
    .tone-shared .section-label { color: #bb6b0d; }
    .tone-future .section-label { color: var(--future); }
    h1 {
      width: 1110px;
      margin: 0;
      color: var(--ink);
      font-size: 46px;
      line-height: 1.08;
      font-weight: 850;
      letter-spacing: -.8px;
      white-space: nowrap;
    }
    .slide-message {
      width: 1110px;
      margin: 10px 0 0;
      color: var(--muted);
      font-size: 21px;
      line-height: 1.35;
      font-weight: 550;
      white-space: nowrap;
    }
    .slide-main {
      position: relative;
      z-index: 2;
      width: 1152px;
      height: 490px;
    }
    .evidence-label {
      position: absolute;
      left: 64px;
      bottom: 19px;
      z-index: 3;
      max-width: 700px;
      color: #7d8b99;
      font-size: 13px;
      font-weight: 650;
      white-space: nowrap;
    }
    footer {
      position: absolute;
      right: 60px;
      bottom: 17px;
      z-index: 3;
      display: flex;
      align-items: center;
      gap: 18px;
      color: #84919d;
      font-size: 12px;
      font-weight: 700;
    }
    footer b { color: var(--ink); font-size: 15px; }

    /* Application section transitions */
    .application-section-slide {
      padding: 0;
      background:
        radial-gradient(circle at 82% 26%, rgba(45,103,213,.12), transparent 28%),
        linear-gradient(128deg, #f9fbfd 0%, #f3f7fc 58%, #edf4fb 100%);
    }
    .application-section-slide.tone-engineering {
      background:
        radial-gradient(circle at 82% 26%, rgba(13,147,134,.13), transparent 29%),
        linear-gradient(128deg, #f9fbfd 0%, #f2f9f8 58%, #eaf5f3 100%);
    }
    .application-section-slide.tone-future {
      background:
        radial-gradient(circle at 82% 26%, rgba(103,85,217,.14), transparent 30%),
        linear-gradient(128deg, #fbfafd 0%, #f5f2fb 58%, #efebf8 100%);
    }
    .application-section-slide .page-grid {
      opacity: .52;
      mask-image: linear-gradient(90deg, black, black 100%);
    }
    .application-section-slide .accent-bar {
      width: 14px;
    }
    .application-section-layout {
      position: relative;
      z-index: 2;
      width: 100%;
      height: 100%;
      padding: 92px 86px 76px 102px;
      overflow: hidden;
    }
    .application-section-copy {
      position: relative;
      z-index: 3;
      width: 760px;
    }
    .application-section-kicker {
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      margin-bottom: 24px;
      color: var(--product);
      font-size: 15px;
      line-height: 1;
      font-weight: 850;
      letter-spacing: 2.4px;
    }
    .application-section-engineering .application-section-kicker {
      color: var(--engineering);
    }
    .application-section-future .application-section-kicker {
      color: var(--future);
    }
    .application-section-future .application-section-copy {
      width: 900px;
    }
    .application-section-copy h1 {
      width: auto;
      color: var(--ink);
      font-size: 76px;
      line-height: 1;
      font-weight: 900;
      letter-spacing: -2px;
    }
    .application-section-subtitle {
      margin-top: 18px;
      color: #355778;
      font-size: 31px;
      line-height: 1.2;
      font-weight: 750;
    }
    .application-section-engineering .application-section-subtitle {
      color: #176e66;
    }
    .application-section-future .application-section-copy h1 {
      font-size: 68px;
      letter-spacing: -1.5px;
    }
    .application-section-future .application-section-subtitle {
      color: #58479e;
    }
    .application-section-statement {
      width: 910px;
      margin: 34px 0 0;
      color: #5c7083;
      font-size: 20px;
      line-height: 1.55;
      font-weight: 560;
    }
    .application-section-index {
      position: absolute;
      top: 56px;
      right: 56px;
      z-index: 1;
      color: rgba(45,103,213,.085);
      font-size: 250px;
      line-height: 1;
      font-weight: 900;
      letter-spacing: -18px;
    }
    .application-section-engineering .application-section-index {
      color: rgba(13,147,134,.09);
    }
    .application-section-future .application-section-index {
      color: rgba(103,85,217,.09);
    }
    .application-section-orbit {
      position: absolute;
      top: 76px;
      right: 88px;
      width: 318px;
      height: 318px;
      border: 1px solid rgba(45,103,213,.18);
      border-radius: 50%;
    }
    .application-section-orbit::before,
    .application-section-orbit::after {
      content: "";
      position: absolute;
      border-radius: 50%;
    }
    .application-section-orbit::before {
      inset: 44px;
      border: 1px solid rgba(45,103,213,.16);
    }
    .application-section-orbit::after {
      top: 50%;
      left: 50%;
      width: 12px;
      height: 12px;
      margin: -6px 0 0 -6px;
      background: var(--product);
      box-shadow: 0 0 0 12px rgba(45,103,213,.08);
    }
    .application-section-engineering .application-section-orbit,
    .application-section-engineering .application-section-orbit::before {
      border-color: rgba(13,147,134,.18);
    }
    .application-section-engineering .application-section-orbit::after {
      background: var(--engineering);
      box-shadow: 0 0 0 12px rgba(13,147,134,.08);
    }
    .application-section-future .application-section-orbit,
    .application-section-future .application-section-orbit::before {
      border-color: rgba(103,85,217,.18);
    }
    .application-section-future .application-section-orbit::after {
      background: var(--future);
      box-shadow: 0 0 0 12px rgba(103,85,217,.08);
    }
    .application-section-flow {
      position: absolute;
      left: 102px;
      right: 86px;
      bottom: 86px;
      z-index: 3;
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 18px 20px;
      border-top: 2px solid rgba(45,103,213,.55);
      background: rgba(255,255,255,.66);
      box-shadow: 0 14px 38px rgba(16,38,59,.06);
      backdrop-filter: blur(4px);
    }
    .application-section-engineering .application-section-flow {
      border-top-color: rgba(13,147,134,.62);
    }
    .application-section-future .application-section-flow {
      border-top-color: rgba(103,85,217,.62);
    }
    .application-section-stage {
      display: grid;
      grid-template-columns: 30px auto;
      align-items: center;
      min-width: 0;
      flex: 1 1 0;
      gap: 10px;
      padding: 9px 12px;
    }
    .application-section-stage span {
      color: var(--product);
      font-size: 12px;
      font-weight: 850;
      letter-spacing: .5px;
    }
    .application-section-engineering .application-section-stage span {
      color: var(--engineering);
    }
    .application-section-future .application-section-stage span {
      color: var(--future);
    }
    .application-section-stage strong {
      min-width: 0;
      color: var(--ink);
      font-size: 17px;
      line-height: 1.2;
      font-weight: 760;
      white-space: nowrap;
    }
    .application-section-flow > i {
      width: 26px;
      height: 1px;
      flex: 0 0 26px;
      background: #9eb3c5;
      position: relative;
    }
    .application-section-flow > i::after {
      content: "";
      position: absolute;
      right: -1px;
      top: -4px;
      border-top: 4px solid transparent;
      border-bottom: 4px solid transparent;
      border-left: 6px solid #9eb3c5;
    }
    .application-section-slide footer {
      color: #7c8fa0;
    }
    .application-section-slide footer b {
      color: var(--ink);
    }

    /* Cover */
    .cover {
      padding: 0;
      color: var(--white);
      background:
        radial-gradient(circle at 82% 12%, rgba(13,147,134,.2), transparent 32%),
        radial-gradient(circle at 58% 92%, rgba(45,103,213,.18), transparent 34%),
        linear-gradient(125deg, #061421, #0b2337);
    }
    .cover .page-grid {
      opacity: .55;
      background-image:
        linear-gradient(rgba(255,255,255,.045) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.045) 1px, transparent 1px);
      mask-image: none;
    }
    .cover .accent-bar { width: 13px; background: linear-gradient(180deg, var(--shared), var(--engineering)); }
    .cover-layout {
      position: relative;
      z-index: 2;
      display: grid;
      grid-template-columns: 46% 54%;
      width: 100%;
      height: 100%;
      padding: 86px 70px 74px 82px;
    }
    .cover-copy { display: flex; flex-direction: column; justify-content: center; padding-right: 28px; }
    .cover-kicker {
      margin-bottom: 28px;
      color: #8ddfd6;
      font-size: 15px;
      font-weight: 800;
      letter-spacing: 2px;
    }
    .cover h1 {
      width: 570px;
      color: var(--white);
      font-size: 68px;
      line-height: 1.08;
      white-space: normal;
    }
    .cover-message {
      width: 520px;
      margin: 26px 0 30px;
      color: #c5d2dd;
      font-size: 27px;
      line-height: 1.45;
    }
    .cover-tags { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 34px; }
    .cover-tags span {
      padding: 10px 14px;
      border-left: 3px solid var(--shared);
      background: rgba(255,255,255,.07);
      color: #eff5f8;
      font-size: 17px;
      font-weight: 700;
      white-space: nowrap;
    }
    .cover-visual {
      position: relative;
      display: grid;
      grid-template-columns: 1fr 126px 1fr;
      align-items: center;
      gap: 0;
    }
    .engine {
      position: relative;
      height: 388px;
      padding: 26px 18px;
      border: 1px solid rgba(255,255,255,.13);
      background: rgba(255,255,255,.04);
    }
    .engine-product { border-top: 5px solid #5f91f3; }
    .engine-engineering { border-top: 5px solid #50cabc; }
    .engine-head strong { display: block; color: var(--white); font-size: 24px; }
    .engine-head span { display: block; margin-top: 6px; color: #9cb0bf; font-size: 15px; }
    .engine-loop {
      position: relative;
      display: grid;
      grid-template-columns: 94px 94px;
      grid-template-rows: 52px 52px;
      justify-content: space-between;
      align-content: space-between;
      height: 222px;
      margin-top: 35px;
      padding: 18px 0 16px;
    }
    .engine-loop-arrows {
      position: absolute;
      inset: -4px -10px -6px;
      z-index: 1;
      width: calc(100% + 20px);
      height: calc(100% + 10px);
      overflow: visible;
      pointer-events: none;
    }
    .engine-loop-arrows path {
      fill: none;
      stroke: rgba(255,255,255,.34);
      stroke-width: 2;
      vector-effect: non-scaling-stroke;
    }
    .engine-loop-arrows > path {
      marker-end: url(#engine-arrow-product);
    }
    .engine-engineering .engine-loop-arrows > path {
      marker-end: url(#engine-arrow-engineering);
    }
    .engine-product .engine-loop-arrows marker path {
      fill: #79a5ff;
    }
    .engine-engineering .engine-loop-arrows marker path {
      fill: #66d8cb;
    }
    .engine-product .engine-loop-arrows > path {
      stroke: rgba(121,165,255,.72);
    }
    .engine-engineering .engine-loop-arrows > path {
      stroke: rgba(102,216,203,.72);
    }
    .engine-node {
      position: relative;
      z-index: 2;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 52px;
      padding: 12px 8px;
      border: 1px solid rgba(255,255,255,.15);
      background: #102a40;
      color: #f2f6f8;
      font-size: 17px;
      font-weight: 700;
      text-align: center;
      white-space: nowrap;
    }
    .engine-node[data-index="1"] { grid-column: 1; grid-row: 1; }
    .engine-node[data-index="2"] { grid-column: 2; grid-row: 1; }
    .engine-node[data-index="3"] { grid-column: 2; grid-row: 2; }
    .engine-node[data-index="4"] { grid-column: 1; grid-row: 2; }
    .engine-product .engine-node { box-shadow: inset 0 0 0 1px rgba(95,145,243,.16); }
    .engine-engineering .engine-node { box-shadow: inset 0 0 0 1px rgba(80,202,188,.16); }
    .engine-core {
      position: absolute;
      left: 50%;
      top: 50%;
      z-index: 1;
      width: 64px;
      height: 64px;
      transform: translate(-50%, -50%);
      border-radius: 50%;
      background: linear-gradient(135deg, rgba(45,103,213,.9), rgba(13,147,134,.9));
      color: white;
      font-size: 20px;
      font-weight: 850;
      line-height: 64px;
      text-align: center;
    }
    .cover-bridge {
      position: relative;
      z-index: 4;
      display: flex;
      flex-direction: column;
      align-items: center;
      align-self: center;
      width: 126px;
      margin: 0 -1px;
    }
    .bridge-role-row {
      display: flex;
      justify-content: space-between;
      width: 100%;
      margin-bottom: 8px;
      color: #ffd798;
      font-size: 10px;
      font-weight: 800;
      white-space: nowrap;
    }
    .bridge-arrow {
      position: relative;
      width: 100%;
      height: 2px;
      background: linear-gradient(90deg, #5f91f3, var(--shared) 46%, #50cabc);
    }
    .bridge-arrow::after {
      content: "";
      position: absolute;
      right: -1px;
      top: 50%;
      transform: translateY(-50%);
      border-left: 9px solid #50cabc;
      border-top: 6px solid transparent;
      border-bottom: 6px solid transparent;
    }
    .bridge-drop {
      width: 1px;
      height: 16px;
      background: rgba(240,161,59,.78);
    }
    .bridge-file {
      width: 104px;
      padding: 9px 8px 10px;
      border: 1px solid rgba(240,161,59,.75);
      background: rgba(240,161,59,.13);
      text-align: center;
    }
    .bridge-file small {
      display: block;
      margin-bottom: 3px;
      color: #c5ad84;
      font-size: 9px;
      font-weight: 750;
      letter-spacing: .8px;
      white-space: nowrap;
    }
    .bridge-file strong {
      display: block;
      color: #ffd798;
      font-size: 14px;
      font-weight: 850;
      white-space: nowrap;
    }
    .cover .evidence-label, .cover footer { color: #8297a8; }
    .cover footer b { color: #b7c5d0; }

    /* Pages 2-3: Vibe Coding to SDD and current SDD tool choices */
    .vibe-sdd-layout {
      display: grid;
      grid-template-columns: minmax(0, .92fr) 116px minmax(0, 1.08fr);
      gap: 14px;
      height: 342px;
      padding-top: 7px;
    }
    .vibe-panel,
    .sdd-definition-panel {
      min-width: 0;
      overflow: hidden;
      border-top: 5px solid var(--danger);
      background: rgba(255,255,255,.92);
      box-shadow: 0 8px 24px rgba(15,38,58,.05);
    }
    .sdd-definition-panel { border-top-color: var(--engineering); }
    .vibe-panel-title,
    .sdd-definition-title {
      display: flex;
      align-items: center;
      height: 46px;
      padding: 0 18px;
      color: var(--danger);
      font-size: 18px;
      font-weight: 850;
    }
    .sdd-definition-title { color: var(--engineering); }
    .vibe-flow {
      display: grid;
      grid-template-columns: 1fr 22px 1fr 22px 1fr;
      align-items: center;
      gap: 3px;
      padding: 0 18px 14px;
    }
    .vibe-flow-node {
      display: flex;
      align-items: center;
      justify-content: center;
      min-width: 0;
      height: 54px;
      padding: 0 8px;
      border: 1px solid #efc4bf;
      background: var(--danger-soft);
      color: #96362c;
      font-size: 11px;
      font-weight: 800;
      text-align: center;
    }
    .vibe-flow i {
      color: #a6b7c5;
      font-size: 18px;
      font-style: normal;
      text-align: center;
    }
    .vibe-pain-title {
      display: flex;
      align-items: center;
      height: 34px;
      padding: 0 18px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 12px;
      font-weight: 850;
    }
    .vibe-pain-list {
      display: grid;
      gap: 7px;
      padding: 4px 18px 14px;
    }
    .vibe-pain-list div {
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
      min-height: 43px;
      padding: 0 12px;
      border-left: 3px solid var(--danger);
      background: #faf5f4;
    }
    .vibe-pain-list span {
      color: var(--danger);
      font-size: 9px;
      font-weight: 850;
    }
    .vibe-pain-list strong {
      color: var(--ink);
      font-size: 12px;
    }
    .vibe-decision {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      color: #8a9dad;
    }
    .vibe-decision span {
      font-size: 11px;
      font-weight: 800;
    }
    .vibe-decision i {
      color: var(--engineering);
      font-size: 40px;
      font-style: normal;
      line-height: 1.1;
    }
    .vibe-decision strong {
      color: var(--engineering);
      font-size: 28px;
      font-weight: 900;
    }
    .sdd-definition-quote {
      margin: 0 18px 14px;
      padding: 14px 16px;
      border-left: 5px solid var(--engineering);
      background: var(--engineering-soft);
      color: #155e57;
      font-size: 13px;
      font-weight: 750;
      line-height: 1.55;
    }
    .sdd-principles {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      align-items: center;
      gap: 8px;
      padding: 0 18px 16px;
    }
    .sdd-principle {
      min-width: 0;
      min-height: 128px;
      padding: 12px 11px;
      border: 1px solid var(--line);
      background: #f8fafb;
    }
    .sdd-principle span {
      color: var(--engineering);
      font-size: 9px;
      font-weight: 850;
    }
    .sdd-principle strong {
      display: block;
      margin: 8px 0 7px;
      color: var(--ink);
      font-size: 14px;
    }
    .sdd-principle p {
      margin: 0;
      color: var(--muted);
      font-size: 10px;
      line-height: 1.45;
    }
    .vibe-sdd-summary {
      display: flex;
      align-items: center;
      height: 64px;
      margin-top: 16px;
      padding: 0 22px;
      border-left: 5px solid var(--engineering);
      background: linear-gradient(90deg, var(--engineering-soft), var(--product-soft));
      color: #08766b;
      font-size: 16px;
      font-weight: 850;
      white-space: nowrap;
    }
    .sdd-tools-wrap {
      display: grid;
      grid-template-rows: 292px 96px;
      gap: 14px;
      padding-top: 7px;
    }
    .sdd-tools-table {
      width: 100%;
      height: 292px;
      table-layout: fixed;
      border-collapse: collapse;
      background: rgba(255,255,255,.92);
      box-shadow: 0 8px 24px rgba(15,38,58,.05);
    }
    .sdd-tools-table th,
    .sdd-tools-table td {
      padding: 7px 10px;
      border: 1px solid var(--line);
      color: var(--ink);
      font-size: 10px;
      line-height: 1.35;
      vertical-align: middle;
    }
    .sdd-tools-table th {
      height: 39px;
      background: var(--ink);
      color: white;
      font-size: 12px;
      font-weight: 850;
      text-align: left;
    }
    .sdd-tools-table th:first-child,
    .sdd-tools-table td:first-child {
      width: 13%;
      color: var(--muted);
      font-weight: 850;
    }
    .sdd-tools-table th:first-child { color: white; }
    .sdd-tools-table th:nth-child(2) { border-top: 5px solid var(--product); }
    .sdd-tools-table th:nth-child(3) { border-top: 5px solid var(--engineering); }
    .sdd-tools-table th:nth-child(4) { border-top: 5px solid var(--future); }
    .sdd-tools-table td:not(:first-child) { width: 29%; }
    .sdd-tools-table tbody tr:nth-child(even) td { background: #f8fafb; }
    .sdd-tool-selections {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }
    .sdd-tool-selection {
      display: grid;
      grid-template-columns: 72px 112px minmax(0, 1fr);
      align-items: center;
      min-width: 0;
      padding: 12px 16px;
      border-left: 5px solid var(--product);
      background: var(--product-soft);
    }
    .sdd-tool-selection.engineering {
      border-left-color: var(--engineering);
      background: var(--engineering-soft);
    }
    .sdd-tool-selection span {
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
    }
    .sdd-tool-selection strong {
      color: var(--product);
      font-size: 18px;
    }
    .sdd-tool-selection.engineering strong { color: var(--engineering); }
    .sdd-tool-selection p {
      margin: 0;
      padding-left: 14px;
      border-left: 1px solid rgba(96,114,135,.25);
      color: var(--ink);
      font-size: 10px;
      line-height: 1.45;
    }

    /* Previous experimental layouts retained for compatibility */
    .one-line-layout {
      display: grid;
      grid-template-rows: 150px 32px 114px;
      gap: 10px;
      padding-top: 7px;
    }
    .one-line-lanes {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
    }
    .one-line-lane {
      position: relative;
      min-width: 0;
      padding: 17px 18px 18px;
      border-top: 5px solid var(--product);
      background: rgba(255,255,255,.9);
      box-shadow: 0 8px 24px rgba(15,38,58,.05);
    }
    .one-line-lane.engineering { border-top-color: var(--engineering); }
    .one-line-role {
      margin-bottom: 12px;
      color: var(--product);
      font-size: 16px;
      font-weight: 850;
    }
    .one-line-lane.engineering .one-line-role { color: var(--engineering); }
    .one-line-flow {
      display: grid;
      grid-template-columns: 1fr 26px 1fr 26px 1fr;
      align-items: center;
      gap: 4px;
    }
    .one-line-flow > i {
      color: #9db2c4;
      font-size: 22px;
      font-style: normal;
      text-align: center;
    }
    .one-line-node {
      display: flex;
      flex-direction: column;
      justify-content: center;
      min-width: 0;
      height: 66px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      background: #f7f9fb;
    }
    .one-line-node span {
      margin-bottom: 4px;
      color: #8796a4;
      font-size: 9px;
      font-weight: 850;
      letter-spacing: .8px;
    }
    .one-line-node strong {
      color: var(--ink);
      font-size: 12px;
      line-height: 1.35;
    }
    .one-line-node.agent {
      border-color: #d8d2ef;
      background: var(--future-soft);
    }
    .one-line-benefit {
      position: absolute;
      right: 18px;
      top: 14px;
      padding: 5px 10px;
      background: var(--product-soft);
      color: #1c56a5;
      font-size: 10px;
      font-weight: 800;
    }
    .one-line-lane.engineering .one-line-benefit {
      background: var(--engineering-soft);
      color: #08766b;
    }
    .one-line-gap-title {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 14px;
      color: var(--muted);
      font-size: 14px;
      font-weight: 800;
    }
    .one-line-gap-title b { color: var(--danger); font-size: 24px; }
    .one-line-gap-title strong { color: var(--ink); }
    .one-line-gaps {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }
    .one-line-gap {
      min-width: 0;
      padding: 13px 14px;
      border-top: 4px solid var(--danger);
      background: rgba(255,255,255,.9);
    }
    .one-line-gap span {
      color: var(--danger);
      font-size: 10px;
      font-weight: 850;
    }
    .one-line-gap strong {
      display: block;
      margin: 5px 0 4px;
      color: var(--ink);
      font-size: 15px;
    }
    .one-line-gap p {
      margin: 0;
      color: var(--muted);
      font-size: 10px;
      line-height: 1.35;
    }
    .one-line-summary,
    .sdd-shift-summary {
      display: flex;
      align-items: center;
      height: 64px;
      margin-top: 16px;
      padding: 0 22px;
      border-left: 5px solid var(--shared);
      background: var(--shared-soft);
      color: #875006;
      font-size: 16px;
      font-weight: 850;
      white-space: nowrap;
    }
    .sdd-shift-layout {
      display: grid;
      grid-template-rows: 148px 118px 68px;
      gap: 10px;
      padding-top: 7px;
    }
    .sdd-shift-modes {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 116px minmax(0, 1fr);
      gap: 12px;
    }
    .sdd-mode {
      min-width: 0;
      overflow: hidden;
      border-top: 5px solid var(--danger);
      background: rgba(255,255,255,.92);
    }
    .sdd-mode.after { border-top-color: var(--engineering); }
    .sdd-mode-title {
      padding: 10px 16px 6px;
      color: var(--danger);
      font-size: 15px;
      font-weight: 850;
    }
    .sdd-mode.after .sdd-mode-title { color: var(--engineering); }
    .sdd-mode-core {
      margin: 0 16px 7px;
      padding: 8px 10px;
      background: var(--danger-soft);
      color: #96362c;
      font-size: 15px;
      font-weight: 850;
      text-align: center;
    }
    .sdd-mode.after .sdd-mode-core {
      background: var(--engineering-soft);
      color: #08766b;
    }
    .sdd-mode-items {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 6px;
      padding: 0 16px 10px;
    }
    .sdd-mode-items div {
      display: flex;
      min-width: 0;
      align-items: center;
      gap: 5px;
      padding: 7px 8px;
      border: 1px solid var(--line);
      background: #f8fafb;
    }
    .sdd-mode-items span {
      color: #8c9aa7;
      font-size: 8px;
      font-weight: 850;
    }
    .sdd-mode-items strong {
      color: var(--ink);
      font-size: 9px;
      line-height: 1.25;
    }
    .sdd-shift-arrow {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      color: #8a9dad;
    }
    .sdd-shift-arrow span {
      font-size: 11px;
      font-weight: 800;
      white-space: nowrap;
    }
    .sdd-shift-arrow i {
      color: var(--engineering);
      font-size: 38px;
      font-style: normal;
      line-height: 1;
    }
    .sdd-shift-table {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }
    .sdd-shift-row {
      display: grid;
      grid-template-rows: 24px 1fr 18px 1fr;
      min-width: 0;
      padding: 10px 12px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,.92);
      text-align: center;
    }
    .sdd-shift-row > span {
      color: var(--muted);
      font-size: 10px;
      font-weight: 850;
    }
    .sdd-shift-row b {
      color: #96362c;
      font-size: 11px;
    }
    .sdd-shift-row i {
      color: #9cb1c2;
      font-size: 16px;
      font-style: normal;
      line-height: 18px;
    }
    .sdd-shift-row strong {
      color: #08766b;
      font-size: 11px;
    }
    .sdd-choice {
      display: grid;
      grid-template-columns: 190px minmax(0, 1fr);
      align-items: center;
      min-width: 0;
      border-left: 5px solid var(--engineering);
      background: var(--engineering-soft);
    }
    .sdd-choice > strong {
      padding-left: 18px;
      color: #08766b;
      font-size: 15px;
    }
    .sdd-choice > div {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      padding: 10px 12px 10px 0;
    }
    .sdd-choice span {
      display: flex;
      align-items: center;
      justify-content: center;
      min-width: 0;
      height: 42px;
      padding: 0 9px;
      border: 1px solid rgba(13,147,134,.25);
      background: rgba(255,255,255,.72);
      color: #155e57;
      font-size: 9px;
      font-weight: 750;
      line-height: 1.3;
      text-align: center;
    }
    .sdd-shift-summary {
      height: 58px;
      margin-top: 14px;
      border-left-color: var(--engineering);
      background: linear-gradient(90deg, var(--engineering-soft), var(--product-soft));
      color: #08766b;
    }

    /* Page 4: combined current-state and collaboration overview */
    .collab-overview {
      display: grid;
      grid-template-rows: 166px 184px 68px;
      gap: 14px;
      padding-top: 7px;
    }
    .collab-loops {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 156px minmax(0, 1fr);
      align-items: stretch;
      gap: 14px;
    }
    .collab-loop {
      position: relative;
      min-width: 0;
      padding: 17px 18px 12px;
      border-top: 5px solid var(--product);
      background: rgba(255,255,255,.86);
      box-shadow: 0 8px 26px rgba(15,38,58,.05);
    }
    .collab-loop.engineering { border-top-color: var(--engineering); }
    .collab-loop-title {
      color: var(--product);
      font-size: 19px;
      font-weight: 850;
      white-space: nowrap;
    }
    .collab-loop.engineering .collab-loop-title { color: var(--engineering); }
    .collab-loop-track {
      display: flex;
      align-items: center;
      width: 100%;
      height: 44px;
      margin-top: 13px;
    }
    .collab-loop-step {
      display: flex;
      flex: 1;
      align-items: center;
      justify-content: center;
      min-width: 0;
      height: 42px;
      padding: 0 5px;
      border: 1px solid #c8d8ec;
      background: var(--product-soft);
      color: #174f9c;
      font-size: 12px;
      line-height: 1.2;
      font-weight: 800;
      text-align: center;
      overflow: hidden;
      white-space: nowrap;
    }
    .collab-loop.engineering .collab-loop-step {
      border-color: #bddfd9;
      background: var(--engineering-soft);
      color: #08766c;
    }
    .collab-step-arrow {
      position: relative;
      flex: 0 0 13px;
      height: 2px;
      background: #7fa4dc;
    }
    .collab-loop.engineering .collab-step-arrow { background: #65b9ae; }
    .collab-step-arrow::after {
      content: "";
      position: absolute;
      right: -1px;
      top: 50%;
      transform: translateY(-50%);
      border-left: 5px solid #7fa4dc;
      border-top: 4px solid transparent;
      border-bottom: 4px solid transparent;
    }
    .collab-loop.engineering .collab-step-arrow::after { border-left-color: #65b9ae; }
    .collab-return {
      position: relative;
      height: 31px;
      margin: 8px 4px 0;
    }
    .collab-return::before {
      content: "";
      position: absolute;
      left: 10px;
      right: 0;
      top: 7px;
      height: 2px;
      background: #9bb7e2;
    }
    .collab-loop.engineering .collab-return::before { background: #8ac9c1; }
    .collab-return::after {
      content: "";
      position: absolute;
      left: 1px;
      top: 3px;
      border-right: 7px solid #7fa4dc;
      border-top: 5px solid transparent;
      border-bottom: 5px solid transparent;
    }
    .collab-loop.engineering .collab-return::after { border-right-color: #65b9ae; }
    .collab-return span {
      position: absolute;
      right: 0;
      top: 13px;
      color: #7897c6;
      font-size: 10px;
      font-weight: 800;
      white-space: nowrap;
    }
    .collab-loop.engineering .collab-return span { color: #5ca89f; }
    .collab-handoff {
      position: relative;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-width: 0;
    }
    .collab-handoff-roles {
      display: flex;
      justify-content: space-between;
      width: 100%;
      margin-bottom: 8px;
      color: #9a5a08;
      font-size: 10px;
      font-weight: 800;
      white-space: nowrap;
    }
    .collab-handoff-arrow {
      position: relative;
      width: 100%;
      height: 2px;
      background: linear-gradient(90deg, var(--product), var(--shared) 48%, var(--engineering));
    }
    .collab-handoff-arrow::after {
      content: "";
      position: absolute;
      right: -1px;
      top: 50%;
      transform: translateY(-50%);
      border-left: 8px solid var(--engineering);
      border-top: 5px solid transparent;
      border-bottom: 5px solid transparent;
    }
    .collab-handoff-card {
      width: 140px;
      margin-top: 13px;
      padding: 11px 8px 12px;
      border: 1px solid var(--shared);
      background: var(--shared-soft);
      text-align: center;
    }
    .collab-handoff-card small,
    .collab-handoff-card strong,
    .collab-handoff-card span {
      display: block;
      white-space: nowrap;
    }
    .collab-handoff-card small { color: #9d640e; font-size: 9px; font-weight: 800; letter-spacing: .8px; }
    .collab-handoff-card strong { margin-top: 4px; color: #8d4f00; font-size: 15px; }
    .collab-handoff-card span { margin-top: 2px; color: #a87428; font-size: 10px; font-weight: 750; }
    .collab-spaces {
      display: grid;
      grid-template-columns: 1fr .78fr 1fr;
      gap: 14px;
    }
    .collab-space {
      min-width: 0;
      background: rgba(255,255,255,.88);
      box-shadow: 0 8px 24px rgba(15,38,58,.04);
    }
    .collab-space-title {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 42px;
      background: var(--product);
      color: white;
      font-size: 17px;
      font-weight: 850;
      white-space: nowrap;
    }
    .collab-space.shared .collab-space-title { background: var(--shared); }
    .collab-space.engineering .collab-space-title { background: var(--engineering); }
    .collab-space-items { padding: 4px 16px 5px; }
    .collab-space-item {
      display: grid;
      grid-template-columns: 48px minmax(0, 1fr);
      align-items: center;
      min-height: 44px;
      border-bottom: 1px solid var(--line);
    }
    .collab-space-item:last-child { border-bottom: none; }
    .collab-space-item span {
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      white-space: nowrap;
    }
    .collab-space-item strong {
      color: #1e5cb7;
      font-size: 14px;
      font-weight: 800;
      white-space: nowrap;
    }
    .collab-space.shared .collab-space-item strong { color: #9a5a08; }
    .collab-space.shared .collab-space-item {
      grid-template-columns: minmax(0, 1fr);
      text-align: center;
    }
    .collab-space.shared .collab-space-item span { display: none; }
    .collab-space.engineering .collab-space-item strong { color: #08766c; }
    .collab-conclusion {
      display: flex;
      align-items: center;
      padding: 0 24px;
      border-left: 5px solid var(--shared);
      background: var(--shared-soft);
      color: #7e4905;
      font-size: 16px;
      line-height: 1.45;
      font-weight: 850;
      white-space: normal;
    }

    /* Product manager-led Agent Harness operating model */
    .agent-model-body {
      display: grid;
      grid-template-columns: minmax(0, 2.75fr) minmax(260px, .85fr);
      gap: 12px;
      height: 372px;
      padding-top: 0;
    }
    .agent-system {
      display: grid;
      grid-template-rows: 44px 10px minmax(0, 1fr);
      min-width: 0;
      min-height: 0;
    }
    .agent-manager-row {
      display: grid;
      grid-template-columns: 156px minmax(0, 1fr);
      min-width: 0;
      overflow: hidden;
      border: 1px solid #e7d9c5;
      background: #fff;
    }
    .agent-manager-heading {
      display: flex;
      flex-direction: column;
      justify-content: center;
      padding: 0 11px;
      border-left: 4px solid var(--shared);
      background: #fff7ec;
      color: #7d4b0a;
    }
    .agent-manager-heading strong {
      display: block;
      font-size: 12px;
      line-height: 1.2;
      white-space: nowrap;
    }
    .agent-manager-heading span {
      display: block;
      margin-top: 3px;
      color: #a2763f;
      font-size: 7px;
      font-weight: 650;
      white-space: nowrap;
    }
    .agent-manager-items {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
      padding: 0 10px;
    }
    .agent-manager-items span {
      flex: 1;
      min-width: 0;
      padding: 5px 4px;
      border: 1px solid #ecd9bd;
      background: #fffaf3;
      color: #76562e;
      font-size: 8px;
      font-weight: 800;
      text-align: center;
      white-space: nowrap;
    }
    .agent-governance-link {
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .agent-governance-link::before {
      content: "目标与门禁";
      position: absolute;
      left: calc(50% + 8px);
      top: 0;
      color: #a97a3e;
      font-size: 7px;
      font-weight: 800;
      letter-spacing: .05em;
    }
    .agent-governance-link span {
      position: relative;
      display: block;
      width: 2px;
      height: 8px;
      background: #d7a257;
    }
    .agent-governance-link span::after {
      content: "";
      position: absolute;
      left: 50%;
      bottom: -1px;
      transform: translateX(-50%);
      border-top: 4px solid #d7a257;
      border-left: 4px solid transparent;
      border-right: 4px solid transparent;
    }
    .agent-harness {
      display: grid;
      grid-template-rows: 46px minmax(0, 1fr) 34px;
      gap: 8px;
      min-width: 0;
      min-height: 0;
      padding: 9px;
      border: 1px solid #9cabb8;
      background: #f7fafc;
      box-shadow: 0 2px 8px rgba(16,42,67,.05);
    }
    .agent-harness-header {
      display: grid;
      grid-template-columns: 300px minmax(0, 1fr);
      align-items: center;
      min-width: 0;
      height: 46px;
      padding: 0;
      background: #edf3f7;
      color: var(--ink);
    }
    .agent-harness-header > div:first-child {
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-self: stretch;
      min-width: 0;
      padding: 0 11px;
      background: #173149;
      color: white;
    }
    .agent-harness-header strong {
      display: block;
      font-size: 11.5px;
      line-height: 1.18;
      white-space: nowrap;
    }
    .agent-harness-header > div:first-child span {
      display: block;
      margin-top: 3px;
      color: rgba(255,255,255,.7);
      font-size: 8px;
      font-weight: 650;
      white-space: nowrap;
    }
    .agent-harness-capabilities {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 6px;
      min-width: 0;
      padding: 0 8px;
    }
    .agent-harness-capabilities span {
      min-width: 0;
      padding: 6px 2px;
      border: 1px solid #cbd6df;
      background: #fff;
      color: #41586b;
      font-size: 7px;
      font-weight: 750;
      text-align: center;
      white-space: nowrap;
    }
    .agent-orchestrator {
      display: grid;
      grid-template-rows: 40px minmax(0, 1fr);
      min-width: 0;
      min-height: 0;
      margin-top: 0;
      padding: 0 0 7px;
      border: 1px solid #cbd4df;
      background: #fbfcfe;
      box-shadow: none;
    }
    .agent-orchestrator-header {
      display: grid;
      grid-template-columns: 240px minmax(0, 1fr);
      align-items: center;
      min-width: 0;
      height: 40px;
      padding: 0;
      background: #eef1fb;
      color: var(--ink);
    }
    .agent-orchestrator-header > div:first-child {
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-self: stretch;
      min-width: 0;
      padding: 0 10px;
      background: #5868c8;
      color: white;
    }
    .agent-orchestrator-header strong {
      display: block;
      font-size: 12px;
      line-height: 1.15;
      white-space: nowrap;
    }
    .agent-orchestrator-header > div:first-child span {
      display: block;
      margin-top: 3px;
      color: rgba(255,255,255,.74);
      font-size: 7px;
      font-weight: 650;
      white-space: nowrap;
    }
    .agent-process {
      display: flex;
      align-items: center;
      min-width: 0;
      padding: 0 8px;
    }
    .agent-process span {
      flex: 1;
      min-width: 0;
      padding: 6px 2px;
      border: 1px solid #cbd3ef;
      background: #fff;
      color: #48569b;
      font-size: 7px;
      font-weight: 750;
      text-align: center;
      white-space: nowrap;
    }
    .agent-process i {
      position: relative;
      flex: 0 0 10px;
      height: 1px;
      background: #aeb8dd;
    }
    .agent-process i::after {
      content: "";
      position: absolute;
      right: -1px;
      top: 50%;
      transform: translateY(-50%);
      border-left: 4px solid #aeb8dd;
      border-top: 3px solid transparent;
      border-bottom: 3px solid transparent;
    }
    .agent-engine-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      min-width: 0;
      min-height: 0;
      margin: 8px 8px 0;
    }
    .agent-engine-card {
      min-width: 0;
      min-height: 0;
      height: auto;
      padding: 8px 9px 7px;
      border: 1px solid #e1e6eb;
      border-top: 3px solid var(--future);
      background: #fff;
      box-shadow: none;
    }
    .agent-engine-card.skill { border-top-color: var(--product); }
    .agent-engine-card.tools { border-top-color: var(--engineering); }
    .agent-engine-card strong {
      display: block;
      overflow: hidden;
      color: var(--ink);
      font-size: 11px;
      line-height: 1.15;
      white-space: nowrap;
      text-overflow: ellipsis;
    }
    .agent-engine-card p {
      overflow: hidden;
      margin: 4px 0 7px;
      color: var(--muted);
      font-size: 8px;
      line-height: 1.2;
      white-space: nowrap;
      text-overflow: ellipsis;
    }
    .agent-engine-items {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 4px;
      min-width: 0;
    }
    .agent-engine-items span {
      min-width: 0;
      padding: 6px 1px;
      border: 1px solid #e0e6ec;
      background: #f6f8fa;
      color: #465b6d;
      font-size: 8px;
      font-weight: 750;
      text-align: center;
      white-space: nowrap;
    }
    .agent-engine-card.model .agent-engine-items span { border-color: #dad4f1; background: var(--future-soft); color: #514493; }
    .agent-engine-card.skill .agent-engine-items span { border-color: #c7d7ef; background: var(--product-soft); color: #1d58aa; }
    .agent-engine-card.tools .agent-engine-items span { border-color: #c7e2dd; background: var(--engineering-soft); color: #08766c; }
    .agent-system-relationship {
      display: flex;
      align-items: center;
      min-width: 0;
      height: 34px;
      margin-top: 0;
      padding: 0 10px;
      border: 1px dashed #b8c4ce;
      background: #f1f5f8;
    }
    .agent-system-relationship strong {
      flex: 0 0 62px;
      color: var(--navy);
      font-size: 9px;
      font-weight: 850;
      white-space: nowrap;
    }
    .agent-system-relationship span {
      flex: 1;
      min-width: 0;
      color: #465b6d;
      font-size: 8px;
      font-weight: 750;
      text-align: center;
      white-space: nowrap;
    }
    .agent-system-relationship i {
      flex: 0 0 9px;
      color: #95a9ba;
      font-size: 9px;
      font-style: normal;
      text-align: center;
    }
    .agent-model-principles {
      display: grid;
      grid-template-rows: 42px repeat(4, 1fr);
      gap: 8px;
      min-width: 0;
    }
    .agent-principles-title {
      display: flex;
      align-items: center;
      padding: 0 18px;
      background: var(--ink);
      color: white;
      font-size: 16px;
      font-weight: 850;
    }
    .agent-principle {
      position: relative;
      min-width: 0;
      padding: 9px 12px 7px 43px;
      border-left: 4px solid var(--shared);
      background: rgba(255,255,255,.9);
    }
    .agent-principle:nth-child(3) { border-left-color: var(--product); }
    .agent-principle:nth-child(4) { border-left-color: var(--future); }
    .agent-principle:nth-child(5) { border-left-color: var(--engineering); }
    .agent-principle > span {
      position: absolute;
      left: 13px;
      top: 10px;
      color: #9aa8b3;
      font-size: 10px;
      font-weight: 850;
    }
    .agent-principle strong {
      display: block;
      color: var(--ink);
      font-size: 12px;
      line-height: 1.2;
      white-space: nowrap;
    }
    .agent-principle p {
      margin: 4px 0 0;
      color: var(--muted);
      font-size: 8px;
      line-height: 1.3;
      white-space: nowrap;
    }
    .agent-result-chain {
      display: flex;
      align-items: center;
      height: 66px;
      margin-top: 26px;
      padding: 0 20px;
      border-left: 5px solid var(--shared);
      background: linear-gradient(90deg, var(--shared-soft), #fff 42%, var(--product-soft));
    }
    .agent-result-label {
      flex: 0 0 76px;
      color: #8a5109;
      font-size: 13px;
      font-weight: 850;
    }
    .agent-result-node {
      display: flex;
      flex: 1;
      align-items: center;
      justify-content: center;
      min-width: 0;
      height: 42px;
      border: 1px solid #d5dee5;
      background: white;
      color: var(--ink);
      font-size: 12px;
      font-weight: 850;
      white-space: nowrap;
    }
    .agent-result-node:last-child { border-color: #b9d6d1; color: var(--engineering); }
    .agent-result-arrow {
      position: relative;
      flex: 0 0 22px;
      height: 2px;
      background: #95a9ba;
    }
    .agent-result-arrow::after {
      content: "";
      position: absolute;
      right: -1px;
      top: 50%;
      transform: translateY(-50%);
      border-left: 7px solid #95a9ba;
      border-top: 5px solid transparent;
      border-bottom: 5px solid transparent;
    }

    /* Page 4: project structure and responsibility map */
    .project-framework-map {
      display: grid;
      grid-template-rows: 318px 72px 56px;
      gap: 12px;
      padding-top: 7px;
    }
    .project-framework-main {
      display: grid;
      grid-template-columns: minmax(0, .92fr) minmax(0, 1.38fr);
      gap: 18px;
      min-height: 0;
    }
    .project-tree-panel,
    .project-mapping-panel {
      min-width: 0;
      overflow: hidden;
      border: 1px solid var(--line);
      background: rgba(255,255,255,.92);
    }
    .project-tree-panel {
      border-color: #1d3a50;
      background: #0d2639;
      color: #dce8ef;
    }
    .project-panel-title {
      display: flex;
      align-items: center;
      height: 42px;
      padding: 0 18px;
      background: var(--product);
      color: white;
      font-size: 16px;
      font-weight: 850;
    }
    .project-tree-panel .project-panel-title { background: #173a53; }
    .project-tree {
      padding: 11px 20px 12px;
      font-family: Consolas, "Microsoft YaHei", monospace;
    }
    .project-tree div {
      height: 23px;
      color: #d9e5ec;
      font-size: 12px;
      line-height: 23px;
      white-space: nowrap;
    }
    .project-tree div:first-child {
      color: #7fd8cd;
      font-size: 14px;
      font-weight: 850;
    }
    .project-mapping-head,
    .project-mapping-row {
      display: grid;
      grid-template-columns: 150px minmax(0, 1fr);
      align-items: center;
    }
    .project-mapping-head {
      height: 36px;
      background: #edf2f6;
      color: var(--muted);
      font-size: 11px;
      font-weight: 850;
    }
    .project-mapping-head span { padding: 0 16px; }
    .project-mapping-row {
      height: 40px;
      border-top: 1px solid var(--line);
    }
    .project-mapping-row strong {
      padding: 0 16px;
      color: #1f5eb8;
      font-size: 13px;
      white-space: nowrap;
    }
    .project-mapping-row span {
      min-width: 0;
      padding: 0 16px;
      border-left: 1px solid var(--line);
      color: var(--ink);
      font-size: 13px;
      font-weight: 700;
      white-space: nowrap;
    }
    .project-governance-assets {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 18px;
    }
    .project-governance-card {
      display: grid;
      grid-template-columns: 145px minmax(0, 1fr);
      align-items: center;
      min-width: 0;
      border-top: 4px solid var(--shared);
      background: rgba(255,255,255,.9);
    }
    .project-governance-card:nth-child(2) { border-top-color: var(--future); }
    .project-governance-card:nth-child(3) { border-top-color: var(--product); }
    .project-governance-card strong {
      padding-left: 18px;
      color: var(--ink);
      font-family: Consolas, "Microsoft YaHei", monospace;
      font-size: 15px;
      white-space: nowrap;
    }
    .project-governance-card span {
      padding-left: 16px;
      border-left: 1px solid var(--line);
      color: var(--muted);
      font-size: 13px;
      font-weight: 750;
      white-space: nowrap;
    }
    .project-framework-summary {
      display: flex;
      align-items: center;
      padding: 0 22px;
      border-left: 5px solid var(--product);
      background: var(--product-soft);
      color: #1d55a4;
      font-size: 15px;
      font-weight: 850;
      white-space: nowrap;
    }

    /* Page 5: complete controlled SOP */
    .practice-sop-map {
      display: grid;
      grid-template-rows: 344px 62px;
      gap: 16px;
      padding-top: 7px;
    }
    .practice-sop-stages {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 14px;
    }
    .practice-sop-stage {
      display: grid;
      grid-template-rows: 56px 30px minmax(0, 1fr) 42px;
      min-width: 0;
      overflow: hidden;
      border-top: 5px solid #607d94;
      background: rgba(255,255,255,.9);
    }
    .practice-sop-stage.discovery { border-top-color: var(--product); }
    .practice-sop-stage.delivery { border-top-color: var(--future); }
    .practice-sop-stage.handoff { border-top-color: var(--engineering); }
    .practice-stage-head {
      display: flex;
      align-items: center;
      padding: 0 18px;
      border-bottom: 1px solid var(--line);
    }
    .practice-stage-head span {
      margin-right: 12px;
      color: #8b99a5;
      font-size: 11px;
      font-weight: 850;
    }
    .practice-stage-head strong {
      color: var(--ink);
      font-size: 19px;
      white-space: nowrap;
    }
    .practice-stage-gate {
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 5px 14px 0;
      background: var(--shared-soft);
      color: #985703;
      font-size: 11px;
      font-weight: 850;
      white-space: nowrap;
    }
    .practice-stage-gate.empty { visibility: hidden; }
    .practice-stage-steps {
      display: flex;
      flex-direction: column;
      justify-content: center;
      gap: 6px;
      min-height: 0;
      padding: 8px 14px;
    }
    .practice-stage-step {
      display: grid;
      grid-template-columns: 30px minmax(0, 1fr);
      align-items: center;
      min-height: 36px;
      border: 1px solid var(--line);
      background: #f8fafb;
    }
    .practice-stage-step span {
      color: #8c9ba7;
      font-size: 9px;
      font-weight: 850;
      text-align: center;
    }
    .practice-stage-step strong {
      color: var(--ink);
      font-size: 13px;
      white-space: nowrap;
    }
    .practice-stage-artifact {
      display: flex;
      align-items: center;
      justify-content: center;
      background: #edf2f5;
      color: #50677a;
      font-size: 12px;
      font-weight: 850;
      white-space: nowrap;
    }
    .practice-sop-stage.discovery .practice-stage-artifact { background: var(--product-soft); color: #1d57a7; }
    .practice-sop-stage.delivery .practice-stage-artifact { background: var(--future-soft); color: #514493; }
    .practice-sop-stage.handoff .practice-stage-artifact { background: var(--engineering-soft); color: #08766c; }
    .practice-sop-summary {
      display: flex;
      align-items: center;
      padding: 0 22px;
      border-left: 5px solid var(--shared);
      background: var(--shared-soft);
      color: #875006;
      font-size: 16px;
      font-weight: 850;
      white-space: nowrap;
    }

    /* Page 6: evidence-led requirement analysis */
    .evidence-requirement-layout {
      display: grid;
      grid-template-rows: 278px 90px 54px;
      gap: 12px;
      padding-top: 7px;
    }
    .evidence-analysis-table {
      overflow: hidden;
      border: 1px solid var(--line);
      background: rgba(255,255,255,.92);
    }
    .evidence-table-head,
    .evidence-table-row {
      display: grid;
      grid-template-columns: 140px minmax(0, 1.05fr) minmax(0, 1.5fr);
      align-items: center;
    }
    .evidence-table-head {
      height: 38px;
      background: var(--ink);
      color: white;
      font-size: 12px;
      font-weight: 850;
    }
    .evidence-table-head span { padding: 0 16px; }
    .evidence-table-row {
      min-height: 60px;
      border-top: 1px solid var(--line);
    }
    .evidence-table-row strong {
      padding: 0 16px;
      color: #1e5eb6;
      font-size: 14px;
      white-space: nowrap;
    }
    .evidence-table-row > span {
      min-width: 0;
      padding: 0 16px;
      border-left: 1px solid var(--line);
      color: var(--ink);
      font-size: 13px;
      line-height: 1.35;
      font-weight: 700;
    }
    .evidence-table-row > span.risk { color: #963b34; background: rgba(207,76,65,.045); }
    .evidence-case-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 18px;
    }
    .evidence-case {
      display: grid;
      grid-template-columns: 130px minmax(0, 1fr);
      align-items: center;
      min-width: 0;
      border-left: 5px solid var(--shared);
      background: rgba(255,255,255,.9);
    }
    .evidence-case:last-child { border-left-color: var(--product); }
    .evidence-case strong {
      padding-left: 18px;
      color: var(--ink);
      font-size: 15px;
      white-space: nowrap;
    }
    .evidence-case span {
      padding: 0 18px;
      border-left: 1px solid var(--line);
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
    }
    .evidence-summary {
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--product-soft);
      color: #1d55a4;
      font-size: 18px;
      font-weight: 850;
      white-space: nowrap;
    }

    /* Page 7: Spec Kit to Demo */
    .speckit-demo-layout {
      display: grid;
      grid-template-rows: 108px 246px 58px;
      gap: 14px;
      padding-top: 7px;
    }
    .speckit-pipeline {
      display: flex;
      align-items: center;
      min-width: 0;
    }
    .speckit-pipeline-node {
      display: flex;
      flex: 1;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-width: 0;
      height: 88px;
      border-top: 4px solid var(--product);
      background: rgba(255,255,255,.92);
      text-align: center;
    }
    .speckit-pipeline-node.gate {
      height: 102px;
      border-top-color: var(--shared);
      background: var(--shared-soft);
      box-shadow: 0 0 0 2px rgba(240,161,59,.2);
    }
    .speckit-pipeline-node span {
      color: #7d91a0;
      font-size: 9px;
      font-weight: 850;
    }
    .speckit-pipeline-node strong {
      margin-top: 7px;
      color: var(--ink);
      font-size: 12px;
      line-height: 1.25;
      white-space: nowrap;
    }
    .speckit-pipeline-node.gate strong { color: #955302; font-size: 14px; }
    .speckit-pipeline-arrow {
      position: relative;
      flex: 0 0 22px;
      height: 2px;
      background: #9cafbf;
    }
    .speckit-pipeline-arrow::after {
      content: "";
      position: absolute;
      right: -1px;
      top: 50%;
      transform: translateY(-50%);
      border-left: 6px solid #9cafbf;
      border-top: 4px solid transparent;
      border-bottom: 4px solid transparent;
    }
    .speckit-demo-body {
      display: grid;
      grid-template-columns: minmax(0, 3fr) minmax(0, 1.05fr);
      gap: 18px;
      min-height: 0;
    }
    .speckit-actions {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 14px;
    }
    .speckit-action {
      min-width: 0;
      border-top: 5px solid var(--product);
      background: rgba(255,255,255,.92);
    }
    .speckit-action:nth-child(2) { border-top-color: var(--shared); }
    .speckit-action:nth-child(3) { border-top-color: var(--future); }
    .speckit-action-title {
      display: flex;
      align-items: center;
      height: 54px;
      padding: 0 18px;
      border-bottom: 1px solid var(--line);
    }
    .speckit-action-title span {
      margin-right: 12px;
      color: #95a3af;
      font-size: 10px;
      font-weight: 850;
    }
    .speckit-action-title strong { color: var(--ink); font-size: 17px; white-space: nowrap; }
    .speckit-action-list {
      display: grid;
      gap: 0;
      margin: 0;
      padding: 8px 18px;
      list-style: none;
    }
    .speckit-action-list li {
      display: flex;
      align-items: center;
      min-height: 46px;
      border-bottom: 1px solid var(--line);
      color: var(--ink);
      font-size: 13px;
      font-weight: 700;
      white-space: nowrap;
    }
    .speckit-action-list li:last-child { border-bottom: none; }
    .speckit-pitfalls {
      overflow: hidden;
      border: 1px solid #e7c4c0;
      background: var(--danger-soft);
    }
    .speckit-pitfall-title {
      display: flex;
      align-items: center;
      height: 54px;
      padding: 0 18px;
      background: var(--danger);
      color: white;
      font-size: 17px;
      font-weight: 850;
    }
    .speckit-pitfall {
      min-height: 60px;
      padding: 15px 18px;
      border-bottom: 1px solid #e8c6c2;
      color: #8d3831;
      font-size: 12px;
      line-height: 1.4;
      font-weight: 750;
    }
    .speckit-demo-summary {
      display: flex;
      align-items: center;
      padding: 0 22px;
      border-left: 5px solid var(--product);
      background: var(--product-soft);
      color: #1d55a4;
      font-size: 15px;
      font-weight: 850;
      white-space: nowrap;
    }

    /* Page 8: validation, feedback routing, and delivery */
    .validation-delivery-layout {
      display: grid;
      grid-template-rows: 326px 104px;
      gap: 14px;
      padding-top: 7px;
    }
    .validation-delivery-columns {
      display: grid;
      grid-template-columns: minmax(0, .92fr) minmax(0, 1.3fr) minmax(0, .98fr);
      gap: 16px;
    }
    .validation-column,
    .feedback-column,
    .delivery-column {
      min-width: 0;
      overflow: hidden;
      background: rgba(255,255,255,.92);
    }
    .validation-column-title,
    .feedback-column-title,
    .delivery-column-title {
      display: flex;
      align-items: center;
      height: 44px;
      padding: 0 18px;
      background: var(--product);
      color: white;
      font-size: 17px;
      font-weight: 850;
    }
    .feedback-column-title { background: var(--shared); }
    .delivery-column-title { background: var(--engineering); }
    .validation-level {
      position: relative;
      min-height: 92px;
      padding: 16px 16px 12px 54px;
      border-bottom: 1px solid var(--line);
    }
    .validation-level > span {
      position: absolute;
      left: 18px;
      top: 17px;
      color: #8fa0ac;
      font-size: 10px;
      font-weight: 850;
    }
    .validation-level strong { display: block; color: var(--ink); font-size: 15px; white-space: nowrap; }
    .validation-level p { margin: 8px 0 0; color: var(--muted); font-size: 11px; line-height: 1.4; }
    .feedback-route-line {
      display: flex;
      align-items: center;
      min-height: 54px;
      padding: 0 17px;
      border-bottom: 1px solid var(--line);
      color: #784908;
      font-size: 12px;
      font-weight: 750;
      white-space: nowrap;
    }
    .delivery-package-line {
      display: grid;
      grid-template-columns: 34px minmax(0, 1fr);
      align-items: center;
      min-height: 54px;
      padding: 0 16px;
      border-bottom: 1px solid var(--line);
    }
    .delivery-package-line span { color: #81a29e; font-size: 9px; font-weight: 850; }
    .delivery-package-line strong { color: var(--ink); font-size: 12px; white-space: nowrap; }
    .validation-evolution {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 18px;
    }
    .evolution-case {
      display: grid;
      grid-template-rows: 62px 42px;
      min-width: 0;
      border-left: 5px solid var(--future);
      background: rgba(255,255,255,.92);
    }
    .evolution-case:last-child { border-left-color: var(--shared); }
    .evolution-case-main {
      display: flex;
      align-items: center;
      gap: 18px;
      min-width: 0;
      padding: 0 20px;
    }
    .evolution-kind {
      flex: 0 0 auto;
      padding: 5px 10px;
      border-radius: 3px;
      background: rgba(236,233,251,.92);
      color: var(--future);
      font-size: 10px;
      font-weight: 900;
      white-space: nowrap;
    }
    .evolution-case:last-child .evolution-kind {
      background: var(--shared-soft);
      color: #a25a00;
    }
    .evolution-route {
      display: flex;
      align-items: center;
      justify-content: flex-start;
      gap: 10px;
      min-width: 0;
    }
    .evolution-route strong {
      color: var(--future);
      font-size: 14px;
      white-space: nowrap;
    }
    .evolution-route strong:last-child { color: var(--ink); }
    .evolution-case:last-child .evolution-route strong:first-child { color: #a25a00; }
    .evolution-route span { color: #91a1ad; font-size: 14px; }
    .evolution-case p {
      display: flex;
      align-items: center;
      margin: 0;
      padding: 0 20px;
      border-top: 1px solid var(--line);
      background: rgba(247,249,251,.78);
      color: var(--muted);
      font-size: 11px;
      line-height: 1.4;
    }

    /* Page 9: Skill stack and routing */
    .skill-capability-layout {
      display: grid;
      grid-template-columns: minmax(0, 1.18fr) minmax(0, .92fr);
      gap: 18px;
      height: 350px;
      padding-top: 7px;
    }
    .skill-level-stack {
      display: grid;
      grid-template-rows: repeat(3, 1fr);
      gap: 10px;
    }
    .skill-level {
      display: grid;
      grid-template-columns: 165px minmax(0, 1fr);
      min-width: 0;
      overflow: hidden;
      border: 1px solid var(--line);
      background: rgba(255,255,255,.92);
    }
    .skill-level-title {
      display: flex;
      flex-direction: column;
      justify-content: center;
      padding: 0 18px;
      background: var(--product);
      color: white;
    }
    .skill-level.level-2 .skill-level-title { background: var(--future); }
    .skill-level.level-3 .skill-level-title { background: var(--navy); }
    .skill-level-title span { color: rgba(255,255,255,.7); font-size: 9px; font-weight: 850; }
    .skill-level-title strong { margin-top: 5px; font-size: 17px; white-space: nowrap; }
    .skill-level-items {
      display: flex;
      flex-wrap: wrap;
      align-content: center;
      gap: 8px;
      min-width: 0;
      padding: 12px 16px;
    }
    .skill-level-items span {
      padding: 7px 10px;
      border: 1px solid #d3deea;
      background: var(--product-soft);
      color: #1c56a5;
      font-family: Consolas, "Microsoft YaHei", monospace;
      font-size: 11px;
      font-weight: 750;
      white-space: nowrap;
    }
    .skill-level.level-2 .skill-level-items span { border-color: #d6d0ee; background: var(--future-soft); color: #514493; }
    .skill-level.level-3 .skill-level-items span { border-color: #ccd5dc; background: #eef2f5; color: #29475d; }
    .skill-routing-panel {
      display: grid;
      grid-template-rows: 205px 135px;
      gap: 10px;
    }
    .skill-route-block,
    .skill-quality-block {
      min-width: 0;
      overflow: hidden;
      background: rgba(255,255,255,.92);
    }
    .skill-block-title {
      display: flex;
      align-items: center;
      height: 40px;
      padding: 0 16px;
      background: var(--ink);
      color: white;
      font-size: 15px;
      font-weight: 850;
    }
    .skill-route-line {
      display: flex;
      align-items: center;
      min-height: 27px;
      padding: 0 16px;
      border-bottom: 1px solid var(--line);
      color: var(--ink);
      font-family: Consolas, "Microsoft YaHei", monospace;
      font-size: 10px;
      font-weight: 700;
      white-space: nowrap;
    }
    .skill-quality-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 5px;
      padding: 7px 14px;
    }
    .skill-quality-grid span {
      padding: 5px 9px;
      background: var(--shared-soft);
      color: #875006;
      font-size: 9px;
      font-weight: 800;
      text-align: center;
      white-space: nowrap;
    }
    .skill-capability-summary {
      display: flex;
      align-items: center;
      height: 58px;
      margin-top: 16px;
      padding: 0 22px;
      border-left: 5px solid var(--shared);
      background: var(--shared-soft);
      color: #875006;
      font-size: 16px;
      font-weight: 850;
      white-space: nowrap;
    }

    /* Page 10: minimum product-manager input */
    .pm-input-layout {
      display: grid;
      grid-template-columns: minmax(0, .78fr) minmax(0, 1.22fr);
      gap: 18px;
      height: 350px;
      padding-top: 7px;
    }
    .pm-minimum-inputs,
    .pm-trigger-prompts {
      min-width: 0;
      overflow: hidden;
      background: rgba(255,255,255,.92);
    }
    .pm-input-title,
    .pm-prompt-title {
      display: flex;
      align-items: center;
      height: 44px;
      padding: 0 18px;
      background: var(--product);
      color: white;
      font-size: 17px;
      font-weight: 850;
    }
    .pm-prompt-title { background: var(--future); }
    .pm-input-card {
      display: grid;
      grid-template-columns: 46px minmax(0, 1fr);
      align-items: center;
      min-height: 76px;
      padding: 0 18px;
      border-bottom: 1px solid var(--line);
    }
    .pm-input-card span { color: #91a0ac; font-size: 10px; font-weight: 850; }
    .pm-input-card strong { color: var(--ink); font-size: 16px; white-space: nowrap; }
    .pm-prompt-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 10px;
      padding: 14px;
    }
    .pm-prompt-bubble {
      position: relative;
      display: flex;
      align-items: center;
      min-height: 64px;
      padding: 10px 14px 10px 20px;
      border: 1px solid #d7d0ef;
      border-radius: 10px;
      background: var(--future-soft);
      color: #4e428f;
      font-size: 11px;
      line-height: 1.35;
      font-weight: 750;
    }
    .pm-prompt-bubble::before {
      content: "“";
      position: absolute;
      left: 7px;
      top: 7px;
      color: #8e82d9;
      font-size: 18px;
      font-weight: 850;
    }
    .pm-input-principle {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 68px;
      margin-top: 18px;
      border-left: 5px solid var(--shared);
      background: linear-gradient(90deg, var(--shared-soft), #fff 50%, var(--product-soft));
      color: var(--ink);
      font-size: 17px;
      font-weight: 850;
      white-space: nowrap;
    }

    /* Product-manager AI Coding quadrants */
    .quadrant-collab-layout { height: 490px; }
    .quadrant-theory-row {
      display: grid;
      grid-template-columns: minmax(0, 1.25fr) minmax(0, .75fr);
      gap: 12px;
      height: 47px;
    }
    .quadrant-definition,
    .quadrant-routing {
      display: flex;
      align-items: center;
      padding: 0 16px;
      border-left: 5px solid var(--product);
      background: var(--product-soft);
      color: #174f9d;
      font-size: 13px;
      font-weight: 800;
      white-space: nowrap;
    }
    .quadrant-routing {
      justify-content: center;
      border-left-color: var(--shared);
      background: var(--shared-soft);
      color: #915606;
    }
    .quadrant-matrix {
      height: 254px;
      margin-top: 10px;
      padding: 6px 8px 8px;
      border: 1px solid #ced9e2;
      background: rgba(255,255,255,.80);
    }
    .quadrant-axis-x {
      display: grid;
      grid-template-columns: 124px 1fr 32px 1fr;
      align-items: center;
      height: 24px;
      padding-left: 35px;
    }
    .quadrant-axis-x strong { color: var(--ink); font-size: 11px; white-space: nowrap; }
    .quadrant-axis-x span { color: var(--muted); font-size: 11px; font-weight: 800; text-align: center; white-space: nowrap; }
    .quadrant-axis-x i { color: #8ca0b0; font-size: 15px; font-style: normal; text-align: center; }
    .quadrant-matrix-body {
      display: grid;
      grid-template-columns: 34px 90px minmax(0, 1fr);
      height: 214px;
    }
    .quadrant-axis-y {
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--ink);
      font-size: 10px;
      font-weight: 850;
      writing-mode: vertical-rl;
      transform: rotate(180deg);
      white-space: nowrap;
    }
    .quadrant-row-labels {
      display: grid;
      grid-template-rows: 1fr 20px 1fr;
      align-items: center;
      padding-right: 8px;
    }
    .quadrant-row-labels span {
      color: var(--muted);
      font-size: 10px;
      line-height: 1.25;
      font-weight: 800;
      text-align: center;
    }
    .quadrant-row-labels i { color: #8ca0b0; font-size: 15px; font-style: normal; text-align: center; }
    .quadrant-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      grid-template-rows: repeat(2, minmax(0, 1fr));
      gap: 7px;
    }
    .quadrant-coordinate {
      position: relative;
      height: 382px;
      margin-top: 0;
      border: 1px solid #ced9e2;
      background: rgba(255,255,255,.80);
    }
    .quadrant-coordinate-title-y {
      position: absolute;
      z-index: 9;
      left: calc(50% + 16px);
      top: 5px;
      transform: none;
      color: #415b70;
      font-size: 10px;
      font-weight: 900;
      writing-mode: vertical-rl;
      text-orientation: upright;
      letter-spacing: 1px;
      white-space: nowrap;
    }
    .quadrant-coordinate-title-x {
      position: absolute;
      z-index: 9;
      right: 14px;
      top: calc(50% - 29px);
      left: auto;
      bottom: auto;
      transform: none;
      color: #415b70;
      font-size: 10px;
      font-weight: 900;
      white-space: nowrap;
    }
    .quadrant-coordinate-plot {
      position: absolute;
      left: 50px;
      right: 18px;
      top: 9px;
      bottom: 20px;
    }
    .quadrant-coordinate-axis-x,
    .quadrant-coordinate-axis-y {
      position: absolute;
      z-index: 4;
      background: #7890a3;
    }
    .quadrant-coordinate-axis-x { left: 0; right: 0; top: 50%; height: 2px; }
    .quadrant-coordinate-axis-y { top: 0; bottom: 0; left: 50%; width: 2px; }
    .quadrant-coordinate-axis-x::after {
      content: "";
      position: absolute;
      right: -2px;
      top: -5px;
      border-left: 9px solid #7890a3;
      border-top: 6px solid transparent;
      border-bottom: 6px solid transparent;
    }
    .quadrant-coordinate-axis-y::after {
      content: "";
      position: absolute;
      left: -5px;
      top: -2px;
      border-bottom: 9px solid #7890a3;
      border-left: 6px solid transparent;
      border-right: 6px solid transparent;
    }
    .quadrant-coordinate-label {
      position: absolute;
      z-index: 7;
      padding: 3px 8px;
      border: 1px solid #cbd8e1;
      border-radius: 10px;
      background: #f8fbfd;
      box-shadow: 0 1px 2px rgba(32, 58, 79, .08);
      color: #536d81;
      font-size: 9.5px;
      font-weight: 900;
      line-height: 1;
      white-space: nowrap;
    }
    .quadrant-coordinate-label.ai-unknown {
      left: 10px;
      top: 50%;
      transform: translateY(-50%);
    }
    .quadrant-coordinate-label.ai-known {
      right: 104px;
      top: 50%;
      transform: translateY(-50%);
    }
    .quadrant-coordinate-label.pm-known,
    .quadrant-coordinate-label.pm-unknown {
      width: 50px;
      padding: 4px 5px;
      text-align: center;
      white-space: normal;
      line-height: 1.15;
    }
    .quadrant-coordinate-label.pm-known {
      left: 50%;
      top: 112px;
      transform: translateX(-50%);
    }
    .quadrant-coordinate-label.pm-unknown {
      left: 50%;
      bottom: 16px;
      transform: translateX(-50%);
    }
    .quadrant-coordinate-origin {
      position: absolute;
      z-index: 8;
      left: 50%;
      top: 50%;
      width: 38px;
      height: 22px;
      transform: translate(-50%, -50%);
      border: 2px solid #7890a3;
      border-radius: 12px;
      background: #fff;
      color: #50687a;
      font-size: 9px;
      line-height: 18px;
      font-weight: 900;
      text-align: center;
    }
    .quadrant-card {
      min-width: 0;
      padding: 8px 10px 7px;
      border-top: 4px solid var(--product);
      background: rgba(230,238,252,.70);
      overflow: hidden;
    }
    .quadrant-card.coord-card {
      position: absolute;
      width: calc(50% - 45px);
      height: calc(50% - 24px);
      padding: 10px 13px 8px;
    }
    .quadrant-card.coord-card.teaching { left: 0; top: 0; }
    .quadrant-card.coord-card.execution { right: 0; top: 0; }
    .quadrant-card.coord-card.exploration { left: 0; bottom: 0; }
    .quadrant-card.coord-card.blindspot { right: 0; bottom: 0; }
    .quadrant-card.execution { border-top-color: var(--engineering); background: rgba(223,242,238,.78); }
    .quadrant-card.teaching { border-top-color: var(--shared); background: rgba(255,241,221,.78); }
    .quadrant-card.blindspot { border-top-color: var(--product); background: rgba(230,238,252,.78); }
    .quadrant-card.exploration { border-top-color: var(--future); background: rgba(236,233,251,.80); }
    .quadrant-card-head { display: flex; align-items: center; gap: 8px; }
    .quadrant-card-head > span {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 25px;
      height: 25px;
      border-radius: 50%;
      background: var(--product);
      color: white;
      font-size: 11px;
      font-weight: 900;
    }
    .quadrant-card.execution .quadrant-card-head > span { background: var(--engineering); }
    .quadrant-card.teaching .quadrant-card-head > span { background: var(--shared); }
    .quadrant-card.exploration .quadrant-card-head > span { background: var(--future); }
    .quadrant-card-head strong { color: var(--ink); font-size: 14px; white-space: nowrap; }
    .quadrant-card p {
      margin: 4px 0 0;
      color: #485e70;
      font-size: 10px;
      line-height: 1.22;
      font-weight: 700;
      white-space: nowrap;
    }
    .quadrant-card.coord-card p {
      margin-top: 7px;
      font-size: 10.5px;
      line-height: 1.24;
      white-space: normal;
    }
    .quadrant-card.coord-card .quadrant-card-head strong { font-size: 15px; }
    .quadrant-card.coord-card .quadrant-card-head > span { width: 25px; height: 25px; font-size: 10px; }
    .quadrant-card.coord-card p b { min-width: 30px; margin-right: 5px; font-size: 9px; }
    .quadrant-card p b {
      display: inline-block;
      min-width: 28px;
      margin-right: 5px;
      color: var(--muted);
      font-size: 9px;
      font-weight: 900;
    }
    .quadrant-card .quadrant-case {
      padding: 3px 6px;
      background: rgba(255,255,255,.70);
    }
    .quadrant-card .quadrant-risk { color: #98433b; }
    .quadrant-migration {
      display: flex;
      align-items: stretch;
      height: 84px;
      margin-top: 18px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,.82);
    }
    .quadrant-migration-label {
      display: flex;
      flex: 0 0 82px;
      align-items: center;
      justify-content: center;
      border-left: 5px solid var(--future);
      color: var(--future);
      font-size: 13px;
      font-weight: 900;
    }
    .quadrant-migration-step {
      display: flex;
      flex: 1;
      flex-direction: column;
      justify-content: center;
      min-width: 0;
      padding: 8px 12px;
      border-top: 3px solid var(--product);
    }
    .quadrant-migration-step.execution { border-top-color: var(--engineering); }
    .quadrant-migration-step.teaching { border-top-color: var(--shared); }
    .quadrant-migration-step.exploration { border-top-color: var(--future); }
    .quadrant-migration-step.maturity { border-top-color: #415b70; }
    .quadrant-migration-step strong { color: var(--ink); font-size: 12px; white-space: nowrap; }
    .quadrant-migration-step span { margin-top: 4px; color: var(--muted); font-size: 10px; white-space: nowrap; }
    .quadrant-migration > i {
      display: flex;
      align-items: center;
      color: #91a4b3;
      font-size: 17px;
      font-style: normal;
    }
    .quadrant-conclusion {
      display: grid;
      grid-template-columns: 1fr auto;
      align-items: center;
      min-height: 50px;
      margin-top: 10px;
      padding: 0 16px;
      border-left: 5px solid var(--shared);
      background: linear-gradient(90deg, var(--shared-soft), rgba(230,238,252,.66));
    }
    .quadrant-conclusion strong { color: var(--ink); font-size: 14px; white-space: nowrap; }
    .quadrant-conclusion small { color: #81909c; font-size: 9px; white-space: nowrap; }

    /* Inserted engineering practice chapter */
    .eng-pillar-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 18px;
      height: 330px;
      padding-top: 8px;
    }
    .eng-pillar-card {
      min-width: 0;
      padding: 22px 22px 18px;
      border-top: 5px solid var(--engineering);
      background: rgba(255,255,255,.94);
      box-shadow: 0 8px 24px rgba(16,42,67,.06);
    }
    .eng-pillar-card.tone-2 { border-top-color: var(--product); }
    .eng-pillar-card.tone-3 { border-top-color: var(--future); }
    .eng-pillar-card > span {
      display: block;
      margin-bottom: 14px;
      color: var(--engineering);
      font-size: 11px;
      font-weight: 850;
      letter-spacing: .08em;
      white-space: nowrap;
    }
    .eng-pillar-card.tone-2 > span { color: var(--product); }
    .eng-pillar-card.tone-3 > span { color: var(--future); }
    .eng-pillar-card > strong { display: block; color: var(--ink); font-size: 23px; white-space: nowrap; }
    .eng-pillar-card > p { margin: 9px 0 15px; color: var(--muted); font-size: 15px; font-weight: 750; white-space: nowrap; }
    .eng-pillar-card ul { margin: 0; padding: 0; list-style: none; }
    .eng-pillar-card li {
      position: relative;
      min-height: 51px;
      padding: 11px 0 8px 18px;
      border-top: 1px solid var(--line);
      color: var(--ink);
      font-size: 14px;
      line-height: 1.35;
      font-weight: 650;
    }
    .eng-pillar-card li::before { content: ""; position: absolute; left: 0; top: 17px; width: 7px; height: 7px; border-radius: 50%; background: var(--engineering); }
    .eng-pillar-card.tone-2 li::before { background: var(--product); }
    .eng-pillar-card.tone-3 li::before { background: var(--future); }
    .eng-case-claim {
      display: flex;
      align-items: center;
      min-height: 70px;
      margin-top: 17px;
      padding: 14px 22px;
      border-left: 5px solid var(--engineering);
      background: var(--engineering-soft);
      color: #31564f;
      font-size: 15px;
      line-height: 1.45;
      font-weight: 650;
    }
    .eng-case-claim b { flex: 0 0 84px; color: var(--engineering); }

    .eng-rules-layout {
      display: grid;
      grid-template-columns: minmax(0, .82fr) minmax(0, 1.18fr);
      gap: 22px;
      height: 410px;
      padding-top: 8px;
    }
    .eng-rules-statement {
      padding: 28px 26px;
      border-top: 5px solid var(--engineering);
      background: linear-gradient(160deg, var(--engineering-soft), #fff 70%);
    }
    .eng-rules-statement > strong { display: block; color: var(--ink); font-size: 26px; line-height: 1.45; }
    .eng-rules-statement > p { margin: 22px 0; color: var(--muted); font-size: 15px; line-height: 1.65; }
    .eng-rules-statement > div { padding: 16px 18px; border-left: 4px solid var(--shared); background: var(--shared-soft); color: #71430c; font-size: 14px; line-height: 1.5; }
    .eng-rule-stack { display: grid; grid-template-rows: repeat(4, 1fr); gap: 10px; }
    .eng-rule-row {
      display: grid;
      grid-template-columns: 38px 220px minmax(0, 1fr);
      align-items: center;
      min-width: 0;
      padding: 0 16px;
      border-left: 4px solid var(--engineering);
      background: rgba(255,255,255,.94);
    }
    .eng-rule-row > span { color: #93a1ab; font-size: 11px; font-weight: 850; }
    .eng-rule-row > strong { color: var(--engineering); font-family: Consolas, "Microsoft YaHei", monospace; font-size: 13px; white-space: nowrap; }
    .eng-rule-row > p { margin: 0; color: var(--ink); font-size: 13px; line-height: 1.4; }

    .eng-skill-definition {
      display: flex;
      align-items: center;
      min-height: 48px;
      padding: 0 20px;
      border-left: 5px solid var(--engineering);
      background: var(--engineering-soft);
      color: #31564f;
      font-size: 15px;
    }
    .eng-skill-definition b { margin-right: 8px; color: var(--engineering); }
    .eng-skill-groups { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; height: 284px; margin-top: 14px; }
    .eng-skill-group { min-width: 0; padding: 16px 18px; border-top: 4px solid var(--engineering); background: rgba(255,255,255,.94); }
    .eng-skill-group.domain { border-top-color: var(--future); }
    .eng-skill-group-title { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
    .eng-skill-group-title strong { color: var(--ink); font-size: 17px; white-space: nowrap; }
    .eng-skill-group-title span { color: var(--muted); font-size: 9px; font-weight: 850; letter-spacing: .08em; white-space: nowrap; }
    .eng-skill-stack { display: grid; gap: 7px; }
    .eng-skill-row { display: grid; grid-template-columns: 220px minmax(0, 1fr); align-items: center; min-height: 48px; padding: 7px 10px; border: 1px solid var(--line); background: #f9fbfc; }
    .eng-skill-row strong { color: var(--engineering); font-family: Consolas, "Microsoft YaHei", monospace; font-size: 11px; white-space: nowrap; }
    .eng-skill-group.domain .eng-skill-row strong { color: var(--future); }
    .eng-skill-row p { margin: 0; color: var(--ink); font-size: 11px; line-height: 1.35; }
    .eng-skill-outcomes { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-top: 14px; }
    .eng-skill-outcomes > div { display: grid; grid-template-columns: 94px 1fr; align-items: center; min-height: 62px; padding: 0 15px; border-left: 4px solid var(--engineering); background: #fff; }
    .eng-skill-outcomes strong { color: var(--engineering); font-size: 14px; white-space: nowrap; }
    .eng-skill-outcomes span { color: var(--muted); font-size: 11px; line-height: 1.35; }

    .eng-evidence-image {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      height: 430px;
      padding: 12px;
      border: 1px solid #ccd8de;
      background: #fff;
      box-shadow: 0 8px 28px rgba(16,42,67,.08);
    }
    .eng-evidence-image img { display: block; width: 100%; height: 100%; object-fit: contain; }
    .eng-evidence-caption {
      display: flex;
      align-items: center;
      min-height: 44px;
      margin-top: 12px;
      padding: 0 18px;
      border-left: 4px solid var(--engineering);
      background: var(--engineering-soft);
      color: #31564f;
      font-size: 13px;
      font-weight: 750;
    }

    .engineering-image-focus-slide {
      padding: 0;
      background:
        linear-gradient(180deg, rgba(13,147,134,.045), transparent 24%),
        var(--paper);
    }
    .engineering-image-focus-header {
      position: absolute;
      top: 14px;
      left: 70px;
      right: 70px;
      z-index: 3;
      display: flex;
      align-items: center;
      height: 48px;
      padding-left: 16px;
      border-left: 5px solid var(--engineering);
    }
    .engineering-image-focus-header h1 {
      width: 1080px;
      color: var(--ink);
      font-size: 30px;
      line-height: 1.15;
      font-weight: 850;
      letter-spacing: -.3px;
      white-space: nowrap;
    }
    .engineering-image-focus-main {
      position: absolute;
      top: 68px;
      left: 64px;
      z-index: 2;
      display: flex;
      align-items: flex-start;
      justify-content: center;
      width: 1152px;
      height: 610px;
    }
    .engineering-image-focus-main .eng-evidence-image {
      width: 100%;
      height: 610px;
      padding: 0;
      border: 0;
      background: transparent;
      box-shadow: none;
    }
    .engineering-image-focus-main .eng-evidence-image img {
      width: auto;
      max-width: 100%;
      height: 100%;
      border: 1px solid #c8d4da;
      background: #fff;
      box-shadow: 0 12px 34px rgba(16,42,67,.16);
      object-fit: contain;
    }
    .engineering-image-focus-main .eng-evidence-caption {
      display: none;
    }
    .engineering-image-focus-slide footer {
      right: 32px;
      bottom: 12px;
      padding: 3px 7px;
      border-radius: 3px;
      background: rgba(244,247,249,.9);
    }

    .eng-artifact-flow {
      display: flex;
      align-items: stretch;
      height: 275px;
      padding-top: 8px;
    }
    .eng-artifact { flex: 1; min-width: 0; padding: 20px 15px; border-top: 5px solid var(--engineering); background: rgba(255,255,255,.94); }
    .eng-artifact:nth-of-type(3n+2) { border-top-color: var(--product); }
    .eng-artifact:nth-of-type(3n) { border-top-color: var(--future); }
    .eng-artifact > span { display: block; margin-bottom: 22px; color: #99a6b0; font-size: 11px; font-weight: 850; }
    .eng-artifact > strong { display: block; color: var(--ink); font-size: 18px; white-space: nowrap; }
    .eng-artifact > p { margin: 12px 0 0; color: var(--muted); font-size: 12px; line-height: 1.55; }
    .eng-artifact-flow > i { display: flex; flex: 0 0 26px; align-items: center; justify-content: center; color: #8fa4b5; font-size: 18px; font-style: normal; }
    .eng-artifact-evidence { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-top: 20px; }
    .eng-artifact-evidence > div { min-height: 102px; padding: 17px 20px; border-left: 5px solid var(--shared); background: var(--shared-soft); }
    .eng-artifact-evidence strong { display: block; margin-bottom: 8px; color: #8a5108; font-size: 15px; white-space: nowrap; }
    .eng-artifact-evidence p { margin: 0; color: #65431c; font-size: 13px; line-height: 1.5; }

    .eng-accumulation-layout { display: grid; grid-template-columns: 1.05fr .95fr; gap: 22px; height: 410px; padding-top: 8px; }
    .eng-asset-list { display: grid; grid-template-rows: repeat(4, 1fr) 72px; gap: 8px; min-width: 0; }
    .eng-asset-line { display: grid; grid-template-columns: 150px minmax(0, 1fr); align-items: center; min-width: 0; padding: 0 18px; border-left: 4px solid var(--engineering); background: #fff; }
    .eng-asset-line strong { color: var(--engineering); font-size: 18px; white-space: nowrap; }
    .eng-asset-line span { color: var(--ink); font-size: 12px; line-height: 1.4; }
    .eng-flywheel { display: flex; align-items: center; padding: 0 18px; border-left: 4px solid var(--shared); background: var(--shared-soft); color: #75440a; font-size: 13px; line-height: 1.45; font-weight: 750; }
    .eng-maturity-panel { min-width: 0; padding: 18px 20px; border-top: 5px solid var(--future); background: rgba(255,255,255,.94); }
    .eng-maturity-title { margin-bottom: 11px; color: var(--future); font-size: 17px; font-weight: 850; white-space: nowrap; }
    .eng-maturity-line { display: grid; grid-template-columns: 34px 92px minmax(0, 1fr); align-items: center; min-height: 72px; border-top: 1px solid var(--line); }
    .eng-maturity-line > span { color: #9ba8b2; font-size: 10px; font-weight: 850; }
    .eng-maturity-line > strong { color: var(--ink); font-size: 13px; white-space: nowrap; }
    .eng-maturity-line > p { margin: 0; color: var(--muted); font-size: 11px; line-height: 1.4; }

    /* Legacy Page 2 layout */
    .dual-loop-layout {
      display: grid;
      grid-template-columns: 1fr 130px 1fr;
      gap: 18px;
      height: 374px;
    }
    .loop-panel {
      position: relative;
      padding: 28px 28px 20px;
      border-top: 5px solid var(--product);
      background: rgba(255,255,255,.72);
    }
    .loop-panel.engineering { border-top-color: var(--engineering); }
    .loop-title { margin-bottom: 24px; font-size: 25px; font-weight: 850; }
    .loop-panel.product .loop-title { color: var(--product); }
    .loop-panel.engineering .loop-title { color: var(--engineering); }
    .loop-track { display: grid; gap: 9px; }
    .loop-step { display: grid; grid-template-columns: 42px 1fr; align-items: center; min-height: 42px; border-bottom: 1px solid var(--line); }
    .loop-index { color: #9aa7b2; font-size: 13px; font-weight: 800; }
    .loop-step strong { font-size: 19px; white-space: nowrap; }
    .loop-return {
      position: absolute;
      right: 20px;
      bottom: 14px;
      width: 116px;
      height: 26px;
      border-bottom: 2px solid currentColor;
      border-left: 2px solid currentColor;
      color: var(--product);
      opacity: .62;
    }
    .loop-panel.engineering .loop-return { color: var(--engineering); }
    .loop-return::before { content: "↺"; position: absolute; left: -8px; top: -14px; font-size: 24px; }
    .loop-return span { position: absolute; right: 0; top: 2px; font-size: 12px; font-weight: 700; }
    .current-handoff {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 14px;
    }
    .current-handoff > span { color: var(--muted); font-size: 13px; font-weight: 750; }
    .current-handoff strong {
      width: 108px;
      padding: 22px 10px;
      border: 1px solid var(--shared);
      background: var(--shared-soft);
      color: #9a5705;
      font-size: 19px;
      text-align: center;
    }
    .current-handoff i { width: 102px; height: 1px; background: var(--shared); }
    .conclusion-strip {
      height: 74px;
      margin-top: 18px;
      padding: 22px 28px;
      border-left: 5px solid var(--shared);
      background: #fff;
      color: var(--ink);
      font-size: 22px;
      font-weight: 800;
      white-space: nowrap;
    }

    /* Page 3 */
    .workspace-map { border-top: 1px solid var(--line); }
    .workspace-head, .workspace-row {
      display: grid;
      grid-template-columns: 136px 1fr 190px 1fr;
      align-items: stretch;
    }
    .workspace-head > div {
      padding: 12px 18px;
      color: var(--white);
      font-size: 18px;
      font-weight: 800;
      text-align: center;
      white-space: nowrap;
    }
    .workspace-head .product { background: var(--product); }
    .workspace-head .shared { background: var(--shared); }
    .workspace-head .engineering { background: var(--engineering); }
    .workspace-row { min-height: 58px; border-bottom: 1px solid var(--line); }
    .workspace-row > div { display: flex; align-items: center; padding: 12px 16px; }
    .row-label { color: var(--muted); font-size: 15px; font-weight: 800; }
    .row-value { border-left: 1px solid var(--line); font-size: 18px; font-weight: 700; white-space: nowrap; }
    .row-value.product { color: #2358b5; }
    .row-value.shared { justify-content: center; color: #9d5a08; text-align: center; }
    .row-value.engineering { color: #08786e; }
    .boundary-line {
      margin-top: 20px;
      padding: 17px 22px;
      border-left: 5px solid var(--shared);
      background: var(--shared-soft);
      color: #70400a;
      font-size: 20px;
      font-weight: 800;
      white-space: nowrap;
    }

    /* Pages 4 and 6 */
    .role-line {
      display: flex;
      align-items: center;
      gap: 16px;
      height: 44px;
      margin-bottom: 16px;
    }
    .role-line span { color: var(--muted); font-size: 13px; font-weight: 800; }
    .role-line strong { padding-left: 14px; border-left: 4px solid var(--product); font-size: 21px; white-space: nowrap; }
    .role-line.engineering strong { border-left-color: var(--engineering); }
    .staged-flow { height: 344px; }
    .flow-row { display: grid; align-items: stretch; gap: 12px; }
    .flow-row-four { grid-template-columns: 1fr 32px 1fr 32px 1fr 32px 1fr; }
    .flow-row-three { grid-template-columns: 1fr 32px 1fr 32px 1fr; width: 850px; margin: 0 auto; }
    .flow-node {
      min-height: 118px;
      padding: 17px 16px 14px;
      border-top: 5px solid var(--product);
      background: rgba(255,255,255,.86);
    }
    .flow-node.engineering { border-top-color: var(--engineering); }
    .flow-node > span { display: block; color: var(--product); font-size: 13px; font-weight: 850; }
    .flow-node.engineering > span { color: var(--engineering); }
    .flow-node strong { display: block; margin: 11px 0 7px; color: var(--ink); font-size: 20px; white-space: nowrap; }
    .flow-node small { display: block; height: 36px; color: var(--muted); font-size: 14px; line-height: 1.3; overflow: hidden; }
    .flow-arrow { position: relative; }
    .flow-arrow::before { content: ""; position: absolute; left: 4px; right: 4px; top: 58px; height: 2px; background: #9fb5ca; }
    .flow-arrow::after { content: ""; position: absolute; right: 2px; top: 53px; border-left: 8px solid #9fb5ca; border-top: 6px solid transparent; border-bottom: 6px solid transparent; }
    .flow-gate {
      display: grid;
      grid-template-columns: 1fr auto 1fr;
      align-items: center;
      gap: 18px;
      height: 76px;
      width: 850px;
      margin: 0 auto;
    }
    .flow-gate span { height: 1px; background: var(--shared); }
    .flow-gate strong {
      padding: 9px 18px;
      background: var(--shared-soft);
      color: #995805;
      font-size: 16px;
      white-space: nowrap;
    }
    .completion-line {
      height: 54px;
      margin-top: 8px;
      padding: 15px 20px;
      border-left: 5px solid var(--product);
      background: var(--product-soft);
      color: #244d94;
      font-size: 18px;
      font-weight: 800;
      white-space: nowrap;
    }
    .completion-line.engineering { border-left-color: var(--engineering); background: var(--engineering-soft); color: #086c63; }

    /* Page 5 */
    .product-evidence-layout { display: grid; grid-template-columns: 48% 52%; gap: 44px; height: 396px; }
    .metric-rail { position: relative; padding-left: 22px; }
    .metric-rail::before { content: ""; position: absolute; left: 3px; top: 20px; bottom: 20px; width: 3px; background: linear-gradient(var(--product), var(--engineering)); }
    .metric-line {
      position: relative;
      display: grid;
      grid-template-columns: 96px 1fr;
      align-items: center;
      min-height: 92px;
      border-bottom: 1px solid var(--line);
    }
    .metric-line::before { content: ""; position: absolute; left: -24px; top: 42px; width: 9px; height: 9px; border-radius: 50%; background: var(--product); }
    .metric-line:nth-child(n+3)::before { background: var(--engineering); }
    .metric-line > strong { color: var(--product); font-size: 46px; line-height: 1; }
    .metric-line:nth-child(n+3) > strong { color: var(--engineering); }
    .metric-line b { display: block; margin-bottom: 5px; font-size: 19px; white-space: nowrap; }
    .metric-line span { display: block; color: var(--muted); font-size: 14px; white-space: nowrap; }
    .transformation-label { margin-bottom: 14px; color: var(--muted); font-size: 14px; font-weight: 800; }
    .transformation { min-height: 116px; padding: 16px 0; border-bottom: 1px solid var(--line); }
    .transform-pair { display: grid; grid-template-columns: 105px 34px 1fr; align-items: center; }
    .transform-pair span { color: var(--muted); font-size: 17px; font-weight: 700; white-space: nowrap; }
    .transform-pair i { color: var(--shared); font-size: 24px; font-style: normal; }
    .transform-pair strong { color: var(--product); font-size: 22px; white-space: nowrap; }
    .transformation p { margin: 8px 0 0 139px; color: var(--ink); font-size: 15px; line-height: 1.35; }
    .boundary-alert {
      height: 58px;
      margin-top: 16px;
      padding: 17px 22px;
      border-left: 5px solid var(--danger);
      background: var(--danger-soft);
      color: #8f352e;
      font-size: 18px;
      font-weight: 800;
      white-space: nowrap;
    }

    /* Page 7 */
    .effect-pipeline {
      display: grid;
      grid-template-columns: 245px 48px 430px 48px 245px;
      align-items: stretch;
      height: 280px;
    }
    .effect-column { padding: 24px 22px; background: rgba(255,255,255,.85); }
    .effect-column.input { border-top: 5px solid var(--product); }
    .effect-column.controls { border: 2px solid var(--engineering); background: #f9fffd; }
    .effect-column.output { border-top: 5px solid var(--engineering); }
    .effect-column > strong { display: block; margin-bottom: 16px; font-size: 21px; white-space: nowrap; }
    .effect-list { margin: 0; padding: 0; list-style: none; }
    .effect-list li { min-height: 38px; padding: 8px 0; border-bottom: 1px solid var(--line); color: var(--ink); font-size: 16px; font-weight: 650; white-space: nowrap; }
    .pipeline-arrow { position: relative; }
    .pipeline-arrow::before { content: ""; position: absolute; left: 7px; right: 7px; top: 50%; height: 2px; background: #92aaa8; }
    .pipeline-arrow::after { content: ""; position: absolute; right: 4px; top: calc(50% - 5px); border-left: 8px solid #92aaa8; border-top: 6px solid transparent; border-bottom: 6px solid transparent; }
    .effect-meanings { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; margin-top: 18px; }
    .meaning-line { display: flex; align-items: center; gap: 14px; padding-top: 13px; border-top: 3px solid var(--engineering); }
    .meaning-line span { color: var(--engineering); font-size: 14px; font-weight: 850; }
    .meaning-line strong { font-size: 18px; white-space: nowrap; }
    .feedback-split { display: flex; gap: 20px; margin-top: 20px; }
    .feedback-split span { flex: 1; padding: 13px 18px; background: var(--engineering-soft); color: #086d63; font-size: 16px; font-weight: 750; white-space: nowrap; }
    .feedback-split span:last-child { background: var(--shared-soft); color: #935204; }

    /* Page 8 */
    .handoff-layout { display: grid; grid-template-columns: 310px 225px 1fr; gap: 28px; height: 330px; }
    .column-caption { margin-bottom: 14px; padding-bottom: 8px; border-bottom: 4px solid currentColor; font-size: 18px; font-weight: 850; }
    .column-caption.product { color: var(--product); }
    .column-caption.engineering { color: var(--engineering); }
    .handoff-group { display: grid; grid-template-columns: 108px 1fr; align-items: center; min-height: 62px; border-bottom: 1px solid var(--line); }
    .handoff-group strong { color: var(--product); font-size: 16px; white-space: nowrap; }
    .handoff-group span { color: var(--ink); font-size: 15px; line-height: 1.4; }
    .handoff-folder {
      position: relative;
      align-self: center;
      min-height: 250px;
      padding: 38px 25px 24px;
      border: 2px solid var(--shared);
      background: var(--shared-soft);
    }
    .folder-tab { position: absolute; left: -2px; top: -24px; width: 112px; height: 24px; border: 2px solid var(--shared); border-bottom: 0; background: var(--shared-soft); }
    .handoff-folder > strong { display: block; margin-bottom: 18px; color: #8e5004; font-size: 21px; white-space: nowrap; }
    .handoff-folder > span { display: block; padding: 9px 0; border-bottom: 1px solid rgba(157,90,8,.22); color: #70400a; font-size: 16px; white-space: nowrap; }
    .engineering-steps { display: flex; align-items: center; height: 244px; }
    .engineering-step { flex: 1; min-width: 0; padding: 20px 10px; border-top: 4px solid var(--engineering); background: rgba(255,255,255,.82); text-align: center; }
    .engineering-step b { display: block; margin-bottom: 16px; color: var(--engineering); font-size: 13px; }
    .engineering-step span { display: block; height: 50px; font-size: 15px; line-height: 1.5; font-weight: 750; overflow: hidden; }
    .engineering-steps > i { flex: 0 0 18px; color: var(--engineering); font-style: normal; font-size: 20px; text-align: center; }
    .handoff-feedback { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-top: 24px; }
    .feedback-route { display: grid; grid-template-columns: 112px 24px 1fr; align-items: center; min-height: 60px; padding: 0 18px; }
    .feedback-route.engineering { background: var(--engineering-soft); color: #086d63; }
    .feedback-route.shared { background: var(--shared-soft); color: #935204; }
    .feedback-route strong, .feedback-route p { margin: 0; font-size: 16px; white-space: nowrap; }

    /* Page 9 */
    .trace-chain { display: flex; align-items: center; height: 128px; }
    .trace-node {
      flex: 1 1 0;
      min-width: 0;
      padding: 24px 8px;
      border-top: 5px solid var(--product);
      background: rgba(255,255,255,.86);
      font-size: 17px;
      font-weight: 800;
      text-align: center;
      white-space: nowrap;
    }
    .trace-node.engineering { border-top-color: var(--engineering); }
    .trace-node.shared { border-top-color: var(--shared); }
    .trace-link { position: relative; flex: 0 0 32px; height: 2px; background: #91a5b6; }
    .trace-link::after { content: ""; position: absolute; right: -1px; top: -5px; border-left: 8px solid #91a5b6; border-top: 6px solid transparent; border-bottom: 6px solid transparent; }
    .trace-link.gap { height: 0; border-top: 2px dashed var(--danger); background: transparent; }
    .trace-link.gap::after { border-left-color: var(--danger); }
    .trace-link.gap::before { content: "×"; position: absolute; left: 9px; top: -18px; z-index: 2; color: var(--danger); background: var(--paper); font-size: 20px; font-weight: 900; }
    .break-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 24px; margin-top: 26px; }
    .break-item { min-height: 132px; padding-top: 16px; border-top: 4px solid var(--danger); }
    .break-item span { display: block; margin-bottom: 10px; color: var(--danger); font-size: 14px; font-weight: 850; }
    .break-item p { margin: 0; color: var(--ink); font-size: 17px; line-height: 1.5; font-weight: 750; }
    .outcome-line { display: flex; gap: 14px; margin-top: 26px; }
    .outcome-line span { padding: 12px 18px; font-size: 16px; font-weight: 800; white-space: nowrap; }
    .outcome-line .positive { color: #08766c; background: var(--engineering-soft); }
    .outcome-line .negative { flex: 1; color: #943a32; background: var(--danger-soft); }

    /* Page 10 */
    .identity-bar { display: grid; grid-template-columns: 1.15fr .7fr 1fr 1.1fr .9fr; gap: 1px; background: var(--line); }
    .identity-field { min-height: 66px; padding: 11px 14px; background: #fff; }
    .identity-field span { display: block; margin-bottom: 5px; color: var(--muted); font-size: 12px; font-weight: 750; white-space: nowrap; }
    .identity-field strong { display: block; color: var(--ink); font-size: 16px; white-space: nowrap; }
    .status-rail { display: flex; align-items: flex-start; margin-top: 24px; }
    .status-step {
      position: relative;
      flex: 1;
      min-width: 0;
      padding-top: 33px;
      color: #8795a1;
      text-align: center;
    }
    .status-step::before {
      content: "";
      position: absolute;
      left: 50%;
      top: 4px;
      z-index: 2;
      width: 18px;
      height: 18px;
      transform: translateX(-50%);
      border: 3px solid #b9c4cd;
      border-radius: 50%;
      background: var(--paper);
    }
    .status-step::after { content: ""; position: absolute; left: 50%; right: -50%; top: 13px; height: 2px; background: #c7d0d7; }
    .status-step:last-child::after { display: none; }
    .status-step.done::before { border-color: var(--engineering); background: var(--engineering); }
    .status-step.done::after { background: var(--engineering); }
    .status-step.active::before { width: 24px; height: 24px; top: 1px; border-color: var(--shared); background: var(--shared-soft); box-shadow: 0 0 0 6px rgba(240,161,59,.14); }
    .status-step i { display: none; }
    .status-step span { display: block; font-size: 13px; line-height: 1.3; font-weight: 750; }
    .status-step.done span { color: var(--engineering); }
    .status-step.active span { color: #995805; font-weight: 850; }
    .asset-lanes { display: grid; gap: 10px; margin-top: 24px; }
    .asset-lane { display: grid; grid-template-columns: 142px 1fr; align-items: center; min-height: 58px; border-left: 5px solid var(--product); background: #fff; }
    .asset-lane.engineering { border-left-color: var(--engineering); }
    .asset-lane.shared { border-left-color: var(--shared); }
    .asset-lane > strong { padding: 0 18px; font-size: 16px; white-space: nowrap; }
    .asset-lane > div { display: flex; align-items: center; gap: 0; }
    .asset-lane span { position: relative; min-width: 150px; padding: 8px 24px; color: var(--ink); font-size: 15px; font-weight: 700; white-space: nowrap; text-align: center; }
    .asset-lane span:not(:last-child)::after { content: "→"; position: absolute; right: -5px; color: #95a4b0; }
    .target-summary { margin-top: 18px; color: var(--future); font-size: 19px; font-weight: 850; text-align: center; white-space: nowrap; }

    /* Unified OpenSpec target */
    .unified-spec-layout { height: 466px; padding-top: 2px; }
    .unified-spec-main {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 42px minmax(0, 1.2fr) 42px minmax(0, 1fr);
      align-items: stretch;
      height: 306px;
    }
    .unified-side {
      display: flex;
      flex-direction: column;
      min-width: 0;
      padding: 17px 18px 15px;
      border-top: 5px solid var(--product);
      background: rgba(255,255,255,.88);
      box-shadow: 0 8px 24px rgba(17,42,64,.06);
    }
    .unified-side.engineering { border-top-color: var(--engineering); }
    .unified-side-head > span {
      display: block;
      margin-bottom: 4px;
      color: var(--product);
      font-size: 11px;
      font-weight: 900;
      letter-spacing: .11em;
    }
    .unified-side.engineering .unified-side-head > span { color: var(--engineering); }
    .unified-side-head > strong { display: block; color: var(--ink); font-size: 24px; line-height: 1.15; }
    .unified-side-head > p { margin: 6px 0 0; color: var(--muted); font-size: 14px; font-weight: 700; }
    .unified-stage-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      margin-top: 15px;
    }
    .unified-stage {
      display: flex;
      align-items: center;
      min-width: 0;
      min-height: 42px;
      padding: 8px 10px;
      border: 1px solid #bfd0eb;
      background: var(--product-soft);
    }
    .unified-stage.engineering { border-color: #b7ddd7; background: var(--engineering-soft); }
    .unified-stage span { flex: 0 0 22px; color: #7793ba; font-size: 10px; font-weight: 900; }
    .unified-stage.engineering span { color: #5faaa0; }
    .unified-stage strong { min-width: 0; color: #174e9f; font-size: 13px; white-space: nowrap; }
    .unified-stage.engineering strong { color: #08776d; }
    .unified-side.engineering .unified-stage:last-child { grid-column: 1 / -1; }
    .unified-responsibility {
      margin-top: auto;
      padding-top: 12px;
      border-top: 1px solid var(--line);
      color: var(--ink);
      font-size: 13px;
      line-height: 1.35;
      font-weight: 800;
      text-align: center;
    }
    .unified-forward {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      color: #8499aa;
    }
    .unified-forward span { font-size: 31px; line-height: 1; font-weight: 300; }
    .unified-forward small { margin-top: 7px; color: var(--muted); font-size: 11px; font-weight: 800; }
    .unified-core {
      position: relative;
      display: flex;
      flex-direction: column;
      align-items: center;
      min-width: 0;
      padding: 20px 20px 17px;
      border: 2px solid var(--shared);
      background: linear-gradient(145deg, rgba(255,244,225,.98), rgba(255,255,255,.90));
      box-shadow: 0 12px 28px rgba(240,161,59,.14);
      overflow: hidden;
    }
    .unified-core::before {
      content: "";
      position: absolute;
      left: 0;
      right: 0;
      top: 0;
      height: 6px;
      background: linear-gradient(90deg, var(--product), var(--shared), var(--engineering));
    }
    .unified-core-eyebrow {
      margin-top: 2px;
      color: #a4620c;
      font-size: 11px;
      font-weight: 900;
      letter-spacing: .11em;
      white-space: nowrap;
    }
    .unified-core-title { margin-top: 9px; color: var(--ink); font-size: 25px; line-height: 1.15; text-align: center; }
    .unified-core-subtitle { margin: 7px 0 0; color: var(--muted); font-size: 14px; font-weight: 700; text-align: center; }
    .unified-artifacts {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      width: 100%;
      margin-top: 17px;
    }
    .unified-artifacts span {
      min-width: 0;
      padding: 9px 8px;
      border: 1px solid #efc889;
      background: rgba(255,255,255,.72);
      color: #975b0d;
      font-size: 13px;
      font-weight: 850;
      text-align: center;
      white-space: nowrap;
    }
    .unified-artifacts span:last-child { grid-column: 1 / -1; }
    .unified-identity {
      width: 100%;
      margin-top: auto;
      padding: 9px 10px;
      background: rgba(240,161,59,.14);
      color: #8f5509;
      font-size: 13px;
      font-weight: 850;
      text-align: center;
      white-space: nowrap;
    }
    .unified-feedback {
      display: grid;
      grid-template-columns: 44px 92px 1fr;
      align-items: center;
      min-height: 60px;
      margin-top: 14px;
      border-left: 5px solid var(--shared);
      background: var(--shared-soft);
    }
    .feedback-loop { color: var(--shared); font-size: 30px; font-weight: 800; text-align: center; }
    .unified-feedback strong { color: #965704; font-size: 15px; white-space: nowrap; }
    .unified-feedback p { margin: 0; color: #784b11; font-size: 15px; line-height: 1.35; font-weight: 750; }
    .unified-conclusion {
      margin-top: 12px;
      padding: 12px 18px;
      border: 1px solid #c7d6e2;
      background: rgba(255,255,255,.76);
      color: var(--ink);
      font-size: 17px;
      line-height: 1.35;
      font-weight: 850;
      text-align: center;
      white-space: nowrap;
    }

    /* Next-stage improvement plan */
    .improvement-plan-layout { height: 466px; }
    .improvement-plan-start {
      display: grid;
      grid-template-columns: 92px 1.55fr 1.08fr;
      align-items: stretch;
      min-height: 70px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,.80);
    }
    .improvement-plan-start-label {
      display: flex;
      align-items: center;
      justify-content: center;
      border-left: 5px solid var(--shared);
      background: var(--shared-soft);
      color: #955706;
      font-size: 14px;
      font-weight: 900;
      white-space: nowrap;
    }
    .improvement-plan-current-flow {
      display: flex;
      align-items: center;
      gap: 6px;
      min-width: 0;
      padding: 11px 13px;
    }
    .improvement-plan-current-flow span {
      flex: 1;
      min-width: 0;
      padding: 8px 6px;
      border: 1px solid #d4dee7;
      background: #f7f9fb;
      color: var(--ink);
      font-size: 11px;
      font-weight: 800;
      text-align: center;
      white-space: nowrap;
    }
    .improvement-plan-current-flow i { color: #93a6b5; font-size: 14px; font-style: normal; }
    .improvement-plan-issues {
      display: flex;
      flex-direction: column;
      justify-content: center;
      gap: 5px;
      padding: 9px 13px;
      border-left: 1px solid var(--line);
      background: rgba(252,235,232,.55);
    }
    .improvement-plan-issues span {
      position: relative;
      padding-left: 13px;
      color: #93443d;
      font-size: 11px;
      line-height: 1.28;
      font-weight: 750;
    }
    .improvement-plan-issues span::before {
      content: "";
      position: absolute;
      left: 0;
      top: 5px;
      width: 5px;
      height: 5px;
      border-radius: 50%;
      background: var(--danger);
    }
    .improvement-plan-tracks {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
      height: 229px;
      margin-top: 11px;
    }
    .improvement-plan-track {
      min-width: 0;
      padding: 13px 15px 12px;
      border-top: 5px solid var(--product);
      background: rgba(255,255,255,.90);
      box-shadow: 0 7px 20px rgba(20,48,70,.06);
    }
    .improvement-plan-track.mixed {
      border-image: linear-gradient(90deg, var(--product), var(--engineering)) 1;
    }
    .improvement-plan-track.testing {
      border-image: linear-gradient(90deg, var(--future), var(--shared)) 1;
    }
    .improvement-plan-track-head { display: flex; align-items: flex-start; gap: 12px; }
    .improvement-plan-track-head > span {
      flex: 0 0 34px;
      color: var(--product);
      font-size: 14px;
      line-height: 30px;
      font-weight: 900;
      text-align: center;
      border: 1px solid #b9cdef;
      background: var(--product-soft);
    }
    .improvement-plan-track.testing .improvement-plan-track-head > span {
      color: var(--future);
      border-color: #cbc2ef;
      background: var(--future-soft);
    }
    .improvement-plan-track-head > div { min-width: 0; }
    .improvement-plan-track-head strong { display: block; color: var(--ink); font-size: 19px; line-height: 1.1; }
    .improvement-plan-track-head p { margin: 4px 0 0; color: var(--muted); font-size: 11px; font-weight: 700; }
    .improvement-plan-modules {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 7px;
      margin-top: 11px;
    }
    .improvement-plan-module {
      min-width: 0;
      min-height: 91px;
      padding: 10px 9px;
      border: 1px solid #c7d6eb;
      background: rgba(230,238,252,.62);
    }
    .improvement-plan-track.testing .improvement-plan-module {
      border-color: #d3cbed;
      background: linear-gradient(145deg, rgba(236,233,251,.70), rgba(255,241,221,.55));
    }
    .improvement-plan-module strong { display: block; color: #1654aa; font-size: 13px; line-height: 1.15; text-align: center; }
    .improvement-plan-track.testing .improvement-plan-module strong { color: #5b48b7; }
    .improvement-plan-module p {
      margin: 8px 0 0;
      color: #516679;
      font-size: 10.5px;
      line-height: 1.38;
      font-weight: 700;
      text-align: center;
    }
    .improvement-plan-track-output {
      display: grid;
      grid-template-columns: 55px 1fr;
      align-items: center;
      min-height: 37px;
      margin-top: 9px;
      padding: 6px 9px;
      border-left: 4px solid var(--engineering);
      background: var(--engineering-soft);
    }
    .improvement-plan-track.testing .improvement-plan-track-output {
      border-left-color: var(--shared);
      background: var(--shared-soft);
    }
    .improvement-plan-track-output small { color: var(--muted); font-size: 10px; font-weight: 850; }
    .improvement-plan-track-output strong { color: var(--ink); font-size: 11.5px; white-space: nowrap; }
    .improvement-plan-roadmap {
      display: flex;
      align-items: stretch;
      min-height: 78px;
      margin-top: 11px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,.78);
    }
    .improvement-plan-roadmap-label {
      display: flex;
      flex: 0 0 86px;
      align-items: center;
      justify-content: center;
      border-left: 5px solid var(--future);
      color: var(--future);
      font-size: 14px;
      font-weight: 900;
    }
    .improvement-plan-roadmap-step {
      display: flex;
      flex: 1;
      flex-direction: column;
      justify-content: center;
      min-width: 0;
      padding: 8px 13px;
    }
    .improvement-plan-roadmap-step small { color: var(--future); font-size: 10px; font-weight: 900; }
    .improvement-plan-roadmap-step strong { margin-top: 2px; color: var(--ink); font-size: 13px; white-space: nowrap; }
    .improvement-plan-roadmap-step p { margin: 4px 0 0; color: var(--muted); font-size: 10.5px; line-height: 1.25; font-weight: 700; }
    .improvement-plan-roadmap > i {
      display: flex;
      align-items: center;
      color: #98a9b6;
      font-size: 18px;
      font-style: normal;
    }
    .improvement-plan-conclusion {
      margin-top: 10px;
      padding: 10px 16px;
      border-left: 5px solid var(--shared);
      background: linear-gradient(90deg, var(--shared-soft), rgba(230,238,252,.68));
      color: var(--ink);
      font-size: 15px;
      line-height: 1.3;
      font-weight: 850;
      text-align: center;
      white-space: nowrap;
    }

    /* Page 11 */
    .swimlane-wrap { position: relative; padding-bottom: 34px; }
    .swimlane-grid {
      display: grid;
      grid-template-columns: 142px repeat(var(--phase-count), 1fr);
      border-top: 1px solid var(--line);
      border-left: 1px solid var(--line);
    }
    .swim-corner, .phase-head, .lane-role, .lane-cell {
      display: flex;
      align-items: center;
      justify-content: center;
      min-width: 0;
      border-right: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
    }
    .swim-corner { min-height: 42px; color: var(--muted); font-size: 12px; font-weight: 800; }
    .phase-head { min-height: 42px; color: var(--ink); font-size: 14px; font-weight: 850; white-space: nowrap; }
    .lane-role { min-height: 73px; padding: 0 12px; color: var(--white); font-size: 15px; font-weight: 850; white-space: nowrap; }
    .lane-role.product { background: var(--product); }
    .lane-role.shared { background: var(--shared); }
    .lane-role.engineering { background: var(--engineering); }
    .lane-role.agent { background: var(--future); }
    .lane-cell {
      min-height: 73px;
      padding: 10px 9px;
      color: var(--ink);
      background: rgba(255,255,255,.72);
      font-size: 13px;
      line-height: 1.35;
      font-weight: 650;
      text-align: center;
      overflow: hidden;
    }
    .lane-cell.product { background: rgba(230,238,252,.72); }
    .lane-cell.shared { background: rgba(255,241,221,.72); }
    .lane-cell.engineering { background: rgba(223,242,238,.72); }
    .lane-cell.agent { background: rgba(236,233,251,.72); }
    .gate-row { position: absolute; left: 142px; right: 0; bottom: 0; height: 28px; }
    .gate-row span {
      position: absolute;
      left: calc((var(--gate-after) + 1) / 6 * 100% - 72px);
      min-width: 144px;
      padding: 5px 9px;
      background: var(--shared-soft);
      color: #955404;
      font-size: 12px;
      font-weight: 800;
      text-align: center;
      white-space: nowrap;
    }
    .swim-feedback { display: flex; gap: 20px; margin-top: 18px; }
    .swim-feedback span { flex: 1; padding: 12px 18px; border-left: 4px solid var(--danger); background: var(--danger-soft); color: #8f362e; font-size: 15px; font-weight: 750; white-space: nowrap; }
    .swim-feedback span:last-child { border-left-color: var(--shared); background: var(--shared-soft); color: #915203; }

    /* Page 12 */
    .control-plane {
      display: grid;
      grid-template-columns: 150px repeat(6, 1fr);
      align-items: center;
      height: 58px;
      background: var(--navy);
      color: var(--white);
    }
    .control-plane strong, .control-plane span { padding: 0 14px; white-space: nowrap; }
    .control-plane strong { font-size: 17px; }
    .control-plane span { border-left: 1px solid rgba(255,255,255,.15); color: #d6e1e8; font-size: 13px; text-align: center; }
    .asset-space { display: grid; grid-template-columns: 1fr 250px 1fr; gap: 34px; align-items: stretch; height: 278px; margin-top: 18px; }
    .asset-tree { padding: 24px 28px; background: #fff; border-top: 5px solid var(--product); }
    .asset-tree.engineering { border-top-color: var(--engineering); }
    .asset-tree > strong { display: block; margin-bottom: 14px; color: var(--product); font-size: 20px; white-space: nowrap; }
    .asset-tree.engineering > strong { color: var(--engineering); }
    .tree-file { height: 38px; padding: 8px 0; border-bottom: 1px solid var(--line); color: var(--ink); font-family: Consolas, "Microsoft YaHei", monospace; font-size: 15px; white-space: nowrap; }
    .shared-assets { display: flex; flex-direction: column; justify-content: center; gap: 18px; }
    .shared-file { padding: 18px 16px; border: 1px solid var(--shared); background: var(--shared-soft); text-align: center; }
    .shared-file strong { display: block; margin-bottom: 7px; color: #925203; font-family: Consolas, monospace; font-size: 16px; white-space: nowrap; }
    .shared-file span { display: block; color: #74430b; font-size: 13px; line-height: 1.4; }
    .capability-layer {
      display: grid;
      grid-template-columns: 155px repeat(5, 1fr);
      align-items: center;
      height: 64px;
      margin-top: 18px;
      border: 1px solid #d5cfef;
      background: var(--future-soft);
    }
    .capability-layer strong { padding-left: 18px; color: var(--future); font-size: 16px; white-space: nowrap; }
    .capability-layer span { padding: 0 10px; border-left: 1px solid #c8c0ec; color: #4d418e; font-size: 13px; font-weight: 750; text-align: center; }
    .build-summary { margin-top: 15px; color: var(--future); font-size: 17px; font-weight: 850; text-align: center; white-space: nowrap; }

    /* Page 13 */
    .closing {
      color: var(--white);
      background:
        radial-gradient(circle at 84% 12%, rgba(103,88,214,.22), transparent 28%),
        linear-gradient(125deg, #061421, #0b2337);
    }
    .closing .page-grid {
      opacity: .45;
      background-image:
        linear-gradient(rgba(255,255,255,.045) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.045) 1px, transparent 1px);
      mask-image: none;
    }
    .closing h1 { color: var(--white); }
    .closing .slide-message { color: #c6d3dd; }
    .closing .section-label { color: #aca1ff; }
    .closing .evidence-label, .closing footer { color: #8297a8; }
    .closing footer b { color: #c6d3dd; }
    .scope-note {
      height: 42px;
      padding: 11px 16px;
      border-left: 4px solid var(--shared);
      background: rgba(240,161,59,.12);
      color: #ffd18b;
      font-size: 15px;
      font-weight: 800;
      white-space: nowrap;
    }
    .completion-layout { display: grid; grid-template-columns: 60% 40%; gap: 32px; height: 292px; margin-top: 18px; }
    .milestone-path { display: flex; align-items: center; }
    .milestone { flex: 1; min-width: 0; text-align: center; }
    .milestone span {
      display: block;
      width: 34px;
      height: 34px;
      margin: 0 auto 12px;
      border: 2px solid #8073e7;
      border-radius: 50%;
      color: #c9c2ff;
      font-size: 13px;
      font-weight: 850;
      line-height: 30px;
    }
    .milestone strong { display: block; height: 66px; color: #e9eef2; font-size: 14px; line-height: 1.45; overflow: hidden; }
    .milestone-link { flex: 0 0 22px; height: 2px; margin-top: -48px; background: #5f56ad; }
    .criteria-list { padding: 18px 20px; border: 1px solid rgba(255,255,255,.14); background: rgba(255,255,255,.05); }
    .criteria-title { margin-bottom: 10px; color: #aaa0ff; font-size: 15px; font-weight: 850; }
    .criterion { display: grid; grid-template-columns: 28px 1fr; align-items: center; min-height: 42px; border-bottom: 1px solid rgba(255,255,255,.1); }
    .criterion i { color: #7bd4c9; font-style: normal; font-size: 16px; font-weight: 900; }
    .criterion span { color: #e7edf1; font-size: 14px; white-space: nowrap; }
    .decision-outcomes { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-top: 16px; }
    .decision { display: grid; grid-template-columns: 86px 1fr; align-items: center; min-height: 58px; padding: 0 17px; border-left: 5px solid #71c9bd; background: rgba(255,255,255,.07); }
    .decision.adjust { border-left-color: var(--shared); }
    .decision.stop { border-left-color: var(--danger); }
    .decision strong { color: var(--white); font-size: 16px; white-space: nowrap; }
    .decision span { color: #b9c8d2; font-size: 14px; white-space: nowrap; }
    .closing-line { margin-top: 17px; color: #a99fff; font-size: 18px; font-weight: 850; text-align: center; white-space: nowrap; }

    /* Generic fallback */
    .generic-layout { display: grid; gap: 22px; padding-top: 20px; }
    .generic-point { display: grid; grid-template-columns: 54px 1fr; align-items: center; min-height: 90px; border-bottom: 1px solid var(--line); }
    .generic-point span { color: var(--shared); font-size: 16px; font-weight: 850; }
    .generic-point strong { font-size: 25px; white-space: nowrap; }

    @page { size: 1280px 720px; margin: 0; }
    @media print {
      html, body { width: auto; height: auto; overflow: visible; background: white; }
      .deck { width: auto; height: auto; overflow: visible; background: white; }
      .slide {
        position: relative;
        left: auto;
        top: auto;
        display: block;
        opacity: 1;
        visibility: visible;
        pointer-events: auto;
        transform: none !important;
        margin: 0;
        box-shadow: none;
      }
    }
  </style>
</head>
<body>
  <main class="deck" aria-label="${esc(spec.deck.title)}">
    ${slides}
  </main>
  <script>
    const deck = document.querySelector('.deck');
    const slideItems = Array.from(document.querySelectorAll('.slide'));
    let activeIndex = 0;
    let wheelDelta = 0;
    let wheelGestureConsumed = false;
    let wheelResetTimer = null;
    let touchStartY = null;

    function resizeStage() {
      const scale = Math.min(window.innerWidth / 1280, window.innerHeight / 720) * 0.965;
      document.documentElement.style.setProperty('--scale', String(Math.max(0.2, scale)));
    }

    function renderSlide(index) {
      activeIndex = Math.max(0, Math.min(slideItems.length - 1, index));
      slideItems.forEach((slide, slideIndex) => {
        const active = slideIndex === activeIndex;
        slide.classList.toggle('active', active);
        slide.setAttribute('aria-hidden', active ? 'false' : 'true');
      });
    }

    function move(direction) {
      renderSlide(activeIndex + direction);
    }

    deck?.addEventListener('wheel', (event) => {
      event.preventDefault();
      if (wheelResetTimer !== null) window.clearTimeout(wheelResetTimer);
      wheelResetTimer = window.setTimeout(() => {
        wheelGestureConsumed = false;
        wheelDelta = 0;
        wheelResetTimer = null;
      }, 180);

      if (wheelGestureConsumed) return;
      wheelDelta += event.deltaY;
      if (Math.abs(wheelDelta) < 24) return;

      wheelGestureConsumed = true;
      move(wheelDelta > 0 ? 1 : -1);
      wheelDelta = 0;
    }, { passive: false });

    deck?.addEventListener('touchstart', (event) => {
      touchStartY = event.touches[0]?.clientY ?? null;
    }, { passive: true });

    deck?.addEventListener('touchend', (event) => {
      if (touchStartY === null) return;
      const endY = event.changedTouches[0]?.clientY ?? touchStartY;
      const delta = touchStartY - endY;
      if (Math.abs(delta) > 45) move(delta > 0 ? 1 : -1);
      touchStartY = null;
    }, { passive: true });

    window.addEventListener('resize', resizeStage);
    resizeStage();
    renderSlide(0);
  </script>
</body>
</html>`;

writeText(["output", "react", "index.html"], html);
console.log("Generated output/react/index.html.");

