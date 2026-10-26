import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { act, render, screen, cleanup } from "@testing-library/react";

const { mockUseParams } = vi.hoisted(() => ({
  mockUseParams: vi.fn(() => ({ roomId: "room-1" })),
}));

vi.mock("next/navigation", () => ({
  useParams: mockUseParams,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

const harness = vi.hoisted(() => ({
  onNext: null as null | ((room: unknown) => void),
  onError: null as null | ((error: Error) => void),
}));

vi.mock("../src/lib/roomsStore", () => ({
  subscribeRoom: (
    _roomId: string,
    onNext: (room: unknown) => void,
    onError?: (error: Error) => void,
  ) => {
    harness.onNext = onNext;
    harness.onError = onError ?? null;
    return () => {};
  },
  subscribeRooms: () => () => {},
}));

import Scoreboard from "../src/components/Scoreboard";
import RoomLobbyPage from "../src/app/rooms/[roomId]/page";
import AdminRoomDashboardPage from "../src/app/admin/rooms/[roomId]/page";

const SCORES = [
  { playerId: "p1", displayName: "Dana", color: "#FF0000", totalPoints: 2 },
];

const ADMIN_ROOM = {
  roomId: "room-1",
  title: "Room One",
  status: "lobby",
  participants: [{ playerId: "p1", displayName: "Dana", color: "#FF0000" }],
  pendingSubmissions: [],
  scores: [{ playerId: "p1", score: 2 }],
};

function response(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

function isRed(backgroundColor: string) {
  const normalized = backgroundColor.replace(/\s/g, "").toLowerCase();
  return normalized === "rgb(255,0,0)" || normalized === "#ff0000";
}

function emitRoom(value: unknown) {
  act(() => {
    harness.onNext?.(value);
  });
}

beforeEach(() => {
  mockUseParams.mockReturnValue({ roomId: "room-1" });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  harness.onNext = null;
  harness.onError = null;
});

describe("TASK-048 Scoreboard UI", () => {
  it("renders displayName, color dot with player color, and totalPoints", () => {
    render(<Scoreboard scores={SCORES} />);

    expect(screen.getByText("Dana")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
    const dot = screen.getByTestId("score-color");
    expect(isRed(dot.style.backgroundColor)).toBe(true);
  });

  it("shows Loading... while the loading prop is set", () => {
    render(<Scoreboard loading />);
    expect(screen.getByText("Loading...")).toBeTruthy();
  });

  it("shows No scores yet. when scores are empty", () => {
    render(<Scoreboard scores={[]} />);
    expect(screen.getByText("No scores yet.")).toBeTruthy();
  });

  it("shows No scores yet. when scores are not provided", () => {
    render(<Scoreboard />);
    expect(screen.getByText("No scores yet.")).toBeTruthy();
  });

  it("room lobby page renders the scoreboard alongside the participant list", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input).endsWith("/player-progress")) {
          return response(200, { solved: [], revealed: [] });
        }
        throw new Error(`Unexpected fetch: ${String(input)}`);
      }),
    );

    render(<RoomLobbyPage />);
    emitRoom({
      roomId: "room-1",
      title: "Room One",
      status: "lobby",
      players: [{ id: "p9", displayName: "Alice", color: "#00FF00" }],
      solvedClues: [],
      scores: SCORES,
    });

    expect(await screen.findByText("Dana")).toBeTruthy();
    expect(await screen.findByText("Alice")).toBeTruthy();
    expect(screen.queryByRole("list", { name: "Participants" })).toBeNull();
    expect(screen.getByRole("list", { name: "Scoreboard" })).toBeTruthy();
  });

  it("admin dashboard page renders the scoreboard for its room", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input).includes("/admin/rooms/room-1")) {
          return response(200, ADMIN_ROOM);
        }
        throw new Error(`Unexpected fetch: ${String(input)}`);
      }),
    );

    render(<AdminRoomDashboardPage />);

    expect(await screen.findByText("Room One")).toBeTruthy();
    const scoreboard = await screen.findByRole("list", { name: "Scoreboard" });
    expect(scoreboard.textContent).toContain("Dana");
    expect(scoreboard.textContent).toContain("2");
  });
});
