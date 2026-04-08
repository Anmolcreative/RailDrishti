from ortools.graph.python import min_cost_flow

def solve_route(train_id: str, start: int, end: int, congestion_map: dict):
    """
    Finds optimal route for a train using OR-Tools min cost flow.
    
    Args:
        train_id: e.g. "TN001"
        start: starting station node index
        end: destination station node index
        congestion_map: dict of {(from, to): delay_cost}
    
    Returns:
        dict with recommended path and total cost
    """

    # Define railway network edges (from, to, capacity, unit_cost)
    # Dummy network: 5 stations (0=Mumbai, 1=Pune, 2=Nashik, 3=Surat, 4=Delhi)
    edges = [
        (0, 1, 10, 2),   # Mumbai → Pune
        (0, 2, 10, 5),   # Mumbai → Nashik
        (1, 3, 10, 3),   # Pune → Surat
        (2, 3, 10, 1),   # Nashik → Surat
        (3, 4, 10, 4),   # Surat → Delhi
        (1, 4, 10, 8),   # Pune → Delhi (direct, expensive)
    ]

    # Apply congestion penalty from congestion_map
    adjusted_edges = []
    for (u, v, cap, cost) in edges:
        penalty = congestion_map.get((u, v), 0)
        adjusted_edges.append((u, v, cap, cost + penalty))

    # Build OR-Tools min cost flow solver
    smcf = min_cost_flow.SimpleMinCostFlow()

    for (u, v, cap, cost) in adjusted_edges:
        smcf.add_arc_with_capacity_and_unit_cost(u, v, cap, cost)

    # Set supply and demand
    num_nodes = 5
    for i in range(num_nodes):
        if i == start:
            smcf.set_node_supply(i, 1)   # source
        elif i == end:
            smcf.set_node_supply(i, -1)  # sink
        else:
            smcf.set_node_supply(i, 0)

    # Solve
    status = smcf.solve()

    if status == smcf.OPTIMAL:
        path = []
        total_cost = smcf.optimal_cost()

        for arc in range(smcf.num_arcs()):
            if smcf.flow(arc) > 0:
                path.append({
                    "from": smcf.tail(arc),
                    "to": smcf.head(arc),
                    "cost": smcf.unit_cost(arc)
                })

        return {
            "train_id": train_id,
            "status": "optimal",
            "total_cost": total_cost,
            "path": path
        }
    else:
        return {
            "train_id": train_id,
            "status": "no solution found",
            "total_cost": None,
            "path": []
        }


# Test it directly
if __name__ == "__main__":
    congestion = {(0, 1): 10}  # Mumbai→Pune is congested
    result = solve_route("TN001", start=0, end=4, congestion_map=congestion)
    print(result)