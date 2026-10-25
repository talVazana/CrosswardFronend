import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/react";

const { mockUseParams } = vi.hoisted(() => ({
  mockUseParams: vi.fn(() => ({ roomId: "room-1" })),
}));

vi.mock("next/navigation", () => ({
  useParams: mockUseParams,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import Scoreboard from "../src/components/Scoreboard";
import RoomLobbyPage from "../src/app/rooms/[roomId]/page";
import AdminRoomDashboardPage from "../src/app/admin/rooms/[roomId]/page";

const SCORES = [
  { playerId: "p1", displayName: "Dana", color: "#FF0000", totalPoints: 2 },
];

const ROOM = {
  roomId: "room-1",
  title: "Room One",
  status: "lobby",
  participants: [{ playerId: "p9", displayName: "Alice", color: "#00FF00" }],
  pendingSubmissions: [],
  scores: [],
};

function response(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

function isScoreUrl(input: RequestInfo | URL) {
  return String(input).endsWith("/rooms/room-1/scores");
}

function fetchReturningScores() {
  return vi.fn(async (input: RequestInfo | URL) => {
    if (isScoreUrl(input)) return response(200, SCORES);
    if (String(input).includes("/admin/rooms/room-1")) return response(200, ROOM);
    return response(200, ROOM);
  });
}

function isRed(backgroundColor: string) {
  const normalized = backgroundColor.replace(/\s/g, "").toLowerCase();
  return normalized === "rgb(255,0,0)" || normalized === "#ff0000";
}

class MockEventSource {
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  addEventListener() {}
  removeEventListener() {}
  close() {}
}

beforeEach(() => {
  mockUseParams.mockReturnValue({ roomId: "room-1" });
  vi.stubGlobal("EventSource", MockEventSource);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("TASK-048 Scoreboard UI", () => {
  it("renders displayName, color dot with player color, and totalPoints from API", async () => {
    vi.stubGlobal("fetch", fetchReturningScores());
    render(<Scoreboard roomId="room-1" />);

    expect(await screen.findByText("Dana")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
    const dot = screen.getByTestId("score-color");
    expect(isRed(dot.style.backgroundColor)).toBe(true);
  });

  it("shows Loading... while fetch is pending", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})));
    render(<Scoreboard roomId="room-1" />);
    expect(screen.getByText("Loading...")).toBeTruthy();
  });

  it("shows a fallback message and does not throw when fetch rejects", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("network down")))
    );
    render(<Scoreboard roomId="room-1" />);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent && alert.textContent.length > 0).toBe(true);
    expect(screen.queryByText("Loading...")).toBeNull();
  });

  it("shows No scores yet. when the API returns an empty array", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => response(200, []))
    );
    render(<Scoreboard roomId="room-1" />);
    expect(await screen.findByText("No scores yet.")).toBeTruthy();
  });

  it("edge: fetch URL ends with /rooms/<roomId>/scores, uses backend base URL and credentials include", async () => {
    const mockFetch = fetchReturningScores();
    vi.stubGlobal("fetch", mockFetch);
    render(<Scoreboard roomId="room-1" />);
    await screen.findByText("Dana");

    await waitFor(() => {
      const scoreCall = mockFetch.mock.calls.find(([input]) =>
        isScoreUrl(input)
      );
      expect(scoreCall).toBeTruthy();
    });
    const scoreCall = mockFetch.mock.calls.find(([input]) =>
      isScoreUrl(input)
    ) as [RequestInfo | URL, RequestInit];
    expect(String(scoreCall[0])).toBe(
      "http://localhost:8000/rooms/room-1/scores"
    );
    expect(scoreCall[1]?.credentials).toBe("include");
  });

  it("room lobby page renders the scoreboard alongside the participant list", async () => {
    vi.stubGlobal("fetch", fetchReturningScores());
    render(<RoomLobbyPage />);

    expect(await screen.findByText("Dana")).toBeTruthy();
    expect(await screen.findByText("Alice")).toBeTruthy();
    expect(screen.getByRole("list", { name: "Participants" })).toBeTruthy();
    expect(screen.getByRole("list", { name: "Scoreboard" })).toBeTruthy();
  });

  it("admin dashboard page renders the scoreboard for its room", async () => {
    vi.stubGlobal("fetch", fetchReturningScores());
    render(<AdminRoomDashboardPage />);

    expect(await screen.findByText("Room One")).toBeTruthy();
    expect(await screen.findByText("Dana")).toBeTruthy();
    expect(screen.getByRole("list", { name: "Scoreboard" })).toBeTruthy();
  });
});
