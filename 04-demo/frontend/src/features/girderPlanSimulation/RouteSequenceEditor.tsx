import type {
  BeamYardPlan,
  ConfirmedPathSegment,
  ErectionLinePlan,
  GirderPlanReadiness,
  LineGraphSnapshot,
  ManualRoutePlan,
} from "../../contracts";
import { girderTargets, moveItem, yardNodeId } from "./adapter";

export function RouteSequenceEditor({
  graph,
  yards,
  lines,
  routes,
  readiness,
  onChange,
}: {
  graph: LineGraphSnapshot | null;
  yards: BeamYardPlan[];
  lines: ErectionLinePlan[];
  routes: ManualRoutePlan[];
  readiness: GirderPlanReadiness | null;
  onChange: (routes: ManualRoutePlan[]) => void;
}) {
  const targets = girderTargets(graph?.nodes ?? []);

  function ensureRoute(yard: BeamYardPlan) {
    if (routes.some((item) => item.beam_yard_id === yard.beam_yard_id)) return;
    const line = lines.find((item) => item.beam_yard_id === yard.beam_yard_id);
    if (!line) return;
    onChange([...routes, {
      route_plan_id: `route-${yard.beam_yard_id}`,
      beam_yard_id: yard.beam_yard_id,
      erection_line_id: line.erection_line_id,
      name: `${yard.name}架梁顺序`,
      target_node_ids: [],
      confirmed_paths: [],
      confirmed: false,
    }]);
  }

  function updateRoute(routeId: string, patch: Partial<ManualRoutePlan>) {
    onChange(routes.map((item) => item.route_plan_id === routeId ? { ...item, ...patch } : item));
  }

  return (
    <section className="girder-sim-card" aria-label="人工架梁顺序">
      <div className="girder-sim-card-heading">
        <div><h3>人工架梁顺序</h3><p>只排列待架桥梁幅别；中间路桥隧通行节点由线路图自动补齐。</p></div>
      </div>
      {yards.map((yard) => {
        const route = routes.find((item) => item.beam_yard_id === yard.beam_yard_id);
        if (!route) return <button type="button" key={yard.beam_yard_id} onClick={() => ensureRoute(yard)}>为{yard.name}建立一条架梁线路</button>;
        const deploymentNodeId = yardNodeId(yard, graph?.nodes ?? []);
        const pairs = route.target_node_ids.map((target, index) => ({
          from: index === 0 ? deploymentNodeId : route.target_node_ids[index - 1],
          to: target,
        }));
        return (
          <article className="girder-sim-route" key={route.route_plan_id} data-entity-id={route.route_plan_id} tabIndex={-1}>
            <div className="girder-sim-route-title">
              <input value={route.name} onChange={(event) => updateRoute(route.route_plan_id, { name: event.target.value })} />
              <label><input type="checkbox" checked={route.confirmed} onChange={(event) => updateRoute(route.route_plan_id, { confirmed: event.target.checked })} />顺序已人工确认</label>
            </div>
            <div className="girder-sim-target-picker">
              {targets.map((target) => {
                const assigned = route.target_node_ids.includes(target.node_id);
                const assignedElsewhere = routes.some((item) => item.route_plan_id !== route.route_plan_id && item.target_node_ids.includes(target.node_id));
                return <label key={target.node_id} className={assignedElsewhere ? "assigned" : ""}>
                  <input
                    type="checkbox"
                    checked={assigned}
                    disabled={assignedElsewhere}
                    onChange={(event) => updateRoute(route.route_plan_id, {
                      target_node_ids: event.target.checked
                        ? [...route.target_node_ids, target.node_id]
                        : route.target_node_ids.filter((item) => item !== target.node_id),
                      confirmed: false,
                    })}
                  />
                  {target.name}（{target.beam_demands.map((item) => `${item.beam_type_name} ${item.beam_count}片`).join("、")}）
                </label>;
              })}
            </div>
            <ol className="girder-sim-sequence">
              {route.target_node_ids.map((targetId, index) => {
                const target = targets.find((item) => item.node_id === targetId);
                return <li key={targetId}>
                  <span>{index + 1}. {target?.name ?? targetId}</span>
                  <div><button type="button" onClick={() => updateRoute(route.route_plan_id, { target_node_ids: moveItem(route.target_node_ids, index, -1), confirmed: false })}>上移</button><button type="button" onClick={() => updateRoute(route.route_plan_id, { target_node_ids: moveItem(route.target_node_ids, index, 1), confirmed: false })}>下移</button></div>
                </li>;
              })}
            </ol>
            {pairs.map((pair) => {
              const confirmed = route.confirmed_paths.find((item) => item.from_target_node_id === pair.from && item.to_target_node_id === pair.to);
              return <label className="girder-sim-path-confirm" key={`${pair.from}-${pair.to}`}>
                路径 {pair.from} → {pair.to} 的确认边 ID（唯一通路可留空）
                <input
                  list="girder-sim-edge-ids"
                  value={confirmed?.edge_ids.join(",") ?? ""}
                  placeholder="多路径时输入按顺序排列的 edge_id，以逗号分隔"
                  onChange={(event) => updateRoute(route.route_plan_id, {
                    confirmed_paths: updateConfirmedPath(route.confirmed_paths, pair.from, pair.to, event.target.value),
                    confirmed: false,
                  })}
                />
              </label>;
            })}
            <datalist id="girder-sim-edge-ids">{(graph?.edges ?? []).map((edge) => <option key={edge.edge_id} value={edge.edge_id} />)}</datalist>
            {readiness?.expanded_routes[route.route_plan_id] && <div className="girder-sim-expanded">自动补齐：{readiness.expanded_routes[route.route_plan_id].join(" → ")}</div>}
          </article>
        );
      })}
      {yards.length === 0 && <div className="girder-sim-empty">请先维护梁场。</div>}
    </section>
  );
}

function updateConfirmedPath(
  paths: ConfirmedPathSegment[],
  from: string,
  to: string,
  rawEdgeIds: string,
): ConfirmedPathSegment[] {
  const others = paths.filter((item) => item.from_target_node_id !== from || item.to_target_node_id !== to);
  const edgeIds = rawEdgeIds.split(",").map((item) => item.trim()).filter(Boolean);
  return edgeIds.length === 0 ? others : [...others, {
    from_target_node_id: from,
    to_target_node_id: to,
    edge_ids: edgeIds,
    source: "user_selected_path",
  }];
}
