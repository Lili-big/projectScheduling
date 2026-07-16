import type { BeamYardConfig, ErectionMachineConfig, GirderPlanningConfig } from "../../contracts";

export function YardMachineEditor({
  config,
  startDate,
  onChange,
}: {
  config: GirderPlanningConfig;
  startDate: string;
  onChange: (next: GirderPlanningConfig) => void;
}) {
  function addYardAndMachine() {
    const index = config.beam_yards.length + 1;
    const yard: BeamYardConfig = {
      beam_yard_id: `yard-${index}`,
      name: `${index}号梁场`,
      mileage_m: 0,
      side: "unknown",
      corridor_id: "main",
      production_start_date: startDate,
      daily_production_capacity: 4,
      initial_inventory_by_type: { default: 0 },
      max_inventory_by_type: null,
      calendar_id: "continuous",
      enabled: true,
    };
    const machine: ErectionMachineConfig = {
      erection_machine_id: `machine-${index}`,
      name: `${index}号架桥机`,
      beam_yard_id: yard.beam_yard_id,
      available_date: startDate,
      daily_erection_capacity: 1,
      first_span_preparation_days: 3,
      span_launching_days: 1,
      bridge_transfer_days: 2,
      side_switch_days: 1,
      calendar_id: "continuous",
      enabled: true,
    };
    onChange({
      ...config,
      beam_yards: [...config.beam_yards, yard],
      erection_machines: [...config.erection_machines, machine],
    });
  }

  function updateYard(index: number, patch: Partial<BeamYardConfig>) {
    onChange({
      ...config,
      beam_yards: config.beam_yards.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)),
    });
  }

  function updateMachine(index: number, patch: Partial<ErectionMachineConfig>) {
    onChange({
      ...config,
      erection_machines: config.erection_machines.map((item, itemIndex) =>
        itemIndex === index ? { ...item, ...patch } : item,
      ),
    });
  }

  return (
    <section className="girder-card">
      <div className="girder-card-heading">
        <div>
          <h3>梁场与架桥机</h3>
          <p>配置生产能力、期初库存和设备作业参数。</p>
        </div>
        <button type="button" onClick={addYardAndMachine}>新增梁场和设备</button>
      </div>
      <div className="girder-grid">
        {config.beam_yards.map((yard, index) => {
          const machine = config.erection_machines.find((item) => item.beam_yard_id === yard.beam_yard_id);
          const machineIndex = machine ? config.erection_machines.indexOf(machine) : -1;
          return (
            <div className="girder-editor-group" key={yard.beam_yard_id}>
              <label>梁场名称<input value={yard.name} onChange={(event) => updateYard(index, { name: event.target.value })} /></label>
              <label>中心里程（m）<input type="number" value={yard.mileage_m} onChange={(event) => updateYard(index, { mileage_m: Number(event.target.value) })} /></label>
              <label>日产量（片）<input type="number" min={0} value={yard.daily_production_capacity} onChange={(event) => updateYard(index, { daily_production_capacity: Number(event.target.value) })} /></label>
              <label>期初库存（默认梁型）<input type="number" min={0} value={yard.initial_inventory_by_type.default ?? 0} onChange={(event) => updateYard(index, { initial_inventory_by_type: { ...yard.initial_inventory_by_type, default: Number(event.target.value) } })} /></label>
              {machine && machineIndex >= 0 && (
                <>
                  <label>架桥机名称<input value={machine.name} onChange={(event) => updateMachine(machineIndex, { name: event.target.value })} /></label>
                  <label>日架设能力（跨/天）<input type="number" min={0.1} step={0.1} value={machine.daily_erection_capacity} onChange={(event) => updateMachine(machineIndex, { daily_erection_capacity: Number(event.target.value) })} /></label>
                  <label>转场天数<input type="number" min={0} value={machine.bridge_transfer_days} onChange={(event) => updateMachine(machineIndex, { bridge_transfer_days: Number(event.target.value) })} /></label>
                  <label>换幅天数<input type="number" min={0} value={machine.side_switch_days} onChange={(event) => updateMachine(machineIndex, { side_switch_days: Number(event.target.value) })} /></label>
                </>
              )}
            </div>
          );
        })}
        {!config.beam_yards.length && <div className="empty-state">尚未配置梁场和架桥机。</div>}
      </div>
    </section>
  );
}
