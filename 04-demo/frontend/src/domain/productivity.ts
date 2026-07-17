import type { ProcessTemplate, ProductivityOption } from "../contracts";

export const pileProductivityUnitOptions = [
  { unit: "m/天", duration_method: "units_per_day", quantity_source: "pile_length_m" },
  { unit: "根/天", duration_method: "units_per_day", quantity_source: "count" },
  { unit: "天/根", duration_method: "fixed_days", quantity_source: "count" },
  { unit: "天/m", duration_method: "days_per_unit", quantity_source: "pile_length_m" },
];

export const segmentedPierMethodIds = new Set(["climbing_form", "sliding_form", "turnover_form"]);

export const segmentedPierProductivityUnitOptions = [
  { unit: "天/节", duration_method: "days_per_unit", quantity_source: "pier_height_m" },
  { unit: "m/天", duration_method: "units_per_day", quantity_source: "pier_height_m" },
];

export function defaultStandardSectionHeightForUnit(unit: string): number | undefined {
  return unit === "天/节" ? 4.5 : undefined;
}

export function supportsSegmentedPierUnits(process: ProcessTemplate): boolean {
  return (
    process.component_type === "pier_body"
    && (
      Boolean(process.method_id && segmentedPierMethodIds.has(process.method_id))
      || ["爬模", "滑模", "翻模"].some((keyword) => process.process_name.includes(keyword))
    )
  );
}

export function sectionHeightForOption(option: ProductivityOption): number | undefined {
  const value = option.standard_section_height_m;
  return typeof value === "number" && value > 0 ? value : defaultStandardSectionHeightForUnit(option.productivity_unit);
}

export function normalizeProductivityOptionForProcess(process: ProcessTemplate, option: ProductivityOption): ProductivityOption {
  if (process.component_type === "pile") {
    const unitRule = pileProductivityUnitOptions.find((item) => item.unit === option.productivity_unit);
    if (unitRule) {
      return {
        ...option,
        duration_method: unitRule.duration_method,
        quantity_source: unitRule.quantity_source,
      };
    }
  }

  if (!supportsSegmentedPierUnits(process)) {
    return option;
  }
  const unitRule = segmentedPierProductivityUnitOptions.find((item) => item.unit === option.productivity_unit);
  if (!unitRule) {
    return option;
  }
  return {
    ...option,
    duration_method: unitRule.duration_method,
    quantity_source: unitRule.quantity_source,
    standard_section_height_m: unitRule.unit === "天/节" ? sectionHeightForOption(option) : undefined,
  };
}

export function isSectionBasedPierProductivity(option: ProductivityOption): boolean {
  return option.productivity_unit === "天/节";
}
