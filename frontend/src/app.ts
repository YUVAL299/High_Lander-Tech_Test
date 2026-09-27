import { bearingDeg, destinationPoint, haversineM, remainingPath } from "./geo";
import { MapView } from "./map/mapView";
import { ApiError, api } from "./net/api";
import { GameSocket } from "./net/gameSocket";
import { createPositionSource, SOURCE_LABELS } from "./position/factory";
import { GeolocationSource } from "./position/geolocation";
import { KeyboardControls } from "./position/keyboard";
import { SimulatedSource } from "./position/simulated";
import { PositionThrottle } from "./position/throttle";
import type { PositionFix, PositionSource, PositionSourceKind } from "./position/types";
import type { JoinedSession, LatLngPos, PlayerView, SessionView } from "./types/protocol";
import { DebugPanel } from "./ui/debugPanel";
import { Hud } from "./ui/hud";
import { showResult } from "./ui/resultBanner";
import { type StartChoice, StartScreen } from "./ui/startScreen";

const STORAGE_KEY = "highlander.session";
const DEFAULT_START: LatLngPos = { lat: 32.0853, lng: 34.7818 }; // Tel Aviv
const WANDER_OFF_M = 60;
const NAME_KEY = "highlander.name";

interface SavedSession {
  sessionId: string;
  playerId: string;
  mode: PositionSourceKind;
}

/** Wires the pieces together: start screen -> session -> live game loop. */
export class GameApp {
  private startScreen: StartScreen | null = null;
  private hud: Hud | null = null;
  private debug: DebugPanel | null = null;
  private keyboard: KeyboardControls | null = null;
  private simSettings = { stepM: 10, speedMps: 8 };
  /** Last position we knew, reused as the start of the next simulated game. */
  private lastKnown: LatLngPos | null = null;
  private socket: GameSocket | null = null;
  private source: PositionSource | null = null;
  private throttle = new PositionThrottle();
  private session: SessionView | null = null;
  private selfId = "";
  private selfPos: LatLngPos | null = null;
  private resultShown = false;

  constructor(
    private readonly map: MapView,
    private readonly root: HTMLElement,
  ) {
    map.onClick((pos) => {
      if (!this.session) return;
      this.simulated(true)?.teleport(pos);
    });
  }

  async boot(): Promise<void> {
    if (await this.tryResume()) return;
    this.showStartScreen();
  }

  // ---- lifecycle -------------------------------------------------------------

  protected showStartScreen(): void {
    const joinId = new URLSearchParams(location.search).get("join");
    this.startScreen = new StartScreen(
      {
        joining: Boolean(joinId),
        gpsSupported: GeolocationSource.isSupported(),
        defaultName: safeStorage(() => localStorage.getItem(NAME_KEY)) ?? "",
      },
      (choice) => void this.start(choice, joinId),
    );
    const screen = this.startScreen;
    screen.addAction("🎮 Simulate (no GPS needed)", () => {
      void this.start({ name: screen.name, mode: "simulated" }, joinId);
    });
    this.root.append(screen.el);
  }

  protected async start(choice: StartChoice, joinId: string | null, origin?: LatLngPos): Promise<void> {
    const screen = this.startScreen!;
    safeStorage(() => localStorage.setItem(NAME_KEY, choice.name));
    try {
      let start = origin;
      if (!start && choice.mode === "gps") {
        screen.setBusy(true, "Getting your location…");
        try {
          start = await GeolocationSource.current();
        } catch (err) {
          throw new Error(`${describeError(err)}. You can still play with 🎮 Simulate.`);
        }
      }
      if (!start) {
        screen.setBusy(true, "Finding a starting point…");
        start = await this.simulatedStart();
      }
      screen.setBusy(true, joinId ? "Joining the race…" : "Placing your goal and finding a route…");
      const joined = joinId
        ? await api.joinSession(joinId, start, choice.name)
        : await api.createSession(start, choice.name);
      this.enterGame(joined, choice.mode, start);
    } catch (err) {
      screen.showError(describeError(err));
    }
  }

  /** Where a simulated game starts: ?at=lat,lng > last position > real location > default. */
  private async simulatedStart(): Promise<LatLngPos> {
    const at = new URLSearchParams(location.search).get("at")?.split(",").map(Number);
    if (at && at.length === 2 && at.every(Number.isFinite)) return { lat: at[0], lng: at[1] };
    if (this.lastKnown) return this.lastKnown;
    try {
      return await GeolocationSource.current(3_000);
    } catch {
      return DEFAULT_START;
    }
  }

