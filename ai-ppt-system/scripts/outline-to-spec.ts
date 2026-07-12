import { ALLOWED_TYPES, DeckSpec, DeckTemplate, SlideSpec, SlideType, charLen, compact, limitText, readText, writeJson } from "./shared.ts";

const outline = readText("input", "outline.md");

function field(label: string, fallback: string) {
  const pattern = new RegExp(`${label}\\s*[：:]\\s*([^\\n]+)`, "i");
  const match = outline.match(pattern);
  return compact(match?.[1] ?? fallback);
}

function section(name: string) {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(`^##\\s+${escaped}\\s*$([\\s\\S]*?)(?=^##\\s+|\\s*$)`, "m");
  const match = outline.match(pattern);
  return match?.[1]?.trim() ?? "";
}

function parsePageCount(value: string) {
  const match = value.match(/\d+/);
  return match ? Math.max(4, Math.min(24, Number(match[0]))) : 8;
}

function parseFormats(value: string) {
  const formats = value
    .split(/[、,，/ ]+/)
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
  return formats.length ? formats : ["pptx", "html", "pdf", "png", "marp"];
}

function inferTemplate(style: string): DeckTemplate | undefined {
  const source = `${outline}\n${style}`;
  const wantsCompany = /公司\s*(?:ppt|PPT)?\s*模板|公司PPT模板|公司ppt模板|company\s*ppt\s*template/i.test(source);
  if (!wantsCompany) {
    return undefined;
  }
  return {
    id: "company",
    variant: /深色|暗色|投屏版|\bdark\b/i.test(source) ? "dark" : "light"
  };
}

function contentItems() {
  const content = section("内容大纲");
  const lines = content
    .split(/\r?\n/)
    .map((line: string) => compact(line.replace(/^[-*]\s*/, "").replace(/^\d+[.、)]\s*/, "")))
    .filter(Boolean);
  if (lines.length) {
    return lines;
  }
  return [
    "当前问题：业务材料分散，演示准备成本高；内容结构难统一；输出质量不稳定。",
    "方案总览：建立结构化大纲、模板渲染和版式检查流程；让演示材料稳定复用。",
    "流程闭环：先生成 slide_spec；再输出多格式；最后根据检查报告优化。",
    "落地路线：先跑通 MVP；再补充模板；最后沉淀企业级演示资产。"
  ];
}

function inferType(text: string): SlideType {
  const rules: Array<[SlideType, RegExp]> = [
    ["problem", /问题|痛点|现状|挑战/],
    ["insight", /洞察|判断|趋势|价值/],
    ["solution", /方案|能力|产品|总览/],
    ["process", /流程|闭环|链路|步骤/],
    ["comparison", /对比|改造前|改造后|差异/],
    ["timeline", /时间|阶段|里程碑/],
    ["data_card", /数据|指标|收益|效率/],
    ["architecture", /架构|系统|集成|对接/],
    ["case", /案例|场景|实践/],
    ["roadmap", /路线|计划|落地|推进/]
  ];
  return rules.find(([, pattern]) => pattern.test(text))?.[0] ?? "solution";
}

function defaultsFor(type: SlideType) {
  const map: Record<SlideType, string[]> = {
    cover: ["明确主题", "聚焦听众", "说明目标"],
    agenda: ["现状与痛点", "方案与流程", "价值与行动"],
    section: ["承接上文", "进入重点", "保持节奏"],
    problem: ["入口分散", "反馈滞后", "责任难追踪"],
    insight: ["统一计划主线", "沉淀过程数据", "减少人工追踪"],
    solution: ["统一入口", "在线审批", "移动反馈"],
    process: ["计划编制", "发布审批", "反馈回流"],
    comparison: ["流程可追踪", "责任可定位", "结果可沉淀"],
    timeline: ["先跑通入口", "再补齐闭环", "后沉淀分析"],
    data_card: ["效率提升", "过程透明", "风险提前暴露"],
    architecture: ["管理端统一配置", "移动端快速反馈", "数据端持续沉淀"],
    case: ["明确场景", "落地动作", "验证结果"],
    roadmap: ["入口改造", "审批联动", "分析沉淀"],
    summary: ["统一入口", "闭环反馈", "持续优化"]
  };
  return map[type];
}

function splitItem(item: string) {
  const [rawTitle, ...restParts] = item.split(/[：:]/);
  const rawRest = restParts.join("：") || item;
  const fragments = rawRest
    .split(/[;；]/)
    .map(compact)
    .filter(Boolean);
  return {
    title: rawTitle && rawTitle !== item ? rawTitle : fragments[0] ?? item,
    message: fragments[0] ?? rawRest,
    points: fragments.slice(1)
  };
}

function normalizeSlide(page: number, type: SlideType, title: string, message: string, points: string[], visual: string): SlideSpec {
  const safePoints = (points.length ? points : defaultsFor(type)).slice(0, 3).map((point) => limitText(point, 24));
  return {
    page,
    type,
    title: limitText(title, 18),
    message: limitText(message, 34),
    points: safePoints,
    visual,
    speaker_note: `${limitText(title, 18)}：${limitText(message, 60)}`
  };
}

const title = field("PPT 主题", "进度计划与反馈闭环演示");
const audience = field("听众对象", "客户项目负责人、业务管理者、实施顾问");
const scenario = field("使用场景", "客户方案演示与需求评审");
const goal = field("期望达成的目标", "说明计划入口、发布审批和移动端反馈如何形成闭环");
const pageCount = parsePageCount(field("页数", "8"));
const style = field("风格要求", "商务、克制、清晰，适合企业级软件产品汇报");
const formats = parseFormats(field("输出格式要求", "PPTX、HTML、PDF、PNG、Marp"));
const template = inferTemplate(style);

const items = contentItems();
const middleCount = Math.max(1, pageCount - 2);
const selectedItems = items.slice(0, middleCount);

while (selectedItems.length < middleCount) {
  selectedItems.push(defaultsFor("solution")[selectedItems.length % 3]);
}

const slides: SlideSpec[] = [
  normalizeSlide(1, "cover", title, goal, [audience, scenario], "Use a calm cover with one strong title and concise meta information."),
  normalizeSlide(2, "agenda", "汇报路径", "从问题到方案再到落地", ["现状与痛点", "方案与流程", "价值与行动"], "Use a three-step agenda.")
];

for (const item of selectedItems.slice(0, pageCount - 3)) {
  const parsed = splitItem(item);
  const type = inferType(item);
  slides.push(
    normalizeSlide(
      slides.length + 1,
      type,
      parsed.title,
      parsed.message,
      parsed.points,
      `Use a ${type} layout with restrained enterprise styling.`
    )
  );
}

slides.push(
  normalizeSlide(slides.length + 1, "summary", "总结与行动", "用统一闭环提升计划执行质量", ["统一计划入口", "打通反馈闭环", "沉淀进度资产"], "Use a closing summary with clear next actions.")
);

slides.forEach((slide, index) => {
  slide.page = index + 1;
  if (!ALLOWED_TYPES.includes(slide.type)) {
    slide.type = "solution";
  }
  if (charLen(slide.title) > 18) {
    slide.title = limitText(slide.title, 18);
  }
});

const spec: DeckSpec = {
  deck: {
    title,
    audience,
    scenario,
    goal,
    page_count: slides.length,
    style,
    formats,
    ...(template ? { template } : {})
  },
  slides
};

writeJson(["specs", "slide_spec.json"], spec);
console.log(`Generated specs/slide_spec.json with ${slides.length} slides.`);
