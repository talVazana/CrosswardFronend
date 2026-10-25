import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

import Page from "../src/app/page";
import type { RoomSummary } from "../src/utils/rooms";

const rooms: RoomSummary[] = [
  {
    roomId: "alpha",
    title: "Alpha",
    status: "active",
    playerCount: 3,
    width: 11,
    height: 11,
    clueCount: 24,
  },
  {
    roomId: "beta",
    title: "Beta",
    status: "lobby",
    playerCount: 0,
    width: 5,
    height: 5,
    clueCount: 6,
  },
];

function jsonResponse(data: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  } as Response;
}

function mockFetch(roomResponse: () => Promise<Response>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("/health")) return jsonResponse({ status: "ok" });
    if (url.endsWith("/rooms")) return roomResponse();
    throw new Error(`Unexpected fetch: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("landing page room gallery", () => {
  it("renders every room with its active or inactive status", async () => {
    mockFetch(async () => jsonResponse(rooms));

    render(<Page />);

    expect(await screen.findByText("Alpha")).toBeTruthy();
    expect(screen.getByText("Beta")).toBeTruthy();
    expect(screen.getByText("Room gallery")).toBeTruthy();
    expect(screen.getAllByText("Active now")).toHaveLength(1);
    expect(screen.getAllByText("Not active")).toHaveLength(1);
  });

  it("links each room to its join page and exposes the admin entry", async () => {
    mockFetch(async () => jsonResponse(rooms));

    render(<Page />);

    await screen.findByText("Alpha");
    const joinLinks = screen.getAllByRole("link", { name: "Join room" });
    expect(joinLinks[0].getAttribute("href")).toBe("/rooms/alpha/join");
    expect(joinLinks[1].getAttribute("href")).toBe("/rooms/beta/join");
    expect(
      screen.getByRole("link", { name: "Admin" }).getAttribute("href"),
    ).toBe("/admin/rooms");
  });

  it("shows an empty state when no rooms exist", async () => {
    mockFetch(async () => jsonResponse([]));

    render(<Page />);

    expect(await screen.findByText("No rooms yet")).toBeTruthy();
  });

  it("shows a retryable error when the gallery request fails", async () => {
    mockFetch(async () => jsonResponse({ detail: "boom" }, 500));

    render(<Page />);

    expect(await screen.findByText("Could not load rooms")).toBeTruthy();
    expect(screen.getByText("Try again")).toBeTruthy();
  });
});
