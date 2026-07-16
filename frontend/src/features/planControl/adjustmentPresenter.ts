export function diagnosticText(
  diagnostics: Array<{ level: "error" | "warning" | "info"; message: string }>,
  level: "error" | "warning",
): string {
  return diagnostics.filter((item) => item.level === level).map((item) => item.message).join("；");
}
