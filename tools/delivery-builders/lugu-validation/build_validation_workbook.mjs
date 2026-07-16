import fs from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = fileURLToPath(new URL(".", import.meta.url));
const outputPath = `${outputDir}泸古项目验证材料_20260715.xlsx`;
const date = (day) => new Date(Date.UTC(2026, 6, day));

const COLORS = {
  navy: "#183B56",
  teal: "#0F766E",
  tealLight: "#D9F0EC",
  blueLight: "#EAF3FF",
  grayLight: "#F3F4F6",
  gray: "#667085",
  border: "#D0D5DD",
  white: "#FFFFFF",
  green: "#DCFCE7",
  greenText: "#166534",
  yellow: "#FEF3C7",
  yellowText: "#92400E",
  red: "#FEE2E2",
  redText: "#991B1B",
  orange: "#F59E0B",
};

const workbook = Workbook.create();
const dashboard = workbook.worksheets.add("验证看板");
const hypotheses = workbook.worksheets.add("验证总表");
const timeline = workbook.worksheets.add("进度计划");
const dataSheet = workbook.worksheets.add("数据清单");
const review = workbook.worksheets.add("客户复核");
const interview = workbook.worksheets.add("访谈提纲");
const minutes = workbook.worksheets.add("会议纪要");
const actions = workbook.worksheets.add("行动项");

const allSheets = [dashboard, hypotheses, timeline, dataSheet, review, interview, minutes, actions];
for (const sheet of allSheets) {
  sheet.showGridLines = false;
}

function setTitle(sheet, titleText, subtitleText, lastCol) {
  const title = sheet.getRange(`A1:${lastCol}2`);
  title.merge();
  title.values = [[titleText]];
  title.format = {
    fill: COLORS.navy,
    font: { name: "Microsoft YaHei", size: 20, bold: true, color: COLORS.white },
    horizontalAlignment: "left",
    verticalAlignment: "center",
  };
  title.format.rowHeight = 30;

  const subtitle = sheet.getRange(`A3:${lastCol}3`);
  subtitle.merge();
  subtitle.values = [[subtitleText]];
  subtitle.format = {
    fill: COLORS.tealLight,
    font: { name: "Microsoft YaHei", size: 10, color: COLORS.navy },
    horizontalAlignment: "left",
    verticalAlignment: "center",
    wrapText: true,
    borders: { bottom: { style: "thin", color: COLORS.border } },
  };
  subtitle.format.rowHeight = 26;
}

function styleHeader(range) {
  range.format = {
    fill: COLORS.teal,
    font: { name: "Microsoft YaHei", size: 10, bold: true, color: COLORS.white },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: COLORS.border },
  };
  range.format.rowHeight = 30;
}

function styleBody(range) {
  range.format = {
    font: { name: "Microsoft YaHei", size: 10, color: "#202939" },
    verticalAlignment: "center",
    wrapText: true,
    borders: {
      insideHorizontal: { style: "thin", color: COLORS.border },
      bottom: { style: "thin", color: COLORS.border },
      left: { style: "thin", color: COLORS.border },
      right: { style: "thin", color: COLORS.border },
    },
  };
}

function styleSection(range, text) {
  range.merge();
  range.values = [[text]];
  range.format = {
    fill: COLORS.navy,
    font: { name: "Microsoft YaHei", size: 11, bold: true, color: COLORS.white },
    horizontalAlignment: "left",
    verticalAlignment: "center",
  };
  range.format.rowHeight = 25;
}

function setWidths(sheet, lastRow, widths) {
  const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  widths.forEach((width, index) => {
    sheet.getRange(`${letters[index]}1:${letters[index]}${lastRow}`).format.columnWidth = width;
  });
}

function addStatusFormatting(range) {
  range.conditionalFormats.add("containsText", {
    text: "已完成",
    format: { fill: COLORS.green, font: { color: COLORS.greenText, bold: true } },
  });
  range.conditionalFormats.add("containsText", {
    text: "通过",
    format: { fill: COLORS.green, font: { color: COLORS.greenText, bold: true } },
  });
  range.conditionalFormats.add("containsText", {
    text: "绿色",
    format: { fill: COLORS.green, font: { color: COLORS.greenText, bold: true } },
  });
  range.conditionalFormats.add("containsText", {
    text: "进行中",
    format: { fill: COLORS.yellow, font: { color: COLORS.yellowText, bold: true } },
  });
  range.conditionalFormats.add("containsText", {
    text: "需校准",
    format: { fill: COLORS.yellow, font: { color: COLORS.yellowText, bold: true } },
  });
  range.conditionalFormats.add("containsText", {
    text: "黄色",
    format: { fill: COLORS.yellow, font: { color: COLORS.yellowText, bold: true } },
  });
  range.conditionalFormats.add("containsText", {
    text: "不通过",
    format: { fill: COLORS.red, font: { color: COLORS.redText, bold: true } },
  });
  range.conditionalFormats.add("containsText", {
    text: "不可获得",
    format: { fill: COLORS.red, font: { color: COLORS.redText, bold: true } },
  });
  range.conditionalFormats.add("containsText", {
    text: "红色",
    format: { fill: COLORS.red, font: { color: COLORS.redText, bold: true } },
  });
}

