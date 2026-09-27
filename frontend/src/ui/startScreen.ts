import { h } from "./dom";

export interface StartChoice {
  name: string;
  mode: "gps" | "simulated";
}

export interface StartScreenOptions {
  joining: boolean;
  gpsSupported: boolean;
  defaultName: string;
}

/** The first screen: pick a name and how your position is determined. */
export class StartScreen {
  readonly el: HTMLElement;
  private message: HTMLElement;
  private buttons: HTMLButtonElement[] = [];
  private nameInput: HTMLInputElement;

  constructor(opts: StartScreenOptions, onStart: (choice: StartChoice) => void) {
    this.nameInput = h("input", {
      type: "text",
      maxlength: "32",
      placeholder: "Your name",
      value: opts.defaultName,
      "aria-label": "Your name",
    });
    this.message = h("p", { class: "start-message", role: "status" });

    const start = (mode: StartChoice["mode"]) => () =>
      onStart({ name: this.nameInput.value.trim(), mode });

    const gpsBtn = h(
      "button",
      {
        class: "btn btn-primary",
        onclick: start("gps"),
        disabled: !opts.gpsSupported,
        "data-unsupported": !opts.gpsSupported,
      },
      "📍 Use my location",
    );
    this.buttons.push(gpsBtn);

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
          opts.joining
            ? "You've been invited to a race. First one to the flag wins!"
            : "A goal will appear somewhere near you. Follow the route and reach the flag!",
        ),
        this.nameInput,
        h("div", { class: "start-actions" }, gpsBtn),
        this.message,
      ),
    );
  }

  addAction(label: string, onClick: () => void, className = "btn"): void {
    const btn = h("button", { class: className, onclick: onClick }, label);
    this.buttons.push(btn);
    this.el.querySelector(".start-actions")!.append(btn);
  }

  get name(): string {
    return this.nameInput.value.trim();
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
