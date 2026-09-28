"""A fleet has one actual path. Only selected adjacent arcs incur transfer."""
from collections import defaultdict
from graphlib import TopologicalSorter

from ....project_master.validation import resolve_roadbed_handover


def forbidden_fleet_edges(tasks, links, checkpoint=lambda: None):
    """Only nonnegative FS chains prove end-before-start ordering."""
    graph = {t.id: set() for t in tasks}
    for link in links:
        if link.relationship == "FS" and link.lag_days >= 0:
            graph[link.successor_id].add(link.predecessor_id)
    ancestors = defaultdict(set)
    forbidden = set()
    for tid in TopologicalSorter(graph).static_order():
        checkpoint()
        for parent in graph[tid]:
            ancestors[tid].add(parent)
            ancestors[tid].update(ancestors[parent])
        forbidden.update((tid, parent) for parent in ancestors[tid])
    normal = [t.id for t in tasks if resolve_roadbed_handover(t.properties)[0] != "pending"]
    # Applied within each resource's circuit below: after entering a pending
    # section, that actual fleet cannot return to normal work. Other fleets
    # and unresourced preparation tasks have no shared completion barrier.
    for task in tasks:
        checkpoint()
        if resolve_roadbed_handover(task.properties)[0] == "pending":
            forbidden.update((task.id, tid) for tid in normal)
    return forbidden


def add_pavement_fleet_paths(model, tasks, resources, candidates, starts, ends, horizon,
                             links=(), checkpoint=lambda: None):
    assignments, arcs = {}, []
    route_vars = {}
    forbidden = forbidden_fleet_edges(tasks, links, checkpoint)
    for task in tasks:
        checkpoint()
        if not candidates[task.id]: continue
        choices = []
        for resource in candidates[task.id]:
            var = model.NewBoolVar(f"assign:{task.id}:{resource.id}")
            assignments[task.id, resource.id] = var
            choices.append(var)
        model.AddExactlyOne(choices)
    for resource in resources:
        checkpoint()
        eligible = [t for t in tasks if (t.id, resource.id) in assignments]
        if not eligible: continue
        circuit = []
        empty = model.NewBoolVar(f"empty:{resource.id}")
        route_vars[resource.id, None, None] = empty
        circuit.append((0, 0, empty))
        selected = [assignments[t.id, resource.id] for t in eligible]
        model.Add(sum(selected) == 0).OnlyEnforceIf(empty)
        model.Add(sum(selected) >= 1).OnlyEnforceIf(empty.Not())
        intervals = []
        for i, task in enumerate(eligible, 1):
            checkpoint()
            assigned = assignments[task.id, resource.id]
            circuit.append((i, i, assigned.Not()))
            first = model.NewBoolVar(f"first:{resource.id}:{i}")
            last = model.NewBoolVar(f"last:{resource.id}:{i}")
            route_vars[resource.id, None, task.id] = first
            route_vars[resource.id, task.id, None] = last
            circuit.append((0, i, first))
            circuit.append((i, 0, last))
            intervals.append(model.NewOptionalIntervalVar(starts[task.id], task.duration_days, ends[task.id], assigned, f"fleet:{resource.id}:{i}"))
            for j, following in enumerate(eligible, 1):
                checkpoint()
                if i == j or (task.id, following.id) in forbidden: continue
                arc = model.NewBoolVar(f"arc:{resource.id}:{i}:{j}")
                route_vars[resource.id, task.id, following.id] = arc
                circuit.append((i, j, arc))
                days = resource.transfer_days if task.pavement_context.position_id != following.pavement_context.position_id else 0
                model.Add(starts[following.id] >= ends[task.id] + days).OnlyEnforceIf(arc)
                arcs.append((resource, task, following, days, arc))
        model.AddCircuit(circuit)
        model.AddNoOverlap(intervals)
    return assignments, arcs, route_vars