// 1. 验证看板
setTitle(
  dashboard,
  "泸古项目客户验证看板",
  "验证周期：2026-07-15 至 2026-07-30｜目标：用一个真实工程切片验证数据可用性、结果可信度、决策价值和继续试点意愿",
  "L",
);

const cards = [
  ["A5:C5", "A6:C7", "计划活动", "=COUNTA('进度计划'!A5:A13)"],
  ["D5:F5", "D6:F7", "已完成活动", "=COUNTIF('进度计划'!H5:H13,\"已完成\")"],
  ["G5:I5", "G6:I7", "已收到数据", "=COUNTIF('数据清单'!G5:G12,\"已收到\")"],
  [
    "J5:L5",
    "J6:L7",
    "总体状态",
    "=IF(COUNTIF('验证总表'!G5:G9,\"未验证\")=5,\"待启动\",IF(AND(COUNTIF('数据清单'!G5:G12,\"已收到\")>=6,COUNTIF('验证总表'!G5:G9,\"通过\")>=4),\"绿色\",IF(OR(COUNTIF('数据清单'!G5:G12,\"不可获得\")>=3,COUNTIF('验证总表'!G5:G9,\"不通过\")>=2),\"红色\",\"黄色\")))",
  ],
];
for (const [labelRange, valueRange, label, formula] of cards) {
  const labelCell = dashboard.getRange(labelRange);
  labelCell.merge();
  labelCell.values = [[label]];
  labelCell.format = {
    fill: COLORS.grayLight,
    font: { name: "Microsoft YaHei", size: 10, bold: true, color: COLORS.gray },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    borders: { preset: "outside", style: "thin", color: COLORS.border },
  };
  const valueCell = dashboard.getRange(valueRange);
  valueCell.merge();
  valueCell.formulas = [[formula]];
  valueCell.format = {
    fill: COLORS.white,
    font: { name: "Microsoft YaHei", size: 20, bold: true, color: COLORS.navy },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    borders: { preset: "outside", style: "medium", color: COLORS.border },
  };
}
addStatusFormatting(dashboard.getRange("J6:L7"));

styleSection(dashboard.getRange("A9:L9"), "本轮核心验证问题");
const mainQuestion = dashboard.getRange("A10:L11");
mainQuestion.merge();
mainQuestion.values = [["能否将泸古项目一个边界清晰的真实工程场景转化为可计算的计划模型，得到客户基本认可的排程结果，并帮助客户判断一个真实的节点或资源决策？"]];
mainQuestion.format = {
  fill: COLORS.blueLight,
  font: { name: "Microsoft YaHei", size: 12, bold: true, color: COLORS.navy },
  horizontalAlignment: "left",
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "outside", style: "thin", color: COLORS.border },
};

styleSection(dashboard.getRange("A13:F13"), "当前 Demo 可用于验证");
const currentScope = dashboard.getRange("A14:F18");
currentScope.merge();
currentScope.values = [["• 项目结构、工程量、工艺工效、施工逻辑、资源和里程碑建模\n• 任务网络生成与问题诊断\n• 固定资源求工期、目标工期测算资源\n• 当前/调整方案及经济、平衡、抢工方案比较\n• 节点偏差、资源投入和瓶颈解释"]];
currentScope.format = { fill: COLORS.white, font: { name: "Microsoft YaHei", size: 10 }, wrapText: true, verticalAlignment: "top", borders: { preset: "outside", style: "thin", color: COLORS.border } };

styleSection(dashboard.getRange("G13:L13"), "本轮不作成熟能力承诺");
const futureScope = dashboard.getRange("G14:L18");
futureScope.merge();
futureScope.values = [["• 全项目数据自动接入和无人工干预建模\n• 正式生产环境的持久化、权限、审批和系统集成\n• 已打通的实际进度采集、滚动预测、动态重排和风险闭环\n• 质量、安全、成本、合同和物资的完整风险模型\n\n动态管控与风险预警只用于方向共创，不作为本轮主要通过标准。"]];
futureScope.format = { fill: "#FFF7ED", font: { name: "Microsoft YaHei", size: 10 }, wrapText: true, verticalAlignment: "top", borders: { preset: "outside", style: "thin", color: COLORS.orange } };

