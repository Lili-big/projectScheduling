import { Loader2, Save } from "lucide-react";
import { PanelTitle } from "../../components/common/PanelTitle";
import { componentLabels, componentSortIndex, durationMethodLabels, quantitySourceLabels } from "../../domain/labels";
import {
  defaultStandardSectionHeightForUnit,
  isSectionBasedPierProductivity,
  normalizeProductivityOptionForProcess,
  pileProductivityUnitOptions,
  sectionHeightForOption,
  segmentedPierProductivityUnitOptions,
  supportsSegmentedPierUnits,
} from "../../domain/productivity";
import { processResourceLabel } from "../../domain/resources";
import type { ProcessTemplate, ProductivityOption, ScenarioInput } from "../../types/scheduler";

export function ProcessTab({
  scenario,
  onUpdateProcess,
  onSaveProcessLibrary,
  savingProcessLibrary,
  processLibraryDirty,
}: {
  scenario: ScenarioInput;
  onUpdateProcess: (index: number, patch: Partial<ProcessTemplate>) => void;
  onSaveProcessLibrary: () => void;
  savingProcessLibrary: boolean;
  processLibraryDirty: boolean;
}) {
  function productivityOptions(process: ProcessTemplate): ProductivityOption[] {
    return process.productivity_options?.length
      ? process.productivity_options
      : [
          {
            id: `${process.id}-default`,
            name: "默认工效",
            duration_method: process.duration_method,
            quantity_source: process.quantity_source,
            productivity_value: process.productivity_value,
            productivity_unit: process.productivity_unit,
            standard_section_height_m: defaultStandardSectionHeightForUnit(process.productivity_unit),
            is_default: true,
          },
        ];
  }

  function patchProductivityOption(processIndex: number, optionId: string, patch: Partial<ProductivityOption>) {
    const process = scenario.process_library[processIndex];
    const nextOptions = productivityOptions(process).map((option) => {
      if (option.id !== optionId) return option;
      return { ...option, ...patch };
    });
    updateProcessWithOptions(processIndex, nextOptions);
  }

  function addProductivityOption(processIndex: number) {
    const process = scenario.process_library[processIndex];
    const options = productivityOptions(process);
    const defaultOption = options.find((option) => option.is_default) ?? options[0];
    updateProcessWithOptions(processIndex, [
      ...options,
      {
        ...defaultOption,
        id: `${process.id}-option-${Date.now()}`,
        name: `工效分组${options.length + 1}`,
        is_default: false,
      },
    ]);
  }

  function removeProductivityOption(processIndex: number, optionId: string) {
    const options = productivityOptions(scenario.process_library[processIndex]);
    if (options.length <= 1) return;
    const removed = options.find((option) => option.id === optionId);
    let nextOptions = options.filter((option) => option.id !== optionId);
    if (removed?.is_default) {
      nextOptions = nextOptions.map((option, index) => ({ ...option, is_default: index === 0 }));
    }
    updateProcessWithOptions(processIndex, nextOptions);
  }

  function setDefaultProductivityOption(processIndex: number, optionId: string) {
    updateProcessWithOptions(
      processIndex,
      productivityOptions(scenario.process_library[processIndex]).map((option) => ({ ...option, is_default: option.id === optionId })),
    );
  }

  function updateProcessWithOptions(processIndex: number, options: ProductivityOption[]) {
    const process = scenario.process_library[processIndex];
    const normalizedByUnit = options.map((option) => normalizeProductivityOptionForProcess(process, option));
    const defaultOption = normalizedByUnit.find((option) => option.is_default) ?? normalizedByUnit[0];
    const normalizedOptions = normalizedByUnit.map((option) => ({ ...option, is_default: option.id === defaultOption.id }));
    onUpdateProcess(processIndex, {
      productivity_options: normalizedOptions,
      duration_method: defaultOption.duration_method,
      quantity_source: defaultOption.quantity_source,
      productivity_value: defaultOption.productivity_value,
      productivity_unit: defaultOption.productivity_unit,
    });
  }

  const sortedProcessEntries = scenario.process_library
    .map((process, processIndex) => ({ process, processIndex }))
    .sort((left, right) => (
      componentSortIndex(left.process.component_type) - componentSortIndex(right.process.component_type)
      || left.processIndex - right.processIndex
    ));

  return (
    <section className="panel full process-library-panel">
      <PanelTitle
        title="施工工艺及工效库"
        subtitle="工艺模板按构件类型和适用工艺维护，关键资源由工艺规则自动匹配"
        action={
          <button
            className="secondary"
            type="button"
            onClick={onSaveProcessLibrary}
            disabled={savingProcessLibrary || !processLibraryDirty}
            title="保存到后端本地 JSON 配置文件"
            aria-label="保存工艺工效库"
          >
            {savingProcessLibrary ? <Loader2 className="spin" size={16} /> : <Save size={16} />}
            保存
          </button>
        }
      />
      <div className="table-wrap process-library-table">
        <table>
          <thead>
            <tr>
              <th>构件</th>
              <th>工艺名称</th>
              <th>工效分组</th>
              <th>默认资源</th>
            </tr>
          </thead>
          <tbody>
            {sortedProcessEntries.map(({ process, processIndex }) => {
              const options = productivityOptions(process);
              return (
                <tr key={process.id}>
                  <td><span className="tag">{componentLabels[process.component_type]}</span></td>
                  <td>
                    <span className="process-name-text">{process.process_name}</span>
                  </td>
                  <td>
                    <div className="productivity-groups">
                      {options.map((option, optionIndex) => {
                        const isSegmentedPierProcess = supportsSegmentedPierUnits(process);
                        const showSectionHeight = isSectionBasedPierProductivity(option);
                        const isLastOption = optionIndex === options.length - 1;
                        return (
                          <div className={`productivity-group ${option.is_default ? "default" : ""}`} key={option.id}>
                            <input
                              className="productivity-name-input"
                              value={option.name}
                              onChange={(event) => patchProductivityOption(processIndex, option.id, { name: event.target.value })}
                            />
                            <input
                              type="number"
                              min={0.1}
                              step={0.1}
                              value={option.productivity_value}
                              onChange={(event) => patchProductivityOption(processIndex, option.id, { productivity_value: Number(event.target.value) })}
                              aria-label="工效值"
                            />
                            {process.component_type === "pile" ? (
                              <select
                                className="productivity-unit-control"
                                value={option.productivity_unit}
                                onChange={(event) => patchProductivityOption(processIndex, option.id, { productivity_unit: event.target.value })}
                              >
                                {pileProductivityUnitOptions.map((item) => (
                                  <option value={item.unit} key={item.unit}>{item.unit}</option>
                                ))}
                              </select>
                            ) : isSegmentedPierProcess ? (
                              <select
                                className="productivity-unit-control"
                                value={option.productivity_unit}
                                onChange={(event) => patchProductivityOption(processIndex, option.id, { productivity_unit: event.target.value })}
                              >
                                {segmentedPierProductivityUnitOptions.map((item) => (
                                  <option value={item.unit} key={item.unit}>{item.unit}</option>
                                ))}
                              </select>
                            ) : (
                              <span className="text-pill productivity-unit-control">{option.productivity_unit}</span>
                            )}
                            <span className="section-height-field">
                              {showSectionHeight ? (
                                <>
                                  <input
                                    type="number"
                                    min={0.1}
                                    step={0.1}
                                    value={sectionHeightForOption(option)}
                                    onChange={(event) => patchProductivityOption(processIndex, option.id, { standard_section_height_m: Number(event.target.value) })}
                                    aria-label="标准节高"
                                  />
                                  <span className="unit">m/节</span>
                                </>
                              ) : (
                                <span className="section-height-placeholder">-</span>
                              )}
                            </span>
                            <span className="text-pill productivity-method-pill">{durationMethodLabels[option.duration_method] ?? option.duration_method}</span>
                            <span className="text-pill productivity-source-pill">{quantitySourceLabels[option.quantity_source] ?? option.quantity_source}</span>
                            {option.is_default ? (
                              <span className="default-badge">默认分组</span>
                            ) : (
                              <button
                              className="mini-button set-default"
                              type="button"
                              onClick={() => setDefaultProductivityOption(processIndex, option.id)}
                            >
                                设为默认
                              </button>
                            )}
                            <button
                              className="mini-button"
                              type="button"
                              disabled={options.length <= 1}
                              onClick={() => removeProductivityOption(processIndex, option.id)}
                            >
                              删除
                            </button>
                            {isLastOption ? (
                              <button className="mini-button add" type="button" onClick={() => addProductivityOption(processIndex)}>
                                新增
                              </button>
                            ) : (
                              <span className="productivity-add-spacer" />
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </td>
                  <td>
                    {processResourceLabel(process, scenario.resource_pools)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
