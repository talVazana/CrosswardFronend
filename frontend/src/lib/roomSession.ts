const STORAGE_PREFIX = "crossword:room-session:";

export function getRoomSessionToken(roomId: string): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.sessionStorage.getItem(STORAGE_PREFIX + roomId);
}

export function setRoomSessionToken(roomId: string, token: string | null): void {
  if (typeof window === "undefined") {
    return;
  }
  if (token) {
    window.sessionStorage.setItem(STORAGE_PREFIX + roomId, token);
  } else {
    window.sessionStorage.removeItem(STORAGE_PREFIX + roomId);
  }
}

export function roomFetch(
  roomId: string,
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
  const headers = new Headers(init.headers);
  const token = getRoomSessionToken(roomId);
  if (token) {
    headers.set("X-Session-Token", token);
  }
  return fetch(`${base}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
}