styleSection(dashboard.getRange("A20:L20"), "7 月 30 日总体判定");
dashboard.getRange("A21:L24").values = [
  ["结论", "条件", null, null, null, null, null, null, null, null, null, null],
  ["绿色", "真实数据可跑通，结果基本可信，支持至少一个实际决策，客户同意继续试点。", null, null, null, null, null, null, null, null, null, null],
  ["黄色", "真实数据能够跑通，但工效、逻辑或数据仍需校准；客户认可方向并愿意继续复核。", null, null, null, null, null, null, null, null, null, null],
  ["红色", "无法获得最低真实数据，结果不能形成可解释的工程判断，或客户没有继续意愿。", null, null, null, null, null, null, null, null, null, null],
];
for (let r = 21; r <= 24; r += 1) dashboard.getRange(`B${r}:L${r}`).merge();
styleHeader(dashboard.getRange("A21:L21"));
styleBody(dashboard.getRange("A22:L24"));
dashboard.getRange("A22:A22").format = { fill: COLORS.green, font: { bold: true, color: COLORS.greenText }, horizontalAlignment: "center", verticalAlignment: "center", borders: { preset: "all", style: "thin", color: COLORS.border } };
dashboard.getRange("A23:A23").format = { fill: COLORS.yellow, font: { bold: true, color: COLORS.yellowText }, horizontalAlignment: "center", verticalAlignment: "center", borders: { preset: "all", style: "thin", color: COLORS.border } };
dashboard.getRange("A24:A24").format = { fill: COLORS.red, font: { bold: true, color: COLORS.redText }, horizontalAlignment: "center", verticalAlignment: "center", borders: { preset: "all", style: "thin", color: COLORS.border } };

styleSection(dashboard.getRange("A26:L26"), "工作表使用说明");
dashboard.getRange("A27:L34").values = [
  ["工作表", "用途", null, null, null, null, null, null, null, null, null, null],
  ["验证总表", "跟踪五项核心假设、证据、客户评价和最终结论。", null, null, null, null, null, null, null, null, null, null],
  ["进度计划", "按 7 月 30 日倒排工作，修改状态后自动计算完成度。", null, null, null, null, null, null, null, null, null, null],
  ["数据清单", "现场确认资料来源、责任人、承诺日期和数据质量问题。", null, null, null, null, null, null, null, null, null, null],
  ["客户复核", "记录关键任务、逻辑、工期、资源和方案价值的客户判断。", null, null, null, null, null, null, null, null, null, null],
  ["访谈提纲", "按 60—75 分钟议程引导上午沟通，记录客户原话和承诺。", null, null, null, null, null, null, null, null, null, null],
  ["会议纪要", "会中或会后填写场景、数据承诺和下一步安排。", null, null, null, null, null, null, null, null, null, null],
  ["行动项", "统一跟踪双方行动、截止日期、优先级和逾期状态。", null, null, null, null, null, null, null, null, null, null],
];
for (let r = 27; r <= 34; r += 1) dashboard.getRange(`B${r}:L${r}`).merge();
styleHeader(dashboard.getRange("A27:L27"));
styleBody(dashboard.getRange("A28:L34"));
dashboard.getRange("A28:A34").format.font = { name: "Microsoft YaHei", size: 10, bold: true, color: COLORS.teal };
setWidths(dashboard, 34, [14, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12]);
dashboard.getRange("A10:L11").format.rowHeight = 34;
dashboard.getRange("A14:L18").format.rowHeight = 24;
dashboard.freezePanes.freezeRows(3);

