import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { GeneratedScheduleInput, ScheduleResult } from "../../contracts";
import { buildCrewFlowScene, crewSequenceLayout, dateAt, taskLabel, type CrewFlowVisit, type CrewFlowEdge } from "./pavementViewModel";

export function PavementCrewRoute({ result, generated }: { result: ScheduleResult; generated?: GeneratedScheduleInput }) {
  const scene = useMemo(() => buildCrewFlowScene(result, generated), [result, generated]);
  const [crewId, setCrewId] = useState<string | null>(null);
  const [visitKey, setVisitKey] = useState<string | null>(null);
  const [edgeKey, setEdgeKey] = useState<string | null>(null);
  const [localOnly, setLocalOnly] = useState(false);
  const [zoom, setZoom] = useState(1);
  const arrowId = useId().replace(/:/g, "");
  const axisScroll = useRef<HTMLDivElement>(null);
  const visitNodes = useRef(new Map<string, SVGGraphicsElement | HTMLButtonElement>());
  const focusRequested = useRef(false);
  const route = scene.routes.find(r => r.id === crewId) ?? scene.routes[0];
  const selected = route?.visits.find(v => v.key === visitKey) ?? route?.visits[0];
  const selectedEdge = route?.edges.find(e => e.key === edgeKey && e.to.key === selected?.key);
  const index = selected ? route.visits.indexOf(selected) : -1;
  const previous = route?.visits[index - 1], next = route?.visits[index + 1];
  const dates = (visit: CrewFlowVisit) => visit.start == null || visit.end == null ? "作业日期无效" : `${dateAt(result.plan_start_date, visit.start)} ～ ${dateAt(result.plan_start_date, visit.end - 1)}`;
  const label = (visit: CrewFlowVisit) => `第${visit.ordinal}次 · ${visit.name}`;
  const transferText = (visit: CrewFlowVisit) => visit.incomingTransfer?.issue ?? (visit.incomingTransfer?.days == null ? "转场时间未提供" : `转场 ${visit.incomingTransfer.days} 天`);
  const select = (visit: CrewFlowVisit | undefined, focus = false, edge?: CrewFlowEdge) => {
    if (!visit) return;
    focusRequested.current = focus;
    setVisitKey(visit.key); setEdgeKey(edge?.key ?? null);
  };
  const register = (key: string, node: SVGGraphicsElement | HTMLButtonElement | null) => {
    if (node) visitNodes.current.set(key, node); else visitNodes.current.delete(key);
  };
  useEffect(() => {
    const scroller = axisScroll.current, node = selected && visitNodes.current.get(selected.key);
    if (!scroller || !node) return;
    const target = node.getBoundingClientRect(), frame = scroller.getBoundingClientRect();
    if (target.top < frame.top + 24 || target.bottom > frame.bottom - 24) scroller.scrollTop += (target.top + target.bottom - frame.top - frame.bottom) / 2;
    if (target.left < frame.left + 30 || target.right > frame.right - 30) scroller.scrollLeft += (target.left + target.right - frame.left - frame.right) / 2;
    if (focusRequested.current) { node.focus({ preventScroll: true }); focusRequested.current = false; }
  }, [selected?.key, scene, zoom]);
  const edgeLabel = (edge: CrewFlowEdge) => `流转 ${edge.from.ordinal} → ${edge.to.ordinal}：${edge.from.name} → ${edge.to.name}`;
  const processes = (visit: CrewFlowVisit) => visit.tasks.map(t => taskLabel(t).replace("碎石垫层", "碎石").replace(/^水稳/, "")).join(" / ");

  return <section className="pv-section pv-flow-section" aria-label="机组里程轴与施工顺序">
    <div className="pv-section-heading"><div><h3>机组施工顺序</h3><p>施工段按里程排序 · 沿编号与箭头查看流转 · 同段回访向外分层</p></div>
      {route && <label className="pv-crew-picker">机组 <select aria-label="选择施工机组" value={route.id} onChange={e => { setCrewId(e.target.value); setVisitKey(null); setEdgeKey(null); }}>{scene.routes.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}</select></label>}
    </div>
    {!route || !selected ? <p className="pv-empty">没有已分配机组的作业可展示。</p> : <>
      <div className="pv-flow-toolbar">
        <label><input type="checkbox" checked={localOnly} onChange={e => setLocalOnly(e.target.checked)} />仅看当前前后箭线</label>
        <label>节点间距 <select aria-label="施工顺序图节点间距" value={zoom} onChange={e => setZoom(Number(e.target.value))}><option value={1}>紧凑</option><option value={1.5}>宽松</option><option value={2}>展开</option></select></label>
        <span className="pv-flow-legend"><i>1</i>到访顺序 <b>→</b>施工流转 <em>→</em>当前前后</span>
      </div>
      <div className="pv-route-summary"><span>{route.visits.length} 次到访 · {route.visits.reduce((n, v) => n + v.tasks.length, 0)} 道工序</span><span>连续同段合并 · 返回另行编号 · 点选箭线或序号查看</span></div>
      {scene.sourceNote && <p className="pv-note">{scene.sourceNote}</p>}
      {route.issues.map(issue => <p className="pv-note" key={issue}>{issue}</p>)}
      <div className="pv-route-layout">
        <div className="pv-axes-scroll pv-flow-scroll" ref={axisScroll} tabIndex={0} aria-label="双幅施工顺序图，可滚动">
          {scene.groups.filter(group => route.visits.some(v => v.location.coordinateGroupKey === group.key && !v.unlocatedReason)).map((group, groupIndex) => {
            const visits = route.visits.filter(v => v.location.coordinateGroupKey === group.key && !v.unlocatedReason);
            const drawableEdges = route.edges.filter(e => (e.kind === "same-side" || e.kind === "cross-side") && e.from.location.coordinateGroupKey === group.key);
            const isNear = (edge: CrewFlowEdge) => edge.from.key === selected.key || edge.to.key === selected.key;
            const edges = drawableEdges.filter(e => !localOnly || isNear(e)).sort((a, b) => Number(isNear(a)) - Number(isNear(b)));
            const layout = crewSequenceLayout(group, route.visits, zoom);
            return <div className="pv-flow-group" key={group.key} data-flow-group={group.key}>
              <h4>{group.label}<span>等宽施工段 · 编号表示先后 · 位置与间距为示意</span></h4>
              <svg className="pv-flow-canvas" height={layout.height} viewBox={`0 0 ${layout.width} ${layout.height}`} role="group" aria-label={`${group.label} 双幅施工顺序示意图`}>
                <defs>{["normal", "active"].map(kind => <marker key={kind} id={`${arrowId}-${groupIndex}-${kind}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0L10 5L0 10Z" fill={kind === "active" ? "#dc641d" : "#699a98"} /></marker>)}</defs>
                {(["left", "right"] as const).map(side => {
                  const header = side === "left" ? layout.leftBase : layout.rightHeader;
                  const fieldY = side === "left" ? 12 : layout.rightBase;
                  const fieldHeight = side === "left" ? layout.leftBase - 12 : layout.height - layout.rightBase - 12;
                  return <g key={side} data-flow-side={side}>
                    <text x={14} y={header + 28} className="pv-flow-side-label">{side === "left" ? "左幅" : "右幅"}</text>
                    {layout.sections[side].map((section, column) => {
                      const x = 64 + column * layout.columnWidth, center = x + layout.columnWidth / 2;
                      return <g key={section.key} data-flow-section={section.key}>
                        <rect x={x} y={fieldY} width={layout.columnWidth} height={fieldHeight} className={`pv-flow-field is-${side} ${column % 2 ? "is-alternate" : ""}`} />
                        <line x1={x} x2={x} y1={fieldY} y2={fieldY + fieldHeight} className="pv-flow-gridline" />
                        <rect x={x} y={header} width={layout.columnWidth} height={56} className={`pv-flow-section-cell is-${side}`} />
                        <text x={center} y={header + 17} textAnchor="middle" className="pv-flow-section-name">{section.name}</text>
                        <text x={center} y={header + 33} textAnchor="middle" className="pv-flow-section-chainage">{section.rawStart}</text>
                        <text x={center} y={header + 47} textAnchor="middle" className="pv-flow-section-chainage">{section.rawEnd}</text>
                      </g>;
                    })}
                    {!visits.some(v => v.location.side === side) && <text x={layout.width / 2} y={fieldY + fieldHeight / 2} textAnchor="middle" className="pv-flow-empty">本机组该幅无作业</text>}
                  </g>;
                })}
                <text x={layout.width / 2} y={layout.leftBase + 72} textAnchor="middle" className="pv-flow-axis-note">各幅施工段按里程递增 →</text>
                {edges.map(edge => {
                  const from = layout.nodes.get(edge.from.key)!, to = layout.nodes.get(edge.to.key)!;
                  const dx = to.x - from.x, dy = to.y - from.y, length = Math.hypot(dx, dy) || 1;
                  const x1 = from.x + dx / length * 17, x2 = to.x - dx / length * 17;
                  const y1 = from.y + dy / length * 17, y2 = to.y - dy / length * 17;
                  const middle = (y1 + y2) / 2;
                  const bend = (edge.from.ordinal % 3 - 1) * 9;
                  let path = `M${x1} ${y1} Q${x1} ${middle + bend} ${(x1 + x2) / 2} ${middle + bend} Q${x2} ${middle + bend} ${x2} ${y2}`;
                  let arrowX = (x1 + x2) / 2, arrowY = middle + bend;
                  let arrowDx = Math.sign(dx), arrowDy = dx === 0 ? Math.sign(dy) : 0;
                  if (edge.kind === "cross-side") {
                    // Cross the section headers on their borders, keeping names and chainages readable.
                    const fromPort = from.x + layout.columnWidth / 2, toPort = to.x + layout.columnWidth / 2;
                    arrowX = (fromPort + toPort) / 2; arrowY = layout.leftBase + 68 + (edge.from.ordinal % 3 - 1) * 5;
                    path = `M${from.x + 17} ${from.y} H${fromPort} V${arrowY} H${toPort} V${to.y} H${to.x + 17}`;
                    arrowDx = Math.sign(toPort - fromPort); arrowDy = fromPort === toPort ? Math.sign(dy) : 0;
                  } else if (dx !== 0) {
                    // Use column borders and the gap above a node row; never pass through an unrelated visit.
                    const direction = Math.sign(dx), fromPort = from.x + direction * layout.columnWidth / 2;
                    const toPort = to.x - direction * layout.columnWidth / 2;
                    if (Math.abs(fromPort - toPort) < .01) {
                      path = `M${from.x + direction * 17} ${from.y} H${fromPort} V${to.y} H${to.x - direction * 17}`;
                      arrowX = dy === 0 ? (from.x + to.x) / 2 : fromPort; arrowY = (from.y + to.y) / 2;
                      arrowDx = dy === 0 ? direction : 0; arrowDy = dy === 0 ? 0 : Math.sign(dy);
                    } else {
                      arrowX = (fromPort + toPort) / 2; arrowY = Math.min(from.y, to.y) - 23;
                      path = `M${from.x + direction * 17} ${from.y} H${fromPort} V${arrowY} H${toPort} V${to.y} H${to.x - direction * 17}`;
                      arrowDx = direction; arrowDy = 0;
                    }
                  }
                  const directionPath = `M${arrowX - arrowDx * 6} ${arrowY - arrowDy * 6} L${arrowX} ${arrowY} L${arrowX + arrowDx * 6} ${arrowY + arrowDy * 6}`;
                  const active = isNear(edge), activate = () => select(edge.to, false, edge);
                  return <g key={edge.key} role="button" tabIndex={0} aria-label={edgeLabel(edge)} aria-pressed={selectedEdge?.key === edge.key} data-flow-edge={edge.key} data-flow-kind={edge.kind} className={`pv-flow-edge ${active ? "is-active" : ""}`} onClick={activate} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); activate(); } }}>
                    <title>{`${edgeLabel(edge)} · ${transferText(edge.to)}`}</title>
                    {active && <path d={path} className="pv-flow-edge-halo" />}
                    <path d={path} className="pv-flow-edge-line" markerEnd={`url(#${arrowId}-${groupIndex}-${active ? "active" : "normal"})`} />
                    <path d={directionPath} className="pv-flow-edge-line" markerMid={`url(#${arrowId}-${groupIndex}-${active ? "active" : "normal"})`} />
                    <path d={path} className="pv-flow-edge-hit" />
                  </g>;
                })}
                {[...visits].sort((a, b) => Number(a.key === selected.key) - Number(b.key === selected.key)).map(visit => {
                  const { x, y } = layout.nodes.get(visit.key)!, active = visit.key === selected.key;
                  const endpoint = visit.ordinal === 1 ? "起点" : visit.ordinal === route.visits.length ? "终点" : "";
                  const activate = () => select(visit);
                  return <g ref={node => register(visit.key, node)} key={visit.key} transform={`translate(${x},${y})`} data-flow-visit={visit.key} data-flow-ordinal={visit.ordinal} role="button" tabIndex={0} aria-label={`查看${label(visit)} · ${dates(visit)}`} aria-pressed={active} className={`pv-flow-visit ${active ? "is-active" : ""} has-label`} onClick={activate} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); activate(); } }}>
                    <title>{`${label(visit)} · ${processes(visit)} · ${dates(visit)}`}</title><circle className="pv-flow-visit-hit" r={18} /><circle className="pv-flow-node" r={14} />
                    <text textAnchor="middle" dominantBaseline="central">{visit.ordinal}</text>
                    <text y={29} textAnchor="middle" className="pv-flow-process">{processes(visit).length > 13 ? `${processes(visit).slice(0, 12)}…` : processes(visit)}</text>
                    {endpoint && <text x={20} y={4} className="pv-flow-endpoint">{endpoint}</text>}
                  </g>;
                })}
              </svg>
            </div>;
          })}
          {route.visits.some(v => v.unlocatedReason) && <div className="pv-unlocated"><h4>无法按统一里程定位 / 未投到左右幅</h4>{route.visits.filter(v => v.unlocatedReason).map(visit => <button ref={node => register(visit.key, node)} type="button" key={visit.key} aria-pressed={visit.key === selected.key} onClick={() => select(visit)}><b>{visit.ordinal}</b><span>{visit.name}<small>{visit.location.rawStart} ～ {visit.location.rawEnd} · {visit.unlocatedReason}</small></span></button>)}</div>}
          {route.edges.some(e => e.kind === "external" || e.kind === "unlocated") && <details className="pv-flow-connections"><summary>跨坐标组 / 无法绘制的衔接</summary>{route.edges.filter(e => e.kind === "external" || e.kind === "unlocated").map(edge => <button type="button" key={edge.key} onClick={() => select(edge.to, true, edge)}>{edgeLabel(edge)}<small>{edge.reason}</small></button>)}</details>}
        </div>
        <aside className="pv-visit-detail" aria-label="到访详情">
          <div className="pv-step-controls"><button type="button" disabled={!previous} onClick={() => select(previous, true)}>← 上一步</button><span>{selected.ordinal} / {route.visits.length}</span><button type="button" disabled={!next} onClick={() => select(next, true)}>下一步 →</button></div>
          <label className="pv-flow-jump">定位到访 <select aria-label="定位机组到访" value={selected.key} onChange={e => select(route.visits.find(v => v.key === e.target.value), true)}>{route.visits.map(v => <option value={v.key} key={v.key}>{label(v)}</option>)}</select></label>
          {selectedEdge && <p className="pv-flow-selected-edge" role="status">已选流转：{selectedEdge.from.ordinal} → {selectedEdge.to.ordinal}{selectedEdge.reason && ` · ${selectedEdge.reason}`}</p>}
          <p className="pv-eyebrow">第 {selected.ordinal} 次到访{selected.ordinal === 1 ? " · 起点" : selected.ordinal === route.visits.length ? " · 终点" : ""}</p><h4>{selected.name}</h4>
          <p>{selected.location.rawStart} ～ {selected.location.rawEnd}</p><p>{dates(selected)}</p>
          <p className="pv-note">{selected.unlocatedReason || selected.location.axisLabel}</p>
          <details open><summary>本次连续施工 · {selected.tasks.length} 道工序</summary><ol>{selected.tasks.map(t => <li key={t.id}><strong>{taskLabel(t)}</strong><small>{t.start_date} ～ {t.finish_date}</small></li>)}</ol></details>
          {previous ? <div className="pv-connection"><span>从第 {previous.ordinal} 次到访转入</span><button type="button" onClick={() => select(previous, true)}>{previous.name}</button><small>{previous.location.axisLabel} · {transferText(selected)}</small>
            {selected.incomingTransfer?.days != null && selected.incomingTransfer.days > 0 && selected.incomingTransfer.start != null && selected.incomingTransfer.end != null && <small>{dateAt(result.plan_start_date, selected.incomingTransfer.start)} ～ {dateAt(result.plan_start_date, selected.incomingTransfer.end - 1)}</small>}</div> : <p className="pv-note">本机组施工起点</p>}
          {next ? <div className="pv-connection"><span>下一步 · 第 {next.ordinal} 次到访</span><button type="button" onClick={() => select(next, true)}>{next.name}</button><small>{next.location.axisLabel} · {transferText(next)}</small></div> : <p className="pv-note">本机组最后一次到访</p>}
        </aside>
      </div>
      <p className="pv-note">按节点编号和箭头读取施工顺序。同段回访另起节点；不同施工段的纵向位置不表示时间先后。段宽、位置与间距均为示意，实际日期及转场见详情。</p>
    </>}
  </section>;
}