  private async tryResume(): Promise<boolean> {
    const sessionId = new URLSearchParams(location.search).get("session");
    const saved = safeStorage(() => JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? "null")) as
      | SavedSession
      | null;
    if (!sessionId || saved?.sessionId !== sessionId) return false;
    try {
      const session = await api.getSession(sessionId);
      const me = session.players.find((p) => p.id === saved.playerId);
      if (!me) return false;
      this.enterGame({ player_id: me.id, session }, saved.mode, me.position);
      return true;
    } catch {
      return false;
    }
  }

  protected enterGame(joined: JoinedSession, mode: PositionSourceKind, origin: LatLngPos): void {
    this.startScreen?.remove();
    this.startScreen = null;
    this.session = joined.session;
    this.selfId = joined.player_id;
    this.selfPos = origin;
    this.resultShown = false;
    this.throttle.reset();

    const saved: SavedSession = { sessionId: joined.session.id, playerId: joined.player_id, mode };
    safeStorage(() => sessionStorage.setItem(STORAGE_KEY, JSON.stringify(saved)));
    history.replaceState(null, "", `?session=${encodeURIComponent(joined.session.id)}`);

    this.hud = new Hud({
      onRecenter: () => this.map.recenter(),
      onNewGame: () => this.newGame(),
      onInvite: () => void this.invite(),
    });
    this.root.append(this.hud.el);
    this.hud.setPositionSource(SOURCE_LABELS[mode]);

    this.debug = new DebugPanel(
      {
        onModeChange: (m) => this.switchMode(m),
        onStepChange: (v) => {
          this.simSettings.stepM = v;
          const sim = this.simulated();
          if (sim) sim.stepM = v;
        },
        onSpeedChange: (v) => {
          this.simSettings.speedMps = v;
          const sim = this.simulated();
          if (sim) sim.speedMps = v;
        },
        onToggleWalk: () => this.toggleAutoWalk(),
        onWanderOff: () => this.wanderOff(),
        onJumpNearGoal: () => this.jumpNearGoal(),
      },
      { ...this.simSettings, gpsSupported: GeolocationSource.isSupported() },
    );
    this.root.append(this.debug.el);
    this.keyboard = new KeyboardControls((bearing, mult) => {
      this.simulated(true)?.step(bearing, mult);
    });

    this.map.setSelf(this.selfId);
    this.applyState(joined.session);
    this.map.fitToGame();

    this.connect(joined.session.id);
    this.useSource(createPositionSource(mode, origin));
  }

  protected newGame(): void {
    this.socket?.close();
    this.source?.stop();
    this.keyboard?.dispose();
    this.keyboard = null;
    this.debug?.el.remove();
    this.debug = null;
    this.socket = null;
    this.source = null;
    this.hud?.el.remove();
    this.hud = null;
    this.session = null;
    this.map.clear();
    document.querySelector(".result")?.remove();
    safeStorage(() => sessionStorage.removeItem(STORAGE_KEY));
    history.replaceState(null, "", location.pathname);
    this.showStartScreen();
  }

  // ---- position handling -----------------------------------------------------

  protected useSource(source: PositionSource): void {
    this.source?.stop();
    this.source = source;
    if (source instanceof SimulatedSource) {
      source.stepM = this.simSettings.stepM;
      source.speedMps = this.simSettings.speedMps;
      this.map.setAccuracy(this.selfPos ?? DEFAULT_START, undefined);
    }
    this.hud?.setPositionSource(SOURCE_LABELS[source.kind]);
    this.debug?.setMode(source.kind);
    this.debug?.setWalking(false);
    this.persistMode(source.kind);
    source.start(
      (fix) => this.onFix(fix),
      (message) => this.hud?.toast(`⚠️ ${message}`, 4000),
    );
  }

  protected onFix(fix: PositionFix): void {
    this.selfPos = { lat: fix.lat, lng: fix.lng };
    this.lastKnown = this.selfPos;
    // Draw locally right away so movement feels instant; the server confirms.
    this.map.upsertPlayer(this.selfId, this.selfName(), this.selfPos);
    this.map.setAccuracy(this.selfPos, fix.accuracyM);
    if (this.session) {
      this.hud?.setDistances(haversineM(this.selfPos, this.session.goal), this.remainingFallback());
    }
    if (this.throttle.shouldSend(this.selfPos, performance.now())) {
      if (!this.socket?.sendPosition(this.selfPos)) this.throttle.reset();
    }
  }

  protected get currentPosition(): LatLngPos | null {
    return this.selfPos;
  }

  protected get currentSession(): SessionView | null {
    return this.session;
  }

  protected get selfPlayer(): PlayerView | undefined {
    return this.session?.players.find((p) => p.id === this.selfId);
  }

  // ---- debug & simulation ------------------------------------------------------

  /** The simulated source, optionally switching to it (e.g. on a key press). */
  private simulated(switchIfNeeded = false): SimulatedSource | null {
    if (this.source instanceof SimulatedSource) return this.source;
    if (!switchIfNeeded || !this.session) return null;
    this.switchMode("simulated");
    this.hud?.toast("🎮 Switched to simulated position");
    return this.source instanceof SimulatedSource ? this.source : null;
  }

  private switchMode(mode: PositionSourceKind): void {
    if (this.source?.kind === mode) return;
    const origin = this.selfPos ?? this.lastKnown ?? DEFAULT_START;
    this.useSource(createPositionSource(mode, origin));
  }

  private toggleAutoWalk(): void {
    const sim = this.simulated(true);
    if (!sim) return;
    if (sim.walking) {
      sim.stopWalking();
      this.debug?.setWalking(false);
      return;
    }
    this.walkRoute(sim);
  }

  private walkRoute(sim: SimulatedSource): void {
    const route = this.selfPlayer?.route;
    if (!route || !this.session) return;
    const points = route.points.map(([lat, lng]) => ({ lat, lng }));
    const path = [...remainingPath(points, sim.position), this.session.goal];
    sim.walkAlong(path, () => this.debug?.setWalking(false));
    this.debug?.setWalking(true);
  }

  private wanderOff(): void {
    const sim = this.simulated(true);
    const route = this.selfPlayer?.route;
    if (!sim || !this.session) return;
    sim.stopWalking();
    this.debug?.setWalking(false);
    // Step sideways relative to where the route is heading, so we really leave it.
    const points = route?.points.map(([lat, lng]) => ({ lat, lng })) ?? [];
    const ahead = remainingPath(points, sim.position)[0] ?? this.session.goal;
    const side = Math.random() < 0.5 ? 90 : -90;
    sim.teleport(destinationPoint(sim.position, bearingDeg(sim.position, ahead) + side, WANDER_OFF_M));
    this.hud?.toast(`🔀 Moved ${WANDER_OFF_M} m off the route – watch it reroute`);
  }

  private jumpNearGoal(): void {
    const sim = this.simulated(true);
    if (!sim || !this.session) return;
    sim.stopWalking();
    this.debug?.setWalking(false);
    const { goal, reach_radius_m } = this.session;
    const from = haversineM(sim.position, goal) > 1 ? bearingDeg(goal, sim.position) : 180;
    const gap = 10;
    sim.teleport(destinationPoint(goal, from, reach_radius_m + gap));
    this.hud?.toast(`🏁 ${gap} m outside the goal radius – take a step closer`);
  }

  private persistMode(mode: PositionSourceKind): void {
    if (!this.session) return;
    const saved: SavedSession = { sessionId: this.session.id, playerId: this.selfId, mode };
    safeStorage(() => sessionStorage.setItem(STORAGE_KEY, JSON.stringify(saved)));
  }

  // ---- server events -----------------------------------------------------------

  private connect(sessionId: string): void {
    const socket = new GameSocket(sessionId, this.selfId);
    this.socket = socket;
    socket.onStatus((status, reason) => {
      this.hud?.setConnection(status);
      if (status === "open" && this.selfPos) {
        this.throttle.reset();
        socket.sendPosition(this.selfPos);
      }
      if (status === "closed" && reason) this.hud?.toast(`Disconnected: ${reason}`, 6000);
    });

    socket.on("session.state", (s) => this.applyState(s));

    socket.on("player.moved", (m) => {
      const p = this.findPlayer(m.player_id);
      if (p) {
        p.position = m.position;
        p.distance_to_goal_m = m.distance_to_goal_m;
        p.remaining_route_m = m.remaining_route_m;
      }
      if (m.player_id === this.selfId) {
        this.hud?.setDistances(m.distance_to_goal_m, m.remaining_route_m);
      } else {
        this.map.upsertPlayer(m.player_id, p?.name ?? "Player", m.position);
      }
      this.refreshPlayers();
    });

    socket.on("route.updated", (m) => {
      const p = this.findPlayer(m.player_id);
      if (p) {
        p.route = m.route;
        p.reroute_count = m.reroute_count;
      }
      if (m.player_id !== this.selfId) return;
      const sim = this.simulated();
      if (sim?.walking) this.walkRoute(sim); // keep auto-walking on the new route
      this.map.setRoute(m.route);
      this.map.flashRoute();
      this.hud?.setRoute(m.route, m.reroute_count);
      if (m.reason === "off_route") this.hud?.toast("🔀 Off the path – new route calculated");
      if (m.reason === "retry_routing" && m.route.source === "osrm")
        this.hud?.toast("✅ Routing is back online");
    });

    socket.on("goal.reached", (m) => {
      this.simulated()?.stopWalking();
      this.debug?.setWalking(false);
      this.applyState(m.session);
      this.showResultOnce(m.player_id, m.name, m.elapsed_s);
    });

    socket.on("player.joined", (p) => {
      if (!this.session || this.findPlayer(p.id)) return;
      this.session.players.push(p);
      this.map.upsertPlayer(p.id, p.name, p.position);
      this.refreshPlayers();
      this.hud?.toast(`👋 ${p.name} joined the race`);
    });

    socket.on("player.presence", (m) => {
      const p = this.findPlayer(m.player_id);
      if (p) p.connected = m.connected;
      this.map.setPlayerConnected(m.player_id, m.connected);
      this.refreshPlayers();
    });

    socket.on("error", (m) => this.hud?.toast(`⚠️ ${m.message}`, 4000));
    socket.connect();
  }

  private applyState(s: SessionView): void {
    this.session = s;
    this.map.setGoal(s.goal, s.reach_radius_m);
    for (const p of s.players) {
      // Our own marker follows local fixes; don't snap it back to a stale server copy.
      const pos = p.id === this.selfId && this.selfPos ? this.selfPos : p.position;
      this.map.upsertPlayer(p.id, p.name, pos);
      this.map.setPlayerConnected(p.id, p.connected || p.id === this.selfId);
    }
    const me = this.selfPlayer;
    if (me?.route) {
      this.map.setRoute(me.route);
      this.hud?.setRoute(me.route, me.reroute_count);
      this.hud?.setDistances(me.distance_to_goal_m, me.remaining_route_m);
    }
    this.refreshPlayers();
    if (s.status === "finished" && s.winner_id) {
      const winner = this.findPlayer(s.winner_id);
      const elapsed = (Date.parse(s.finished_at ?? s.created_at) - Date.parse(s.created_at)) / 1000;
      this.showResultOnce(s.winner_id, winner?.name ?? "Someone", elapsed);
    }
  }

  private showResultOnce(winnerId: string, winnerName: string, elapsedS: number): void {
    if (this.resultShown) return;
    this.resultShown = true;
    showResult({
      won: winnerId === this.selfId,
      winnerName,
      elapsedS,
      onNewGame: () => this.newGame(),
    });
  }

  private refreshPlayers(): void {
    if (this.session) this.hud?.setPlayers(this.session.players, this.selfId, this.session.winner_id);
  }

  private async invite(): Promise<void> {
    if (!this.session) return;
    const link = `${location.origin}${location.pathname}?join=${encodeURIComponent(this.session.id)}`;
    try {
      await navigator.clipboard.writeText(link);
      this.hud?.toast("🔗 Invite link copied – open it in another tab or device");
    } catch {
      window.prompt("Share this link to race against someone:", link);
    }
  }

  private findPlayer(id: string): PlayerView | undefined {
    return this.session?.players.find((p) => p.id === id);
  }

  private selfName(): string {
    return this.selfPlayer?.name ?? "You";
  }

  /** Until the server replies, estimate from the last known value. */
  private remainingFallback(): number {
    if (!this.selfPos || !this.session) return 0;
    const direct = haversineM(this.selfPos, this.session.goal);
    const me = this.selfPlayer;
    return me?.route?.source === "osrm" ? Math.max(me.remaining_route_m, direct) : direct;
  }
}

function describeError(err: unknown): string {
  if (err instanceof ApiError) return `Server error (${err.status}): ${err.message}`;
  if (err instanceof Error) return err.message;
  return String(err);
}

function safeStorage<T>(fn: () => T): T | null {
  try {
    return fn();
  } catch {
    return null;
  }
}