// 2. 验证总表
setTitle(hypotheses, "泸古项目验证总表", "用验证证据判断产品方向，不以页面评价或一次演示替代真实验证。蓝色单元格为待填写项。", "H");
const hypothesisRows = [
  ["H1", "客户现有数据可以转换为当前任务、逻辑、资源和里程碑模型", "完成真实数据映射并记录缺失、冲突与默认假设", "一份完成映射且问题可追踪的真实场景输入", "", "", "未验证", ""],
  ["H2", "系统生成的任务、工期、逻辑和资源结果具备基本工程可信度", "复核至少 10 个关键任务、10 条逻辑及关键工期资源", "客户专业人员给出明确复核意见，主要差异可解释或校准", "", "", "未验证", ""],
  ["H3", "多方案比较能帮助客户判断节点可达性或资源配置", "围绕一个真实决策比较不调整与干预方案", "至少一个客户认可的决策场景和方案比较结论", "", "", "未验证", ""],
  ["H4", "产品相较现有人工方式能够更快发现问题或比较方案", "对比客户现有过程和系统结果", "客户指出至少一项新增信息、效率提升或决策帮助", "", "", "未验证", ""],
  ["H5", "客户愿意继续参与产品校准和试点", "确认下一轮范围、人员和时间", "明确下一轮范围、责任人和时间安排", "", "", "未验证", ""],
];
hypotheses.getRange("A4:H9").values = [["编号", "待验证假设", "关键验证动作", "通过证据", "客户评价", "我方结论", "验证状态", "证据链接/备注"], ...hypothesisRows];
styleHeader(hypotheses.getRange("A4:H4"));
styleBody(hypotheses.getRange("A5:H9"));
hypotheses.getRange("E5:H9").format.fill = COLORS.blueLight;
hypotheses.getRange("E5:E9").dataValidation = { rule: { type: "list", values: ["认可", "需校准", "不认可", "暂无法判断"] } };
hypotheses.getRange("G5:G9").dataValidation = { rule: { type: "list", values: ["未验证", "验证中", "通过", "需校准", "不通过"] } };
addStatusFormatting(hypotheses.getRange("E5:G9"));
hypotheses.getRange("A5:A9").format = { fill: COLORS.grayLight, font: { name: "Microsoft YaHei", size: 10, bold: true, color: COLORS.navy }, horizontalAlignment: "center", verticalAlignment: "center", borders: { preset: "all", style: "thin", color: COLORS.border } };
hypotheses.getRange("A5:H9").format.rowHeight = 58;
setWidths(hypotheses, 9, [8, 31, 31, 31, 14, 24, 13, 28]);
hypotheses.freezePanes.freezeRows(4);
hypotheses.tables.add("A4:H9", true, "ValidationHypothesesTable");

// 3. 进度计划
setTitle(timeline, "7 月 30 日客户验证倒排计划", "修改“状态”后，“完成度”自动计算。7 月 18 日仍拿不到最小数据包时，应立即缩小范围或启动备选项目。", "J");
const timelineRows = [
  ["P01", date(15), date(16), "客户沟通，锁定场景、决策问题、数据、责任人和复核时间", "双方", "场景确认单、数据清单、会议纪要", "必须有场景和责任人", "进行中", null, ""],
  ["P02", date(17), date(18), "接收资料并完成完整性检查", "客户/我方", "原始资料包、数据问题清单", "最小数据包基本到位", "未开始", null, ""],
  ["P03", date(19), date(21), "人工映射、参数标注、第一次求解", "我方", "可复现输入、当前条件方案、首轮诊断", "完成一次全流程求解，问题可解释", "未开始", null, ""],
  ["P04", date(22), date(22), "内部工程与产品预审", "我方", "内部评审记录、客户演示版本", "排除明显数据映射和展示错误", "未开始", null, ""],
  ["P05", date(23), date(24), "第一次客户结果复核", "双方", "客户反馈清单、差异分类", "完成关键任务、逻辑和结果复核", "未开始", null, ""],
  ["P06", date(25), date(26), "参数校准、方案调整和重新求解", "我方", "校准版结果、方案对比", "主要分歧已处理或明确归因", "未开始", null, ""],
  ["P07", date(27), date(28), "第二次客户复核与价值确认", "双方", "客户确认记录、下一步试点建议", "客户对可信度、决策价值和后续意愿表态", "未开始", null, ""],
  ["P08", date(29), date(29), "整理验证证据和结论", "我方", "验证报告、问题优先级、产品建议", "每项结论有数据或客户反馈支撑", "未开始", null, ""],
  ["P09", date(30), date(30), "形成阶段决策", "我方", "绿/黄/红结论及后续计划", "明确继续、校准后继续或停止当前路径", "未开始", null, ""],
];
timeline.getRange("A4:J13").values = [["编号", "开始日期", "结束日期", "重点工作", "责任方", "阶段输出", "通过条件", "状态", "完成度", "风险/备注"], ...timelineRows];
timeline.getRange("I5:I13").formulas = Array.from({ length: 9 }, (_, index) => {
  const row = index + 5;
  return [`=IF(H${row}=\"已完成\",1,IF(H${row}=\"进行中\",0.5,0))`];
});
styleHeader(timeline.getRange("A4:J4"));
styleBody(timeline.getRange("A5:J13"));
timeline.getRange("B5:C13").format.numberFormat = "yyyy-mm-dd";
timeline.getRange("I5:I13").format.numberFormat = "0%";
timeline.getRange("H5:H13").dataValidation = { rule: { type: "list", values: ["未开始", "进行中", "已完成", "已阻塞"] } };
timeline.getRange("H5:H13").format.fill = COLORS.blueLight;
timeline.getRange("J5:J13").format.fill = COLORS.blueLight;
addStatusFormatting(timeline.getRange("H5:H13"));
timeline.getRange("A5:J13").format.rowHeight = 48;
setWidths(timeline, 13, [8, 12, 12, 31, 12, 28, 28, 12, 11, 25]);
timeline.freezePanes.freezeRows(4);
timeline.tables.add("A4:J13", true, "ValidationTimelineTable");

