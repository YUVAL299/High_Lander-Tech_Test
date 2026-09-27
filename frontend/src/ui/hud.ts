import { formatDistance, formatDuration } from "../geo";
import type { SocketStatus } from "../net/gameSocket";
import type { PlayerView, RouteView } from "../types/protocol";
import { h } from "./dom";

export interface HudActions {
  onRecenter: () => void;
  onNewGame: () => void;
  onInvite: () => void;
}

/** The game panel: distances, route info, connection state and players. */
export class Hud {
  readonly el: HTMLElement;
  private fields: Record<
    "distance" | "remaining" | "eta" | "reroutes" | "source" | "connection" | "position",
    HTMLElement
  >;
  private playerList: HTMLElement;
  private toastEl: HTMLElement;
  private toastTimer: number | undefined;

  constructor(actions: HudActions) {
    const field = () => h("span", { class: "value" }, "–");
    this.fields = {
      distance: field(),
      remaining: field(),
      eta: field(),
      reroutes: field(),
      source: field(),
      connection: h("span", { class: "conn conn--connecting" }, "connecting"),
      position: field(),
    };
    const row = (label: string, value: HTMLElement) =>
      h("div", { class: "row" }, h("span", { class: "label" }, label), value);

    this.playerList = h("ul", { class: "players" });
    this.toastEl = h("div", { class: "toast", role: "status", "aria-live": "polite" });

    this.el = h(
      "aside",
      { class: "card hud" },
      h("div", { class: "hud-title" }, h("strong", {}, "High Lander"), this.fields.connection),
      row("To goal (direct)", this.fields.distance),
      row("Route remaining", this.fields.remaining),
      row("Walking ETA", this.fields.eta),
      row("Reroutes", this.fields.reroutes),
      row("Routing", this.fields.source),
      row("Position source", this.fields.position),
      this.playerList,
      h(
        "div",
        { class: "hud-actions" },
        h("button", { class: "btn btn-small", onclick: actions.onRecenter, title: "Follow me" }, "🎯 Recenter"),
        h("button", { class: "btn btn-small", onclick: actions.onInvite, title: "Copy invite link" }, "👥 Invite"),
        h("button", { class: "btn btn-small", onclick: actions.onNewGame }, "🔄 New game"),
      ),
    );
    document.body.append(this.toastEl);
  }

  setDistances(directM: number, remainingM: number): void {
    this.fields.distance.textContent = formatDistance(directM);
    this.fields.remaining.textContent = formatDistance(remainingM);
    this.fields.eta.textContent = formatDuration(remainingM / 1.4);
  }

  setRoute(route: RouteView, rerouteCount: number): void {
    this.fields.reroutes.textContent = String(rerouteCount);
    this.fields.source.textContent =
      route.source === "osrm" ? "OSRM (walking)" : "⚠️ Straight line (router offline)";
    this.fields.source.classList.toggle("warn", route.source !== "osrm");
  }

  setPositionSource(label: string): void {
    this.fields.position.textContent = label;
  }

  setConnection(status: SocketStatus): void {
    this.fields.connection.textContent = status;
    this.fields.connection.className = `conn conn--${status}`;
  }

  setPlayers(players: PlayerView[], selfId: string, winnerId: string | null): void {
    this.playerList.replaceChildren(
      ...(players.length > 1
        ? players.map((p) =>
            h(
              "li",
              { class: p.connected ? "" : "offline" },
              p.id === winnerId ? "🏆 " : p.connected ? "🟢 " : "⚪ ",
              p.id === selfId ? `${p.name} (you)` : p.name,
              h("span", { class: "muted" }, ` · ${formatDistance(p.distance_to_goal_m)}`),
            ),
          )
        : []),
    );
  }

  toast(message: string, ms = 2500): void {
    this.toastEl.textContent = message;
    this.toastEl.classList.add("show");
    window.clearTimeout(this.toastTimer);
    this.toastTimer = window.setTimeout(() => this.toastEl.classList.remove("show"), ms);
  }
}
