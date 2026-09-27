import { h } from "./dom";

export interface StartChoice {
  mode: "gps" | "simulated";
}

export interface StartScreenOptions {
  gpsSupported: boolean;
}

/** The first screen: choose how your position is determined. */
export class StartScreen {
  readonly el: HTMLElement;
  private message: HTMLElement;
  private buttons: HTMLButtonElement[];

  constructor(opts: StartScreenOptions, onStart: (choice: StartChoice) => void) {
    this.message = h("p", { class: "start-message", role: "status" });
    this.buttons = [
      h(
        "button",
        {
          class: "btn btn-primary",
          onclick: () => onStart({ mode: "gps" }),
          disabled: !opts.gpsSupported,
          "data-unsupported": !opts.gpsSupported,
        },
        "📍 Use my location",
      ),
      h(
        "button",
        { class: "btn", onclick: () => onStart({ mode: "simulated" }) },
        "🎮 Simulate (no GPS needed)",
      ),
    ];

    this.el = h(
      "div",
      { class: "overlay" },
      h(
        "div",
        { class: "card start-card" },
        h("h1", {}, "High Lander"),
        h(
          "p",
          { class: "muted" },
          "A goal will appear somewhere near you. Follow the route and reach the flag!",
        ),
        h("div", { class: "start-actions" }, ...this.buttons),
        this.message,
      ),
    );
  }

  setBusy(busy: boolean, message = ""): void {
    this.buttons.forEach((b) => (b.disabled = busy || b.hasAttribute("data-unsupported")));
    this.message.textContent = message;
    this.message.classList.remove("error");
  }

  showError(message: string): void {
    this.setBusy(false);
    this.message.textContent = message;
    this.message.classList.add("error");
  }

  remove(): void {
    this.el.remove();
  }
}