// 4. 数据清单
setTitle(dataSheet, "泸古项目最小数据清单", "建议在 2026-07-18 前取得资料。逐项确认资料在哪里、什么格式、谁能提供、何时能给、谁能解释。", "J");
const dataRows = [
  ["D01", "工程范围与结构", "所选桥梁或工区的结构层级、构件范围和工程量", "必须", "工程/技术负责人", date(18), "未确认", "", "", ""],
  ["D02", "当前计划", "现有 WBS、横道计划或主要任务及日期", "必须", "计划工程师", date(18), "未确认", "", "", ""],
  ["D03", "控制节点", "至少一个合同或内部控制节点及目标日期", "必须", "项目管理人员", date(18), "未确认", "", "", ""],
  ["D04", "资源条件", "当前及可增加的班组、设备、工作面数量", "必须", "生产/设备负责人", date(18), "未确认", "", "", ""],
  ["D05", "工艺与工效", "关键任务工法、计划或经验工效", "必须", "技术/现场负责人", date(18), "未确认", "", "", ""],
  ["D06", "施工逻辑", "关键前后置、工作面释放、转场和并行限制", "必须", "计划与技术人员", date(18), "未确认", "", "", ""],
  ["D07", "实际进度", "状态日期、已开工/已完工任务、剩余工程量", "建议", "计划/现场人员", date(18), "未确认", "", "", ""],
  ["D08", "历史问题", "近期资源、工效、前置条件或节点问题", "建议", "项目管理人员", date(18), "未确认", "", "", ""],
];
dataSheet.getRange("A4:J12").values = [["编号", "数据类别", "最低要求", "必要性", "客户责任人", "承诺日期", "获取状态", "资料路径/来源", "质量问题", "处理结论"], ...dataRows];
styleHeader(dataSheet.getRange("A4:J4"));
styleBody(dataSheet.getRange("A5:J12"));
dataSheet.getRange("F5:F12").format.numberFormat = "yyyy-mm-dd";
dataSheet.getRange("E5:J12").format.fill = COLORS.blueLight;
dataSheet.getRange("G5:G12").dataValidation = { rule: { type: "list", values: ["未确认", "已承诺", "已收到", "需补充", "不可获得"] } };
addStatusFormatting(dataSheet.getRange("G5:G12"));
dataSheet.getRange("D5:D10").format = { fill: "#FFF7ED", font: { name: "Microsoft YaHei", size: 10, bold: true, color: COLORS.yellowText }, horizontalAlignment: "center", verticalAlignment: "center", borders: { preset: "all", style: "thin", color: COLORS.border } };
dataSheet.getRange("A5:J12").format.rowHeight = 46;
setWidths(dataSheet, 12, [8, 18, 35, 10, 18, 13, 14, 28, 28, 28]);
dataSheet.freezePanes.freezeRows(4);
dataSheet.tables.add("A4:J12", true, "MinimumDataTable");

// 5. 客户复核
setTitle(review, "客户结果复核记录", "客户反馈按“认可、需校准、不认可、暂无法判断”记录；差异必须归类，校准后保留前后结果和原因。", "K");
const reviewRows = [];
for (let i = 1; i <= 10; i += 1) {
  reviewRows.push(["关键任务", `T${String(i).padStart(2, "0")}`, "", "任务是否缺失、拆分是否合理、工期是否可信", "", "", "", "", "待复核", "", ""]);
}
for (let i = 1; i <= 10; i += 1) {
  reviewRows.push(["关键逻辑", `L${String(i).padStart(2, "0")}`, "", "前后置、并行、转场或工作面限制是否符合现场", "", "", "", "", "待复核", "", ""]);
}
reviewRows.push(
  ["关键工期", "K01", "", "关键任务工效与持续时间是否在可接受范围", "", "", "", "", "待复核", "", ""],
  ["关键资源", "R01", "", "资源占用、共享、上限和瓶颈判断是否合理", "", "", "", "", "待复核", "", ""],
  ["控制节点", "M01", "", "预测节点及偏差判断是否合理、依据是否可解释", "", "", "", "", "待复核", "", ""],
  ["方案价值", "V01", "", "方案差异是否能支持实际节点或资源决策", "", "", "", "", "待复核", "", ""],
);
review.getRange(`A4:K${4 + reviewRows.length}`).values = [["复核类型", "编号", "检查对象/任务", "检查标准", "客户判断", "差异分类", "问题说明", "处理人", "处理状态", "复核日期", "证据/备注"], ...reviewRows];
styleHeader(review.getRange("A4:K4"));
styleBody(review.getRange(`A5:K${4 + reviewRows.length}`));
review.getRange(`C5:K${4 + reviewRows.length}`).format.fill = COLORS.blueLight;
review.getRange(`E5:E${4 + reviewRows.length}`).dataValidation = { rule: { type: "list", values: ["认可", "需校准", "不认可", "暂无法判断"] } };
review.getRange(`F5:F${4 + reviewRows.length}`).dataValidation = { rule: { type: "list", values: ["无差异", "数据问题", "规则问题", "算法问题", "范围口径问题", "待确认"] } };
review.getRange(`I5:I${4 + reviewRows.length}`).dataValidation = { rule: { type: "list", values: ["待复核", "处理中", "已校准", "已确认", "不采纳"] } };
review.getRange(`J5:J${4 + reviewRows.length}`).format.numberFormat = "yyyy-mm-dd";
addStatusFormatting(review.getRange(`E5:I${4 + reviewRows.length}`));
review.getRange(`A5:K${4 + reviewRows.length}`).format.rowHeight = 42;
setWidths(review, 4 + reviewRows.length, [14, 9, 27, 37, 14, 15, 30, 14, 14, 13, 26]);
review.freezePanes.freezeRows(4);
review.freezePanes.freezeColumns(2);
review.tables.add(`A4:K${4 + reviewRows.length}`, true, "CustomerReviewTable");

