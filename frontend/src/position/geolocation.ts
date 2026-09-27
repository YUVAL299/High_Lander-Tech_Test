import type { PositionFix, PositionSource } from "./types";

const GEO_ERRORS: Record<number, string> = {
  1: "Location permission denied",
  2: "Location unavailable",
  3: "Location request timed out",
};

/** The host machine's real location, via the browser Geolocation API. */
export class GeolocationSource implements PositionSource {
  readonly kind = "gps" as const;
  private watchId: number | null = null;
  private lastError: string | null = null;

  static isSupported(): boolean {
    return "geolocation" in navigator;
  }

  /** One-off fix, used to place the goal when a game starts. */
  static current(timeoutMs = 10_000): Promise<PositionFix> {
    return new Promise((resolve, reject) => {
      if (!GeolocationSource.isSupported()) {
        reject(new Error("Geolocation is not supported by this browser"));
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (p) => resolve(toFix(p)),
        (e) => reject(new Error(GEO_ERRORS[e.code] ?? e.message)),
        { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 5_000 },
      );
    });
  }

  start(onFix: (fix: PositionFix) => void, onError: (message: string) => void): void {
    this.stop();
    // No timeout: a device standing still may legitimately report nothing for a while.
    this.watchId = navigator.geolocation.watchPosition(
      (p) => {
        this.lastError = null;
        onFix(toFix(p));
      },
      (e) => {
        // Report each problem once, not on every retry.
        const message = GEO_ERRORS[e.code] ?? e.message;
        if (message !== this.lastError) onError(message);
        this.lastError = message;
      },
      { enableHighAccuracy: true, maximumAge: 1_000 },
    );
  }

  stop(): void {
    if (this.watchId !== null) {
      navigator.geolocation.clearWatch(this.watchId);
      this.watchId = null;
    }
  }
}

function toFix(p: GeolocationPosition): PositionFix {
  return { lat: p.coords.latitude, lng: p.coords.longitude, accuracyM: p.coords.accuracy };
}
