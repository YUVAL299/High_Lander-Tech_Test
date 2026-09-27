import L from "leaflet";
import "leaflet/dist/leaflet.css";

const TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

/** Owns the Leaflet map and everything drawn on it. */
export class MapView {
  readonly map: L.Map;

  constructor(container: HTMLElement, center: L.LatLngExpression, zoom = 16) {
    this.map = L.map(container, { zoomControl: true }).setView(center, zoom);
    L.tileLayer(TILE_URL, { maxZoom: 19, attribution: ATTRIBUTION }).addTo(this.map);
  }
}
