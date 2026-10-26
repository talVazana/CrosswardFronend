import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

const harness = vi.hoisted(() => ({
  onNext: null as null | ((rooms: unknown) => void),
  onError: null as null | ((error: Error) => void),
}));

vi.mock("../src/lib/roomsStore", () => ({
  subscribeRooms: (
    onNext: (rooms: unknown) => void,
    onError?: (error: Error) => void,
  ) => {
    harness.onNext = onNext;
    harness.onError = onError ?? null;
    return () => {};
  },
  subscribeRoom: () => () => {},
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

function stubHealth() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/health")) return jsonResponse({ status: "ok" });
      throw new Error(`Unexpected fetch: ${String(input)}`);
    }),
  );
}

function emitRooms(value: unknown) {
  act(() => {
    harness.onNext?.(value);
  });
}

function emitError(error: Error) {
  act(() => {
    harness.onError?.(error);
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  harness.onNext = null;
  harness.onError = null;
});

describe("landing page room gallery", () => {
  it("renders every room with its active or inactive status", async () => {
    stubHealth();
    render(<Page />);
    emitRooms(rooms);

    expect(await screen.findByText("Alpha")).toBeTruthy();
    expect(screen.getByText("Beta")).toBeTruthy();
    expect(screen.getByText("Room gallery")).toBeTruthy();
    expect(screen.getAllByText("Active now")).toHaveLength(1);
    expect(screen.getAllByText("Not active")).toHaveLength(1);
  });

  it("links each room to its join page and exposes the admin entry", async () => {
    stubHealth();
    render(<Page />);
    emitRooms(rooms);

    await screen.findByText("Alpha");
    const joinLinks = screen.getAllByRole("link", { name: "Join room" });
    expect(joinLinks[0].getAttribute("href")).toBe("/rooms/alpha/join");
    expect(joinLinks[1].getAttribute("href")).toBe("/rooms/beta/join");
    expect(
      screen.getByRole("link", { name: "Admin" }).getAttribute("href"),
    ).toBe("/admin/rooms");
  });

  it("shows an empty state when no rooms exist", async () => {
    stubHealth();
    render(<Page />);
    emitRooms([]);

    expect(await screen.findByText("No rooms yet")).toBeTruthy();
  });

  it("shows an error when the gallery fails to load", async () => {
    stubHealth();
    render(<Page />);
    emitError(new Error("network down"));

    expect(await screen.findByText("Could not load rooms")).toBeTruthy();
  });
});
