import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

const { mockPush, mockReplace } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockReplace: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
}));

import AdminRoomsPage from "../src/app/admin/rooms/page";
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
  it("shows the admin token entry when the session is missing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "Unauthorized" }, 401)),
    );

    render(<AdminRoomsPage />);

    expect(await screen.findByText("Admin entry")).toBeTruthy();
    expect(screen.getByLabelText("Admin password")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Enter admin area" }),
    ).toBeTruthy();
  });

  it("exchanges the admin password for a session and then lists rooms", async () => {
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
            displayName: "Admin",
          });
        }
        throw new Error(`Unexpected fetch: ${url}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<AdminRoomsPage />);
    await screen.findByText("Admin entry");
    fireEvent.change(screen.getByLabelText("Admin password"), {
      target: { value: "1234" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enter admin area" }));

    expect(await screen.findByText("All rooms")).toBeTruthy();
    expect(screen.getByText("Alpha")).toBeTruthy();

    const sessionCall = fetchMock.mock.calls.find(([url]) =>
      String(url).endsWith("/admin/session"),
    );
    expect(sessionCall).toBeTruthy();
    expect(JSON.parse(String((sessionCall?.[1] as RequestInit).body))).toEqual({
      password: "1234",
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

  it("reports an incorrect admin password", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/admin/rooms")) {
          return jsonResponse({ detail: "Unauthorized" }, 401);
        }
        if (url.endsWith("/admin/session")) {
          return jsonResponse({ detail: "Invalid admin password" }, 401);
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    render(<AdminRoomsPage />);
    await screen.findByText("Admin entry");
    fireEvent.change(screen.getByLabelText("Admin password"), {
      target: { value: "wrong" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enter admin area" }));

    expect(await screen.findByText("Incorrect admin password.")).toBeTruthy();
  });
});