// 6. 访谈提纲
setTitle(interview, "泸古项目上午访谈提纲", "建议时长 60—75 分钟｜会议性质：方案共创与试点确认，不是泛需求调研或单向 Demo 汇报。蓝色单元格用于现场记录。", "F");
const interviewRows = [
  ["0—5 分钟", "开场与边界", "说明产品仍在联合验证阶段，本次希望选真实场景共同跑一轮", "开场：我们不再做泛需求调研，也不把尚未成熟的系统当正式产品汇报。希望在 7 月 30 日前，用一个真实场景共同验证计划建模、方案求解、结果复核和调整比较。", "", ""],
  ["5—15 分钟", "确认近期变化", "确认上次调研是否仍准确，只补充近期变化", "上次沟通后，计划、关键节点、资源组织或现场条件发生了哪些变化？最近两周管理层最关注的计划问题是什么？", "", ""],
  ["15—25 分钟", "找到决策问题", "找到 7 月底前有价值、能量化的节点或资源问题", "从现在到 7 月底，最需要判断的一个节点或资源问题是什么？如果不调整，最担心哪个节点？什么系统结论会真正影响行动？", "", ""],
  ["25—35 分钟", "方案与 Demo", "用客户问题串起完整产品方向，演示当前已验证部分", "只展示：项目结构与输入 → 任务网络 → 当前资源求解 → 调整资源重新求解 → 方案比较。明确当前已验证、下一步共同验证和长期方向三层边界。", "", ""],
  ["35—50 分钟", "选择验证场景", "收敛工程范围、状态日期、控制节点和方案边界", "哪座桥或哪个工区最有代表性且数据相对完整？必须纳入哪些任务？控制节点是什么？资源、工作面或顺序有哪些可调边界？", "", ""],
  ["50—60 分钟", "数据与人员", "逐项确认数据来源、责任人、日期和专业复核人", "逐项追问：资料在哪里、什么格式、谁能提供、何时能给、谁能解释。至少确定一名数据联系人和一名专业复核人。", "", ""],
  ["60—70 分钟", "验收与复核", "对齐什么叫有效并约定两次结果复核", "谁判断任务、逻辑、工效和资源是否合理？什么结果才值得进入下一阶段？首轮 7 月 23—24 日、校准后 7 月 27—28 日能否安排？", "", ""],
  ["70—75 分钟", "复述结论", "逐项复述场景、问题、数据、责任人和日期", "收口：范围是【】、问题是【】、节点是【】；【责任人】在【日期】提供【资料】；【复核人】在【日期】复核；7 月 30 日形成绿/黄/红结论。", "", ""],
];
interview.getRange("A4:F12").values = [["时间", "环节", "目标", "核心问题/话术", "现场记录", "结论/承诺"], ...interviewRows];
styleHeader(interview.getRange("A4:F4"));
styleBody(interview.getRange("A5:F12"));
interview.getRange("E5:F12").format.fill = COLORS.blueLight;
interview.getRange("A5:F12").format.rowHeight = 78;
setWidths(interview, 12, [13, 17, 29, 58, 34, 30]);
interview.freezePanes.freezeRows(4);
interview.tables.add("A4:F12", true, "InterviewAgendaTable");

