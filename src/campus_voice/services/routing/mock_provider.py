"""Walkway-graph-based routing provider for AAUA campus."""

from __future__ import annotations

from campus_voice.models.schemas import Coordinate, DestinationSummary, RouteStep
from campus_voice.services.routing.base import RoutingProvider
from campus_voice.services.routing.geo import distance_meters, bearing_degrees
from campus_voice.services.routing.campus_graph import GRAPH_NODES, LOCATION_ID_TO_NODE, EDGES
from campus_voice.services.routing.dijkstra import find_shortest_path
from campus_voice.services.routing.google_routes_provider import RouteBuildResult


class MockRoutingProvider(RoutingProvider):
    """Deterministic routing provider using a walkway graph and Dijkstra's algorithm."""

    def build_route(
        self,
        origin: Coordinate,
        destination: DestinationSummary,
        destination_coordinate: Coordinate,
    ) -> RouteBuildResult:
        # 1. Snap origin coordinate to the closest graph node
        start_node_id = min(
            GRAPH_NODES.keys(),
            key=lambda nid: distance_meters(
                origin,
                Coordinate(
                    latitude=GRAPH_NODES[nid]["latitude"],
                    longitude=GRAPH_NODES[nid]["longitude"],
                ),
            ),
        )

        # 2. Map destination to graph node ID (by ID lookup or coordinate proximity)
        if destination.id in LOCATION_ID_TO_NODE:
            end_node_id = LOCATION_ID_TO_NODE[destination.id]
        else:
            end_node_id = min(
                GRAPH_NODES.keys(),
                key=lambda nid: distance_meters(
                    destination_coordinate,
                    Coordinate(
                        latitude=GRAPH_NODES[nid]["latitude"],
                        longitude=GRAPH_NODES[nid]["longitude"],
                    ),
                ),
            )

        # 3. Find shortest path on the walkway graph
        path = find_shortest_path(start_node_id, end_node_id, GRAPH_NODES, EDGES)

        if not path:
            # Fallback to straight line if path cannot be resolved
            path = [start_node_id, end_node_id]

        # 4. Build unique, duplicate-filtered list of waypoints
        waypoints = [origin]
        for node_id in path:
            node = GRAPH_NODES[node_id]
            coord = Coordinate(latitude=node["latitude"], longitude=node["longitude"])
            if distance_meters(waypoints[-1], coord) > 2.0:
                waypoints.append(coord)

        if distance_meters(waypoints[-1], destination_coordinate) > 2.0:
            waypoints.append(destination_coordinate)
        else:
            if len(waypoints) > 1:
                waypoints[-1] = destination_coordinate
            else:
                waypoints.append(destination_coordinate)

        # 5. Generate steps and turn-by-turn instructions
        steps: list[RouteStep] = []
        n_waypoints = len(waypoints)

        if n_waypoints <= 1:
            steps.append(
                RouteStep(
                    step_number=1,
                    instruction=f"You have arrived at your destination, {destination.name}",
                    distance_meters=0.0,
                    heading_degrees=0.0,
                    waypoint=destination_coordinate,
                )
            )
        else:
            for i in range(n_waypoints - 1):
                start = waypoints[i]
                end = waypoints[i + 1]
                dist = round(distance_meters(start, end), 1)
                bearing = round(bearing_degrees(start, end), 1)

                # Find clean name for end waypoint
                target_name = destination.name
                matching_node = None
                for node in GRAPH_NODES.values():
                    if (
                        abs(node["latitude"] - end.latitude) < 0.00001
                        and abs(node["longitude"] - end.longitude) < 0.00001
                    ):
                        matching_node = node
                        break

                if matching_node and matching_node["id"] != end_node_id:
                    target_name = matching_node["name"]

                is_junction = "walkway junction" in target_name.lower() or target_name.lower().startswith("walkway junction")

                # Generate instruction text based on relative bearing changes
                if i == 0:
                    if is_junction:
                        instruction = f"Start walking for {dist} meters"
                    else:
                        instruction = f"Start walking towards {target_name} for {dist} meters"
                else:
                    prev_start = waypoints[i - 1]
                    prev_bearing = bearing_degrees(prev_start, start)
                    angle_change = (bearing - prev_bearing + 180) % 360 - 180

                    # Simplified turns (Turn left/right instead of bear left/right)
                    if angle_change < -135 or angle_change > 135:
                        turn = "Make a U-turn and head" if not is_junction else "Make a U-turn and walk"
                    elif -135 <= angle_change < -20:
                        turn = "Turn left"
                    elif -20 <= angle_change < 20:
                        turn = "Continue straight"
                    else:
                        turn = "Turn right"

                    if is_junction:
                        if turn == "Continue straight":
                            instruction = f"Continue straight for {dist} meters"
                        elif turn.startswith("Make a U-turn"):
                            instruction = f"{turn} for {dist} meters"
                        else:
                            instruction = f"{turn} and walk for {dist} meters"
                    else:
                        instruction = f"{turn} towards {target_name} for {dist} meters"

                # Append arrival note on final step
                if i == n_waypoints - 2:
                    instruction += f" and arrive at your destination, {destination.name}"

                steps.append(
                    RouteStep(
                        step_number=len(steps) + 1,
                        instruction=instruction,
                        distance_meters=dist,
                        heading_degrees=bearing,
                        waypoint=end,
                    )
                )

            # 6. Merge consecutive straight walks on non-landmark waypoints
            merged_steps: list[RouteStep] = []
            if steps:
                current_step = steps[0]
                for next_step in steps[1:]:
                    is_curr_straight = current_step.instruction.startswith("Continue straight") or current_step.instruction.startswith("Start walking")
                    is_next_straight = next_step.instruction.startswith("Continue straight")

                    # Check if current_step waypoint is a landmark
                    is_curr_landmark = False
                    for node in GRAPH_NODES.values():
                        if (
                            abs(node["latitude"] - current_step.waypoint.latitude) < 0.00001
                            and abs(node["longitude"] - current_step.waypoint.longitude) < 0.00001
                        ):
                            if "walkway junction" not in node["name"].lower() and not node["name"].lower().startswith("walkway junction"):
                                is_curr_landmark = True
                            break

                    if is_curr_straight and is_next_straight and not is_curr_landmark:
                        new_dist = round(current_step.distance_meters + next_step.distance_meters, 1)

                        # Determine if next_step target is a junction
                        is_next_junction = True
                        next_target_name = destination.name
                        for node in GRAPH_NODES.values():
                            if (
                                abs(node["latitude"] - next_step.waypoint.latitude) < 0.00001
                                and abs(node["longitude"] - next_step.waypoint.longitude) < 0.00001
                            ):
                                if "walkway junction" not in node["name"].lower() and not node["name"].lower().startswith("walkway junction"):
                                    is_next_junction = False
                                    next_target_name = node["name"]
                                break

                        is_final = "arrive at your destination" in next_step.instruction

                        if current_step.instruction.startswith("Start walking"):
                            prefix = "Start walking"
                        else:
                            prefix = "Continue straight"

                        if is_next_junction:
                            new_instruction = f"{prefix} for {new_dist} meters"
                        else:
                            new_instruction = f"{prefix} towards {next_target_name} for {new_dist} meters"

                        if is_final:
                            new_instruction += f" and arrive at your destination, {destination.name}"

                        current_step = RouteStep(
                            step_number=current_step.step_number,
                            instruction=new_instruction,
                            distance_meters=new_dist,
                            heading_degrees=next_step.heading_degrees,
                            waypoint=next_step.waypoint,
                        )
                    else:
                        merged_steps.append(current_step)
                        current_step = next_step
                merged_steps.append(current_step)

                # Re-number the steps sequentially
                for idx, s in enumerate(merged_steps, start=1):
                    s.step_number = idx
                steps = merged_steps

        duration_seconds = round(sum(s.distance_meters for s in steps) / 1.25)

        return RouteBuildResult(
            steps=steps,
            duration_seconds=duration_seconds,
            route_preview=waypoints,
        )
