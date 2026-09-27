import "./style.css";
import { GameApp } from "./app";
import { MapView } from "./map/mapView";

const DEFAULT_CENTER: [number, number] = [32.0853, 34.7818]; // Tel Aviv, until we know better

const map = new MapView(document.getElementById("map")!, DEFAULT_CENTER);
void new GameApp(map, document.body).boot();
