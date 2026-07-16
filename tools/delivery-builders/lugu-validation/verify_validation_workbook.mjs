import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputArgIndex = process.argv.indexOf("--input");
const defaultInputPath = fileURLToPath(
  new URL("../../../deliverables/validation/lugu/泸古项目验证材料_20260715.xlsx", import.meta.url),
);
const filePath = path.resolve(inputArgIndex >= 0 ? process.argv[inputArgIndex + 1] : defaultInputPath);
const input = await FileBlob.load(filePath);
const workbook = await SpreadsheetFile.importXlsx(input);

const sheets = await workbook.inspect({
  kind: "sheet",
  include: "id,name",
  maxChars: 3000,
});
const timeline = await workbook.inspect({
  kind: "table",
  range: "进度计划!A4:J13",
  include: "values,formulas",
  tableMaxRows: 10,
  tableMaxCols: 10,
  maxChars: 4000,
});
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "exported workbook formula error scan",
});

console.log("SHEETS\n" + sheets.ndjson);
console.log("TIMELINE\n" + timeline.ndjson);
console.log("ERRORS\n" + errors.ndjson);
