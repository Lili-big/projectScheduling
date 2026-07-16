import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const outputDir = "D:/codex_workspace/排程算法/outputs/019f69ae-7dc5-7a92-9406-dfb88497d8d1";
const sources = [
  {
    key: "bridge-progress",
    path: "D:/00-1-03-生产产线-24年/02-产品需求/15-2026斑马基建版/03 项目验证/泸古1标/泸古高速TJ-1标桥梁进度统计表4.27(1).xlsx",
  },
  {
    key: "workpoints",
    path: "D:/codex_workspace/架梁倒排/泸古1标架梁工点导入模板.xlsx",
  },
];

await fs.mkdir(outputDir, { recursive: true });

for (const source of sources) {
  const input = await FileBlob.load(source.path);
  const workbook = await SpreadsheetFile.importXlsx(input);
  const summary = await workbook.inspect({
    kind: "workbook,sheet,table,definedName",
    include: "id,name,range,rowCount,columnCount",
    maxChars: 30000,
    tableMaxRows: 8,
    tableMaxCols: 12,
    tableMaxCellChars: 120,
  });
  await fs.writeFile(`${outputDir}/${source.key}-summary.ndjson`, summary.ndjson, "utf8");
  process.stdout.write(`\n=== ${source.key} ===\n${summary.ndjson}\n`);

  const sheetInspection = await workbook.inspect({
    kind: "sheet",
    include: "id,name,range,rowCount,columnCount",
    maxChars: 20000,
  });
  await fs.writeFile(`${outputDir}/${source.key}-sheets.ndjson`, sheetInspection.ndjson, "utf8");
  const sheets = sheetInspection.ndjson
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line))
    .filter((entry) => entry.kind === "sheet");
  const extracted = [];
  for (const entry of sheets) {
    const worksheet = workbook.resolve(entry.id);
    const usedRange = worksheet.getUsedRange(false);
    extracted.push({
      name: entry.name,
      range: entry.range,
      values: usedRange.values,
      formulas: usedRange.formulas,
    });
  }
  await fs.writeFile(
    `${outputDir}/${source.key}-cells.json`,
    JSON.stringify({ source: source.path, sheets: extracted }, null, 2),
    "utf8",
  );

  const previewSheet = source.key === "bridge-progress" ? "汇总表" : "工点";
  const preview = await workbook.render({
    sheetName: previewSheet,
    range: source.key === "bridge-progress" ? "A1:R102" : "A1:I64",
    scale: 0.8,
    format: "png",
  });
  await fs.writeFile(
    `${outputDir}/${source.key}-preview.png`,
    new Uint8Array(await preview.arrayBuffer()),
  );
}