// 7. 会议纪要
setTitle(minutes, "泸古项目验证沟通会议纪要", "建议会中直接填写蓝色单元格，会后 2 小时内发送确认。会议不能以“后续保持沟通”结束。", "H");
minutes.getRange("A5:H7").values = [
  ["会议时间", null, null, "会议地点/方式", null, null, null, null],
  ["客户参会人及角色", null, null, "我方参会人及角色", null, null, null, null],
  ["上次调研后的变化", null, null, null, null, null, null, null],
];
minutes.getRange("B5:C5").merge();
minutes.getRange("E5:H5").merge();
minutes.getRange("B6:C6").merge();
minutes.getRange("E6:H6").merge();
minutes.getRange("B7:H7").merge();
minutes.getRange("A5:A7").format = { fill: COLORS.grayLight, font: { name: "Microsoft YaHei", size: 10, bold: true, color: COLORS.navy }, verticalAlignment: "center", borders: { preset: "all", style: "thin", color: COLORS.border } };
minutes.getRange("D5:D6").format = { fill: COLORS.grayLight, font: { name: "Microsoft YaHei", size: 10, bold: true, color: COLORS.navy }, verticalAlignment: "center", borders: { preset: "all", style: "thin", color: COLORS.border } };
minutes.getRange("B5:C6").format.fill = COLORS.blueLight;
minutes.getRange("E5:H6").format.fill = COLORS.blueLight;
minutes.getRange("B7:H7").format.fill = COLORS.blueLight;
styleBody(minutes.getRange("B5:C7"));
styleBody(minutes.getRange("E5:H7"));

styleSection(minutes.getRange("A9:H9"), "验证场景确认");
const sceneRows = [
  ["项目/标段", ""],
  ["桥梁/工区/结构物范围", ""],
  ["状态日期", ""],
  ["控制节点及目标日期", ""],
  ["核心决策问题", ""],
  ["当前可选措施", ""],
  ["明确不纳入范围", ""],
];
minutes.getRange("A10:H16").values = sceneRows.map(([label, value]) => [label, value, null, null, null, null, null, null]);
for (let r = 10; r <= 16; r += 1) minutes.getRange(`B${r}:H${r}`).merge();
minutes.getRange("A10:A16").format = { fill: COLORS.grayLight, font: { name: "Microsoft YaHei", size: 10, bold: true, color: COLORS.navy }, verticalAlignment: "center", borders: { preset: "all", style: "thin", color: COLORS.border } };
minutes.getRange("B10:H16").format = { fill: COLORS.blueLight, font: { name: "Microsoft YaHei", size: 10 }, verticalAlignment: "center", wrapText: true, borders: { preset: "all", style: "thin", color: COLORS.border } };

styleSection(minutes.getRange("A18:H18"), "数据承诺");
const minuteDataRows = dataRows.map((row) => [row[1], "", "", "", "", ""]);
minutes.getRange("A19:F27").values = [["数据项", "是否具备", "形式/来源", "客户责任人", "提供日期", "备注/风险"], ...minuteDataRows];
styleHeader(minutes.getRange("A19:F19"));
styleBody(minutes.getRange("A20:F27"));
minutes.getRange("B20:F27").format.fill = COLORS.blueLight;
minutes.getRange("B20:B27").dataValidation = { rule: { type: "list", values: ["具备", "部分具备", "不具备", "待确认"] } };
minutes.getRange("E20:E27").format.numberFormat = "yyyy-mm-dd";

styleSection(minutes.getRange("A29:H29"), "客户评价与后续安排");
minutes.getRange("A30:H35").values = [
  ["任务与逻辑复核人", "", null, null, "资源与工效复核人", "", null, null],
  ["决策价值评价人", "", null, null, "客户认为验证有效的标准", "", null, null],
  ["客户最担心的错误或风险", "", null, null, null, null, null, null],
  ["首轮结果复核时间", "", null, null, "校准后复核时间", "", null, null],
  ["下一阶段建议范围", "", null, null, null, null, null, null],
  ["会议启动状态", "待确认", null, null, "绿色=场景/数据/复核人/时间明确；黄色=仍有缺口；红色=无真实承诺", null, null, null],
];
for (const cellRange of ["B30:D30", "F30:H30", "B31:D31", "F31:H31", "B32:H32", "B33:D33", "F33:H33", "B34:H34", "B35:D35", "E35:H35"]) {
  minutes.getRange(cellRange).merge();
}
minutes.getRange("A30:A35").format = { fill: COLORS.grayLight, font: { name: "Microsoft YaHei", size: 10, bold: true, color: COLORS.navy }, verticalAlignment: "center", wrapText: true, borders: { preset: "all", style: "thin", color: COLORS.border } };
minutes.getRange("E30:E33").format = { fill: COLORS.grayLight, font: { name: "Microsoft YaHei", size: 10, bold: true, color: COLORS.navy }, verticalAlignment: "center", wrapText: true, borders: { preset: "all", style: "thin", color: COLORS.border } };
minutes.getRange("B30:H35").format = { fill: COLORS.blueLight, font: { name: "Microsoft YaHei", size: 10 }, verticalAlignment: "center", wrapText: true, borders: { preset: "all", style: "thin", color: COLORS.border } };
minutes.getRange("B35:D35").dataValidation = { rule: { type: "list", values: ["待确认", "绿色", "黄色", "红色"] } };
addStatusFormatting(minutes.getRange("B35:D35"));
minutes.getRange("A5:H35").format.rowHeight = 30;
minutes.getRange("A7:H7").format.rowHeight = 48;
minutes.getRange("A10:H16").format.rowHeight = 34;
minutes.getRange("A20:F27").format.rowHeight = 34;
minutes.getRange("A32:H35").format.rowHeight = 42;
setWidths(minutes, 35, [24, 19, 17, 19, 24, 19, 17, 19]);
minutes.freezePanes.freezeRows(3);

