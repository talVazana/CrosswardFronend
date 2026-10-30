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
  signOutGoogle: vi.fn(async () => {}),
  adminFetch: vi.fn(),
  onAuthChange: vi.fn((cb: (user: unknown) => void) => {
    mockAuthCallback.current = cb;
    return () => {};
  }),
}));

import AdminRoomsPage from "../src/app/admin/rooms/page";
import { adminFetch, signInWithGoogle } from "../src/lib/auth";
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

const adminUser = {
  uid: "user-1",
  email: "shachar383838@gmail.com",
};

function jsonResponse(data: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  } as Response;
}

function mockAdminFetch(handler: (path: string) => Response) {
  vi.mocked(adminFetch).mockImplementation(async (path: string) => handler(path));
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  mockPush.mockReset();
  mockReplace.mockReset();
});

describe("admin room gallery", () => {
  it("shows the Google sign-in entry when the session is missing", async () => {
    mockAdminFetch(() => jsonResponse({ detail: "Unauthorized" }, 401));

    render(<AdminRoomsPage />);
    mockAuthCallback.current?.(null);

    expect(await screen.findByText("Admin entry")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Sign in with Google" }),
    ).toBeTruthy();
  });

  it("enters the admin gallery silently when the Google account is an admin", async () => {
    mockAdminFetch((path) => {
      if (path === "/admin/me") return jsonResponse({ displayName: adminUser.email });
      if (path === "/admin/rooms") return jsonResponse([room]);
      throw new Error(`Unexpected adminFetch: ${path}`);
    });

    render(<AdminRoomsPage />);
    mockAuthCallback.current?.(adminUser);

    expect(await screen.findByText("All rooms")).toBeTruthy();
    expect(screen.getByText("Alpha")).toBeTruthy();
    expect(screen.queryByText("Admin entry")).toBeNull();
    expect(adminFetch).toHaveBeenCalledWith("/admin/me");
    expect(adminFetch).toHaveBeenCalledWith("/admin/rooms");
  });

  it("lists rooms with links to each dashboard and the player view", async () => {
    mockAdminFetch((path) => {
      if (path === "/admin/me") return jsonResponse({ displayName: adminUser.email });
      if (path === "/admin/rooms") return jsonResponse([room]);
      throw new Error(`Unexpected adminFetch: ${path}`);
    });

    render(<AdminRoomsPage />);
    mockAuthCallback.current?.(adminUser);

    expect(await screen.findByText("All rooms")).toBeTruthy();
    expect(
      screen.getByRole("link", { name: "Open dashboard" }).getAttribute("href"),
    ).toBe("/admin/rooms/alpha");
    expect(
      screen.getByRole("link", { name: "Player view" }).getAttribute("href"),
    ).toBe("/rooms/alpha");
  });

  it("reports a non-admin Google account without a sign-in loop", async () => {
    mockAdminFetch(() => jsonResponse({ detail: "Forbidden" }, 403));

    render(<AdminRoomsPage />);
    mockAuthCallback.current?.(null);
    fireEvent.click(await screen.findByRole("button", { name: "Sign in with Google" }));
    mockAuthCallback.current?.({
      uid: "user-2",
      email: "player@example.com",
    });

    expect(await screen.findByText("Not an admin")).toBeTruthy();
    expect(
      screen.getByText(/Signed in as player@example.com/),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Use a different account" }),
    ).toBeTruthy();
    expect(signInWithGoogle).toHaveBeenCalledTimes(1);
  });
});
