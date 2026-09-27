import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { LatLngPos, RouteView } from "../types/protocol";

const TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

/**
 * Player markers are keyed by player id, matching the server protocol, so
 * showing other players later (multiplayer) is just more entries in this map.
 */
interface PlayerLayer {
  marker: L.Marker;
}

/** Owns the Leaflet map and everything drawn on it. Knows nothing about the network. */
export class MapView {
  readonly map: L.Map;
  private players = new Map<string, PlayerLayer>();
  private goalMarker: L.Marker | null = null;
  private goalCircle: L.Circle | null = null;
  private routeLine: L.Polyline | null = null;
  private routeIsStraight = false;
  private accuracyCircle: L.Circle | null = null;
  private selfId: string | null = null;
  follow = true;

  constructor(container: HTMLElement, center: L.LatLngExpression, zoom = 16) {
    this.map = L.map(container, { zoomControl: false }).setView(center, zoom);
    L.control.zoom({ position: "bottomright" }).addTo(this.map);
    L.tileLayer(TILE_URL, { maxZoom: 19, attribution: ATTRIBUTION }).addTo(this.map);
    // Manually dragging the map means "let me look around": stop following.
    this.map.on("dragstart", () => (this.follow = false));
  }

  onClick(handler: (pos: LatLngPos) => void): void {
    this.map.on("click", (e: L.LeafletMouseEvent) => handler({ lat: e.latlng.lat, lng: e.latlng.lng }));
  }

  setSelf(playerId: string): void {
    this.selfId = playerId;
  }

  setGoal(goal: LatLngPos, reachRadiusM: number): void {
    this.goalMarker?.remove();
    this.goalCircle?.remove();
    this.goalCircle = L.circle(goal, {
      radius: reachRadiusM,
      color: "#2b8a3e",
      weight: 1,
      fillOpacity: 0.15,
      interactive: false,
    }).addTo(this.map);
    this.goalMarker = L.marker(goal, {
      icon: L.divIcon({ className: "goal-icon", html: "🏁", iconSize: [32, 32], iconAnchor: [6, 30] }),
      title: "Goal",
      keyboard: false,
    }).addTo(this.map);
  }

  upsertPlayer(id: string, name: string, pos: LatLngPos): void {
    const isSelf = id === this.selfId;
    let layer = this.players.get(id);
    if (!layer) {
      const marker = L.marker(pos, {
        icon: L.divIcon({
          className: `ball ${isSelf ? "ball--self" : "ball--other"}`,
          html: "<span></span>",
          iconSize: [22, 22],
          iconAnchor: [11, 11],
        }),
        zIndexOffset: isSelf ? 1000 : 500,
        keyboard: false,
      })
        .bindTooltip(isSelf ? "You" : name, { direction: "top", offset: [0, -12] })
        .addTo(this.map);
      layer = { marker };
      this.players.set(id, layer);
    } else {
      layer.marker.setLatLng(pos);
    }

    if (isSelf) {
      if (this.routeIsStraight && this.routeLine && this.goalMarker) {
        this.routeLine.setLatLngs([pos, this.goalMarker.getLatLng()]);
      }
      if (this.follow) this.keepInView(pos);
    }
  }

  removePlayer(id: string): void {
    this.players.get(id)?.marker.remove();
    this.players.delete(id);
  }

  setAccuracy(pos: LatLngPos, accuracyM: number | undefined): void {
    if (accuracyM === undefined) {
      this.accuracyCircle?.remove();
      this.accuracyCircle = null;
      return;
    }
    if (!this.accuracyCircle) {
      this.accuracyCircle = L.circle(pos, {
        radius: accuracyM,
        color: "#1c7ed6",
        weight: 1,
        fillOpacity: 0.08,
        interactive: false,
      }).addTo(this.map);
    } else {
      this.accuracyCircle.setLatLng(pos).setRadius(accuracyM);
    }
  }

  /** Draw the local player's route. A straight-line fallback is drawn dashed. */
  setRoute(route: RouteView): void {
    this.routeIsStraight = route.source === "straight_line";
    const style: L.PolylineOptions = this.routeIsStraight
      ? { color: "#868e96", weight: 4, dashArray: "8 10", opacity: 0.9 }
      : { color: "#1c7ed6", weight: 6, opacity: 0.8, lineJoin: "round" };
    this.routeLine?.remove();
    this.routeLine = L.polyline(route.points, { ...style, interactive: false }).addTo(this.map);
  }

  flashRoute(): void {
    const el = this.routeLine?.getElement();
    if (!el) return;
    el.classList.remove("route-flash");
    void (el as HTMLElement).getBoundingClientRect(); // restart the animation
    el.classList.add("route-flash");
  }

  fitToGame(): void {
    const self = this.selfId ? this.players.get(this.selfId) : undefined;
    const pts: L.LatLng[] = [];
    if (self) pts.push(self.marker.getLatLng());
    if (this.goalMarker) pts.push(this.goalMarker.getLatLng());
    if (this.routeLine) pts.push(...(this.routeLine.getLatLngs() as L.LatLng[]));
    if (pts.length) this.map.fitBounds(L.latLngBounds(pts), { padding: [60, 60], maxZoom: 18 });
  }

  recenter(): void {
    this.follow = true;
    const self = this.selfId ? this.players.get(this.selfId) : undefined;
    if (self) this.map.panTo(self.marker.getLatLng());
  }

  clear(): void {
    this.players.forEach((p) => p.marker.remove());
    this.players.clear();
    this.goalMarker?.remove();
    this.goalCircle?.remove();
    this.routeLine?.remove();
    this.accuracyCircle?.remove();
    this.goalMarker = null;
    this.goalCircle = null;
    this.routeLine = null;
    this.accuracyCircle = null;
  }

  private keepInView(pos: LatLngPos): void {
    // Only pan when the player gets close to the edge, to avoid a jittery map.
    const inner = this.map.getBounds().pad(-0.25);
    if (!inner.contains(pos)) this.map.panTo(pos, { animate: true });
  }
}
