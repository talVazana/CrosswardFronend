import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

const { mockPush, mockReplace, mockAuthCallback } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockReplace: vi.fn(),
  mockAuthCallback: { current: undefined as undefined | ((user: unknown) => void) },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
}));

vi.mock("@/lib/auth", () => ({
  signInWithGoogle: vi.fn(async () => {}),
  getIdToken: vi.fn(async () => "fake-token"),
  onAuthChange: vi.fn((cb: (user: unknown) => void) => {
    mockAuthCallback.current = cb;
    return () => {};
  }),
}));

import AdminRoomsPage from "../src/app/admin/rooms/page";
import { getIdToken, signInWithGoogle } from "../src/lib/auth";
import type { RoomSummary } from "../src/utils/rooms";

const room: RoomSummary = {
  roomId: "alpha",
  title: "Alpha",
  status: "active",
  playerCount: 2,
  width: 11,
  height: 11,
  clueCount: 24,
};

function jsonResponse(data: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  } as Response;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  mockPush.mockReset();
  mockReplace.mockReset();
});

describe("admin room gallery", () => {
  it("shows the Google sign-in entry when the session is missing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "Unauthorized" }, 401)),
    );

    render(<AdminRoomsPage />);

    expect(await screen.findByText("Admin entry")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Sign in with Google" }),
    ).toBeTruthy();
  });

  it("signs in with Google and then lists rooms", async () => {
    let adminGalleryCalls = 0;
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/admin/rooms")) {
          adminGalleryCalls += 1;
          return adminGalleryCalls === 1
            ? jsonResponse({ detail: "Unauthorized" }, 401)
            : jsonResponse([room]);
        }
        if (url.endsWith("/admin/session")) {
          return jsonResponse({
            roomId: "alpha",
            playerId: "admin-1",
            displayName: "shachar383838@gmail.com",
          });
        }
        throw new Error(`Unexpected fetch: ${url}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<AdminRoomsPage />);
    await screen.findByText("Admin entry");
    fireEvent.click(screen.getByRole("button", { name: "Sign in with Google" }));
    // Simulate Firebase auth reporting a signed-in user.
    mockAuthCallback.current?.({ uid: "user-1" });

    expect(await screen.findByText("All rooms")).toBeTruthy();
    expect(screen.getByText("Alpha")).toBeTruthy();

    const sessionCall = fetchMock.mock.calls.find(([url]) =>
      String(url).endsWith("/admin/session"),
    );
    expect(sessionCall).toBeTruthy();
    expect((sessionCall?.[1] as RequestInit).headers).toMatchObject({
      Authorization: "Bearer fake-token",
    });
    expect((sessionCall?.[1] as RequestInit).credentials).toBe("include");
  });

  it("lists rooms with links to each dashboard and the player view", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse([room])),
    );

    render(<AdminRoomsPage />);

    expect(await screen.findByText("All rooms")).toBeTruthy();
    expect(
      screen.getByRole("link", { name: "Open dashboard" }).getAttribute("href"),
    ).toBe("/admin/rooms/alpha");
    expect(
      screen.getByRole("link", { name: "Player view" }).getAttribute("href"),
    ).toBe("/rooms/alpha");
  });

  it("reports a non-admin Google account", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/admin/rooms")) {
          return jsonResponse({ detail: "Unauthorized" }, 401);
        }
        if (url.endsWith("/admin/session")) {
          return jsonResponse({ detail: "Forbidden" }, 403);
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    render(<AdminRoomsPage />);
    await screen.findByText("Admin entry");
    fireEvent.click(screen.getByRole("button", { name: "Sign in with Google" }));
    // Simulate Firebase auth reporting a signed-in user (non-admin).
    mockAuthCallback.current?.({ uid: "user-1" });

    expect(await screen.findByText("This account is not an admin.")).toBeTruthy();
  });
});
