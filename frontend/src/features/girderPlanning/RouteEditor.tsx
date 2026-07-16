import type { GirderPlanningConfig, GirderRouteConfig, GirderWorkPoint } from "../../contracts";

export function RouteEditor({
  config,
  workpoints,
  onChange,
}: {
  config: GirderPlanningConfig;
  workpoints: GirderWorkPoint[];
  onChange: (next: GirderPlanningConfig) => void;
}) {
  function addRoute() {
    const index = config.routes.length + 1;
    const yard = config.beam_yards[0];
    const machine = config.erection_machines.find((item) => item.beam_yard_id === yard?.beam_yard_id);
    const route: GirderRouteConfig = {
      route_id: `route-${index}`,
      name: `架梁路线${index}`,
      beam_yard_id: yard?.beam_yard_id ?? "",
      erection_machine_id: machine?.erection_machine_id ?? "",
      route_direction: "custom",
      enabled: true,
      confirmed: false,
      nodes: [],
    };
    onChange({ ...config, routes: [...config.routes, route] });
  }

  function updateRoute(index: number, patch: Partial<GirderRouteConfig>) {
    onChange({ ...config, routes: config.routes.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)) });
  }

  function toggleNode(routeIndex: number, workpointId: string) {
    const route = config.routes[routeIndex];
    const exists = route.nodes.some((item) => item.workpoint_id === workpointId);
    const nodes = exists
      ? route.nodes.filter((item) => item.workpoint_id !== workpointId).map((item, index) => ({ ...item, sequence_index: index }))
      : [...route.nodes, { route_node_id: `${route.route_id}-node-${route.nodes.length + 1}`, workpoint_id: workpointId, sequence_index: route.nodes.length, node_kind: "workpoint" as const }];
    updateRoute(routeIndex, { nodes, confirmed: false });
  }

  return (
    <section className="girder-card">
      <div className="girder-card-heading">
        <div><h3>固定架梁路线</h3><p>节点顺序由用户确认，联合计算只更新日期和派生归属。</p></div>
        <button type="button" onClick={addRoute} disabled={!config.beam_yards.length}>新增路线</button>
      </div>
      {config.routes.map((route, routeIndex) => (
        <div className="girder-route" key={route.route_id}>
          <div className="girder-grid compact">
            <label>路线名称<input value={route.name} onChange={(event) => updateRoute(routeIndex, { name: event.target.value, confirmed: false })} /></label>
            <label>梁场<select value={route.beam_yard_id} onChange={(event) => updateRoute(routeIndex, { beam_yard_id: event.target.value, confirmed: false })}>{config.beam_yards.map((item) => <option key={item.beam_yard_id} value={item.beam_yard_id}>{item.name}</option>)}</select></label>
            <label>架桥机<select value={route.erection_machine_id} onChange={(event) => updateRoute(routeIndex, { erection_machine_id: event.target.value, confirmed: false })}>{config.erection_machines.filter((item) => item.beam_yard_id === route.beam_yard_id).map((item) => <option key={item.erection_machine_id} value={item.erection_machine_id}>{item.name}</option>)}</select></label>
            <label className="girder-check"><input type="checkbox" checked={route.enabled} onChange={(event) => updateRoute(routeIndex, { enabled: event.target.checked, confirmed: false })} />启用路线</label>
          </div>
          <div className="girder-node-picker">
            {workpoints.map((workpoint) => (
              <label key={workpoint.workpoint_id}>
                <input type="checkbox" checked={route.nodes.some((item) => item.workpoint_id === workpoint.workpoint_id)} onChange={() => toggleNode(routeIndex, workpoint.workpoint_id)} />
                {workpoint.name} · {workpoint.side}
              </label>
            ))}
            {!workpoints.length && <span className="muted">请先确认项目主数据版本，系统将按工点与幅别派生路线节点。</span>}
          </div>
          <button type="button" className={route.confirmed ? "secondary" : ""} onClick={() => updateRoute(routeIndex, { confirmed: !route.confirmed })}>{route.confirmed ? "已确认节点顺序" : "确认节点顺序"}</button>
        </div>
      ))}
      {!config.routes.length && <div className="empty-state">尚未配置启用路线。</div>}
    </section>
  );
}
