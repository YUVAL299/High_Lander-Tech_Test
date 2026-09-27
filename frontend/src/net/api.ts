import type { JoinedSession, LatLngPos, PublicConfig, SessionView } from "../types/protocol";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(resp.status, detail);
  }
  return (await resp.json()) as T;
}

export const api = {
  config: () => request<PublicConfig>("/api/config"),

  createSession: (position: LatLngPos, name?: string) =>
    request<JoinedSession>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ position, name: name || null }),
    }),

  joinSession: (sessionId: string, position: LatLngPos, name?: string) =>
    request<JoinedSession>(`/api/sessions/${encodeURIComponent(sessionId)}/players`, {
      method: "POST",
      body: JSON.stringify({ position, name: name || null }),
    }),

  getSession: (sessionId: string) =>
    request<SessionView>(`/api/sessions/${encodeURIComponent(sessionId)}`),
};
