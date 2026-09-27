import { formatDuration } from "../geo";
import { h } from "./dom";

/** Full-screen "goal reached" celebration. */
export function showResult(opts: { elapsedS: number; onNewGame: () => void }): void {
  document.querySelector(".result")?.remove();
  const confetti = Array.from({ length: 40 }, (_, i) =>
    h("i", {
      style: `left:${(i * 37) % 100}%;animation-delay:${(i % 10) * 0.12}s;background:hsl(${(i * 47) % 360} 80% 55%)`,
    }),
  );
  const el = h(
    "div",
    { class: "overlay result" },
    h("div", { class: "confetti" }, ...confetti),
    h(
      "div",
      { class: "card" },
      h("div", { class: "result-emoji" }, "🎉"),
      h("h2", {}, "Goal reached!"),
      h("p", { class: "muted" }, `Time: ${formatDuration(opts.elapsedS)}`),
      h(
        "div",
        { class: "start-actions" },
        h("button", { class: "btn btn-primary", onclick: opts.onNewGame }, "Play again"),
        h("button", { class: "btn", onclick: () => el.remove() }, "Look around"),
      ),
    ),
  );
  document.body.append(el);
}
