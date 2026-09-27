/** Arrow keys / WASD -> compass bearing. Diagonals work by holding two keys. */
const DIRECTIONS: Record<string, [number, number]> = {
  ArrowUp: [0, 1],
  KeyW: [0, 1],
  ArrowDown: [0, -1],
  KeyS: [0, -1],
  ArrowLeft: [-1, 0],
  KeyA: [-1, 0],
  ArrowRight: [1, 0],
  KeyD: [1, 0],
};

export function bearingFromKeys(pressed: Set<string>): number | null {
  let x = 0;
  let y = 0;
  for (const code of pressed) {
    const d = DIRECTIONS[code];
    if (d) {
      x += d[0];
      y += d[1];
    }
  }
  if (x === 0 && y === 0) return null;
  return ((Math.atan2(x, y) * 180) / Math.PI + 360) % 360;
}

/**
 * Calls `onStep(bearing, multiplier)` for every movement key press (including
 * auto-repeat while held). Shift makes steps 5x larger.
 */
export class KeyboardControls {
  private pressed = new Set<string>();
  private readonly down = (e: KeyboardEvent) => this.onDown(e);
  private readonly up = (e: KeyboardEvent) => this.pressed.delete(e.code);
  private readonly blur = () => this.pressed.clear();

  constructor(private readonly onStep: (bearing: number, multiplier: number) => void) {
    window.addEventListener("keydown", this.down);
    window.addEventListener("keyup", this.up);
    window.addEventListener("blur", this.blur);
  }

  dispose(): void {
    window.removeEventListener("keydown", this.down);
    window.removeEventListener("keyup", this.up);
    window.removeEventListener("blur", this.blur);
  }

  private onDown(e: KeyboardEvent): void {
    if (!(e.code in DIRECTIONS)) return;
    const target = e.target as HTMLElement | null;
    if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
    e.preventDefault(); // don't let arrow keys also pan the map
    this.pressed.add(e.code);
    const bearing = bearingFromKeys(this.pressed);
    if (bearing !== null) this.onStep(bearing, e.shiftKey ? 5 : 1);
  }
}
