import { pavementUnits, emptyPavementSettings, pavementShiftConfigErrors } from "../../domain/pavement";
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
import type { ProcessTemplate, ProductivityOption, ScenarioInput, PavementSettings, PavementShiftRegime } from "../../contracts";

export function ProcessTab({
  scenario,
  onUpdateProcess,
  onSaveProcessLibrary,
  savingProcessLibrary,
  processLibraryDirty,
  onUpdatePavementSettings,
}: {
  scenario: ScenarioInput;
  onUpdateProcess: (index: number, patch: Partial<ProcessTemplate>) => void;
  onSaveProcessLibrary: () => void;
  savingProcessLibrary: boolean;
  processLibraryDirty: boolean;
  onUpdatePavementSettings?: (settings: PavementSettings) => void;
}) {
  const pavementSettings = scenario.pavement_settings ?? emptyPavementSettings();
  const regimes = pavementSettings.shift_regimes ?? [];
  const hasIncompleteShift = scenario.engineering_domain === "pavement" && regimes.some(regime => !regime.start_date);
  const shiftErrors = scenario.engineering_domain === "pavement"
    ? pavementShiftConfigErrors(regimes.filter(regime => regime.start_date)) : [];

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
        subtitle={scenario.engineering_domain === "pavement" ? "每套机组的综合日工效；参考值需按项目核实，施工天数向上取整" : "工艺模板按构件类型和适用工艺维护，关键资源由工艺规则自动匹配"}
        action={
          <button
            className="secondary"
            type="button"
            onClick={onSaveProcessLibrary}
            disabled={savingProcessLibrary || !processLibraryDirty || hasIncompleteShift || shiftErrors.length > 0}
            title={hasIncompleteShift ? "填写班制起始日期后即可保存" : "保存到后端本地 JSON 配置文件"}
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
                            {scenario.engineering_domain === "pavement" ? (
                              <select aria-label="路面工效单位" value={option.productivity_unit} onChange={event => patchProductivityOption(processIndex, option.id, { productivity_unit: event.target.value })}>
                                {pavementUnits.map(unit => <option key={unit}>{unit}</option>)}
                              </select>
                            ) : process.component_type === "pile" ? (
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
                            <span className="text-pill productivity-source-pill">
                              {scenario.engineering_domain === "pavement" && option.quantity_source === "quantity" && option.productivity_unit === "m/天"
                                ? "按施工长度（m）计量"
                                : quantitySourceLabels[option.quantity_source] ?? option.quantity_source}
                            </span>
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
      {scenario.engineering_domain === "pavement" && <PavementShiftRegimes settings={pavementSettings}
        onChange={onUpdatePavementSettings} saving={savingProcessLibrary} errors={shiftErrors} />}
    </section>
  );
}

function PavementShiftRegimes({ settings, onChange, saving, errors }: {
  settings: PavementSettings;
  onChange?: (settings: PavementSettings) => void;
  saving: boolean;
  errors: string[];
}) {
  const regimes = settings.shift_regimes ?? [];
  const disabled = saving || !onChange;
  const update = (next: PavementShiftRegime[]) => onChange?.({ ...settings, shift_regimes: next });
  const edit = (index: number, patch: Partial<PavementShiftRegime>) => update(regimes.map((regime, i) => i === index ? { ...regime, ...patch } : regime));

  return <section className="pavement-shift-regimes" aria-labelledby="pavement-shift-title">
    <h3 id="pavement-shift-title">班制配置（单／双班）</h3>
    <p id="pavement-shift-help">在表格内直接编辑，修改后点击上方“保存”。结束日期留空表示持续生效，未覆盖日期按单班。</p>
    {!!errors.length && <ul className="notice error" role="alert">{errors.map(error => <li key={error}>{error}</li>)}</ul>}
    <div className="table-wrap"><table className="pavement-relation-table pavement-shift-table" aria-label="班制区间" aria-describedby="pavement-shift-help">
      <thead><tr><th scope="col">序号</th><th scope="col">起始日期</th><th scope="col">结束日期（可留空）</th><th scope="col">班制</th><th scope="col">操作</th></tr></thead>
      <tbody>
        {regimes.map((regime, i) => <tr key={i}>
          <th scope="row">{i + 1}</th>
          <td><div className="pavement-shift-start"><input type="date" aria-required="true" disabled={disabled} aria-label={`第${i + 1}行起始日期`}
            aria-describedby={!regime.start_date ? `pavement-shift-pending-${i}` : undefined}
            value={regime.start_date} onChange={event => edit(i, { start_date: event.target.value })} />
            {!regime.start_date && <span id={`pavement-shift-pending-${i}`}>待填写</span>}</div></td>
          <td><div className="pavement-shift-end"><input type="date" disabled={disabled} aria-label={`第${i + 1}行结束日期`}
            value={regime.end_date ?? ""} onChange={event => edit(i, { end_date: event.target.value || null })} />
            {!regime.end_date && <span>持续生效</span>}</div></td>
          <td><select disabled={disabled} aria-label={`第${i + 1}行班制`} value={regime.shifts} onChange={event => edit(i, { shifts: Number(event.target.value) })}>
            <option value="1">单班</option><option value="2">双班（日产出×2）</option>
          </select></td>
          <td><button type="button" disabled={disabled} aria-label={`删除第${i + 1}行班制区间`} onClick={() => update(regimes.filter((_, j) => j !== i))}>删除</button></td>
        </tr>)}
        {!regimes.length && <tr><td colSpan={5} className="pavement-shift-empty">暂未配置，全部按单班计算。可在下方新增一行。</td></tr>}
      </tbody>
      <tfoot><tr><td colSpan={5}><button type="button" className="pavement-shift-add" disabled={disabled} aria-label="新增班制区间"
        onClick={() => update([...regimes, { start_date: "", end_date: null, shifts: 2 }])}>＋ 新增一行</button></td></tr></tfoot>
    </table></div>
    <p>双班为每台机械增配 1 组班组，白班＋夜班作业，日产出按基准工效翻倍；养生和转场天数不变。</p>
  </section>;
}