// 8. 行动项
setTitle(actions, "双方行动项跟踪", "截止日期和状态是验证能否在 7 月 30 日形成结果的关键。逾期判断会根据当前日期自动更新。", "J");
const actionRows = [
  ["A01", "会后确认", "发送会议纪要与数据清单", "我方", "高", date(15), "未开始", "纪要、资料清单", "", null],
  ["A02", "数据准备", "提供最小数据包", "客户", "高", date(18), "未开始", "脱敏资料包", "A01", null],
  ["A03", "建模求解", "完成首轮建模与求解", "我方", "高", date(21), "未开始", "首轮排程和诊断", "A02", null],
  ["A04", "内部预审", "完成工程与产品内部检查", "我方", "中", date(22), "未开始", "内部评审记录", "A03", null],
  ["A05", "客户复核", "完成首轮客户结果复核", "双方", "高", date(24), "未开始", "客户反馈清单", "A04", null],
  ["A06", "校准复核", "完成参数校准与第二次客户复核", "双方", "高", date(28), "未开始", "校准结果、确认记录", "A05", null],
  ["A07", "阶段决策", "形成绿/黄/红验证结论", "我方", "高", date(30), "未开始", "验证结论和后续计划", "A06", null],
];
actions.getRange("A4:J11").values = [["编号", "类别", "行动项", "负责人", "优先级", "截止日期", "状态", "输出物", "前置项", "进度判断"], ...actionRows];
actions.getRange("J5:J11").formulas = Array.from({ length: 7 }, (_, index) => {
  const row = index + 5;
  return [`=IF(G${row}=\"已完成\",\"已关闭\",IF(AND(F${row}<TODAY(),F${row}<>\"\"),\"已逾期\",\"正常\"))`];
});
styleHeader(actions.getRange("A4:J4"));
styleBody(actions.getRange("A5:J11"));
actions.getRange("F5:F11").format.numberFormat = "yyyy-mm-dd";
actions.getRange("D5:G11").format.fill = COLORS.blueLight;
actions.getRange("E5:E11").dataValidation = { rule: { type: "list", values: ["高", "中", "低"] } };
actions.getRange("G5:G11").dataValidation = { rule: { type: "list", values: ["未开始", "进行中", "已完成", "已阻塞"] } };
addStatusFormatting(actions.getRange("G5:J11"));
actions.getRange("J5:J11").conditionalFormats.add("containsText", { text: "已逾期", format: { fill: COLORS.red, font: { color: COLORS.redText, bold: true } } });
actions.getRange("A5:J11").format.rowHeight = 42;
setWidths(actions, 11, [8, 14, 32, 14, 11, 13, 13, 25, 10, 13]);
actions.freezePanes.freezeRows(4);
actions.tables.add("A4:J11", true, "ActionItemsTable");

// 紧凑检查与全表预览
const inspections = {};
inspections.dashboard = (await workbook.inspect({ kind: "table", range: "验证看板!A1:L34", include: "values,formulas", tableMaxRows: 34, tableMaxCols: 12, maxChars: 8000 })).ndjson;
inspections.timeline = (await workbook.inspect({ kind: "table", range: "进度计划!A4:J13", include: "values,formulas", tableMaxRows: 12, tableMaxCols: 10, maxChars: 5000 })).ndjson;
inspections.errors = (await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 300 }, summary: "final formula error scan" })).ndjson;
console.log("INSPECT_DASHBOARD\n" + inspections.dashboard);
console.log("INSPECT_TIMELINE\n" + inspections.timeline);
console.log("FORMULA_ERRORS\n" + inspections.errors);

for (const sheet of allSheets) {
  const preview = await workbook.render({ sheetName: sheet.name, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(`${outputDir}preview_${sheet.name}.png`, new Uint8Array(await preview.arrayBuffer()));
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(`OUTPUT=${outputPath}`);
