// Mirrors backend/app/schemas.py. Keep the two in sync.

export interface LatLngPos {
  lat: number;
  lng: number;
}

export type RouteSource = "osrm" | "straight_line";
export type SessionStatus = "active" | "finished";

export interface RouteView {
  points: [number, number][];
  distance_m: number;
  duration_s: number;
  source: RouteSource;
}

export interface PlayerView {
  id: string;
  name: string;
  position: LatLngPos;
  distance_to_goal_m: number;
  remaining_route_m: number;
  reroute_count: number;
  reached_goal_at: string | null;
  route: RouteView | null;
}

export interface SessionView {
  id: string;
  status: SessionStatus;
  goal: LatLngPos;
  reach_radius_m: number;
  winner_id: string | null;
  created_at: string;
  finished_at: string | null;
  players: PlayerView[];
}

export interface SessionCreated {
  player_id: string;
  session: SessionView;
}

export interface PublicConfig {
  goal_reach_radius_m: number;
  goal_min_distance_m: number;
  goal_max_distance_m: number;
  reroute_off_route_m: number;
}

export interface ServerMessages {
  "session.state": SessionView;
  "player.moved": {
    player_id: string;
    position: LatLngPos;
    distance_to_goal_m: number;
    remaining_route_m: number;
  };
  "route.updated": {
    player_id: string;
    reason: "no_route" | "off_route" | "retry_routing";
    reroute_count: number;
    route: RouteView;
  };
  "goal.reached": { player_id: string; name: string; elapsed_s: number; session: SessionView };
  pong: undefined;
  error: { message: string };
}

export type ServerMessageType = keyof ServerMessages;

export type ClientMessage =
  | { type: "position.update"; payload: LatLngPos }
  | { type: "ping" };
