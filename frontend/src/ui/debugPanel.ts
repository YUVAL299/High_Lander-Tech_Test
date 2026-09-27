import type { PositionSourceKind } from "../position/types";
import { h } from "./dom";

export interface DebugActions {
  onModeChange: (mode: PositionSourceKind) => void;
  onStepChange: (metres: number) => void;
  onSpeedChange: (mps: number) => void;
  onToggleWalk: () => void;
  onWanderOff: () => void;
  onJumpNearGoal: () => void;
}

const COLLAPSED_KEY = "highlander.debug.collapsed";

/** Test & debug controls, so the game can be evaluated from a desk. */
export class DebugPanel {
  readonly el: HTMLElement;
  private modeButtons: Record<PositionSourceKind, HTMLButtonElement>;
  private simControls: HTMLElement;
  private walkBtn: HTMLButtonElement;
  private stepLabel: HTMLElement;
  private speedLabel: HTMLElement;

  constructor(actions: DebugActions, initial: { stepM: number; speedMps: number; gpsSupported: boolean }) {
    this.modeButtons = {
      gps: h(
        "button",
        {
          class: "btn btn-small",
          onclick: () => actions.onModeChange("gps"),
          disabled: !initial.gpsSupported,
        },
        "📍 GPS",
      ),
      simulated: h(
        "button",
        { class: "btn btn-small", onclick: () => actions.onModeChange("simulated") },
        "🎮 Simulated",
      ),
    };

    this.stepLabel = h("span", { class: "value" });
    this.speedLabel = h("span", { class: "value" });
    const stepInput = h("input", {
      type: "range",
      min: "1",
      max: "50",
      value: String(initial.stepM),
      "aria-label": "Step size",
    });
    stepInput.addEventListener("input", () => {
      this.stepLabel.textContent = `${stepInput.value} m`;
      actions.onStepChange(Number(stepInput.value));
    });
    const speedInput = h("input", {
      type: "range",
      min: "1",
      max: "30",
      value: String(initial.speedMps),
      "aria-label": "Auto-walk speed",
    });
    speedInput.addEventListener("input", () => {
      this.speedLabel.textContent = `${speedInput.value} m/s`;
      actions.onSpeedChange(Number(speedInput.value));
    });
    this.stepLabel.textContent = `${initial.stepM} m`;
    this.speedLabel.textContent = `${initial.speedMps} m/s`;

    this.walkBtn = h("button", { class: "btn btn-small", onclick: actions.onToggleWalk }, "▶ Auto-walk route");

    this.simControls = h(
      "div",
      { class: "sim-controls" },
      h("label", { class: "row" }, h("span", { class: "label" }, "Step"), this.stepLabel),
      stepInput,
      h("label", { class: "row" }, h("span", { class: "label" }, "Auto-walk speed"), this.speedLabel),
      speedInput,
      h(
        "div",
        { class: "debug-actions" },
        this.walkBtn,
        h(
          "button",
          { class: "btn btn-small", onclick: actions.onWanderOff, title: "Jump 60 m off the route to trigger a reroute" },
          "🔀 Wander off route",
        ),
        h(
          "button",
          { class: "btn btn-small", onclick: actions.onJumpNearGoal, title: "Stand just outside the goal radius" },
          "🏁 Jump near goal",
        ),
      ),
      h(
        "p",
        { class: "hint" },
        h("kbd", {}, "←↑↓→"),
        " / ",
        h("kbd", {}, "WASD"),
        " move · ",
        h("kbd", {}, "Shift"),
        " ×5 · click map to teleport",
      ),
    );

    const body = h(
      "div",
      { class: "debug-body" },
      h("div", { class: "segmented" }, this.modeButtons.gps, this.modeButtons.simulated),
      this.simControls,
    );
    const details = h("details", {}, h("summary", {}, "🛠 Debug & simulation"), body);
    const collapsed = safeGet(COLLAPSED_KEY) === "1";
    details.open = !collapsed;
    details.addEventListener("toggle", () => safeSet(COLLAPSED_KEY, details.open ? "0" : "1"));
    this.el = h("aside", { class: "card debug" }, details);
  }

  setMode(mode: PositionSourceKind): void {
    this.modeButtons.gps.classList.toggle("active", mode === "gps");
    this.modeButtons.simulated.classList.toggle("active", mode === "simulated");
    this.simControls.classList.toggle("disabled", mode !== "simulated");
  }

  setWalking(walking: boolean): void {
    this.walkBtn.textContent = walking ? "⏸ Stop walking" : "▶ Auto-walk route";
    this.walkBtn.classList.toggle("active", walking);
  }
}

function safeGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* storage unavailable */
  }
}
