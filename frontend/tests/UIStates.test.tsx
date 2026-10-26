import { describe, it, expect, vi, afterEach } from "vitest";
import { act, render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useParams: () => ({ roomId: "room-1" }),
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

import AdminRoomDashboardPage from "../src/app/admin/rooms/[roomId]/page";
import RoomLobbyPage from "../src/app/rooms/[roomId]/page";

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

function scoresRoute(input: RequestInfo | URL): boolean {
  return String(input).endsWith("/scores");
}

function emptyAdminRoom() {
  return {
    roomId: "room-1",
    title: "Room One",
    status: "lobby",
    players: [],
    participants: [],
    pendingSubmissions: [],
    pending: [],
    scores: [],
  };
}

function emitRoom(value: unknown) {
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

describe("TASK-044 loading, error and empty UI states", () => {
  it("Given a board component initiating a fetch, when the promise is pending, then the LoadingSpinner element is found in the document", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => {})),
    );

    render(<RoomLobbyPage />);

    const spinner = await screen.findByTestId("loading-spinner");
    expect(spinner).toBeTruthy();
    expect(spinner.parentElement?.textContent).toMatch(/Loading\.\.\./);
  });

  it("Given an admin dashboard initiating a fetch, when the promise is pending, then the LoadingSpinner element is found in the document", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => {})),
    );

    render(<AdminRoomDashboardPage />);

    const spinner = await screen.findByTestId("loading-spinner");
    expect(spinner).toBeTruthy();
    expect(spinner.parentElement?.textContent).toMatch(/Loading\.\.\./);
  });

  it("Given a board component fetching data, when the fetch rejects with a network error, then ErrorMessage renders a fallback message without crashing the React tree", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input).endsWith("/player-progress")) {
          return jsonResponse({ solved: [], revealed: [] });
        }
        throw new TypeError("Failed to fetch");
      }),
    );

    render(<RoomLobbyPage />);
    emitError(new TypeError("Failed to fetch"));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/Network error|Unable to connect to server/i);
    expect(screen.getByRole("main")).toBeTruthy();
    expect(screen.queryByTestId("loading-spinner")).toBeNull();
  });

  it("Given the admin dashboard fetching data, when the fetch rejects with a network error, then ErrorMessage renders a fallback message without crashing the React tree", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );

    render(<AdminRoomDashboardPage />);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/Network error|Unable to connect to server/i);
    expect(screen.getByRole("main")).toBeTruthy();
  });

  it("Given a board whose API returns an empty array of players, when the response resolves, then the EmptyState component is rendered", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input).endsWith("/player-progress")) {
          return jsonResponse({ solved: [], revealed: [] });
        }
        return jsonResponse({
          roomId: "room-1",
          title: "Empty Room",
          status: "lobby",
          players: [],
        });
      }),
    );

    render(<RoomLobbyPage />);
    emitRoom({
      roomId: "room-1",
      title: "Empty Room",
      status: "lobby",
      players: [],
    });

    await screen.findByText("Empty Room");
    expect(screen.getAllByTestId("empty-state").length).toBeGreaterThan(0);
    expect(screen.getByText("No participants yet")).toBeTruthy();
  });

  it("Given a dashboard whose API returns empty arrays [], when the response resolves, then the EmptyState component is rendered", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (scoresRoute(input)) return jsonResponse([]);
        return jsonResponse(emptyAdminRoom());
      }),
    );

    render(<AdminRoomDashboardPage />);

    await screen.findByText("Room One");
    expect(screen.getAllByTestId("empty-state").length).toBe(3);
    expect(screen.getByText("No participants yet")).toBeTruthy();
    expect(screen.getByText("No pending submissions")).toBeTruthy();
    expect(screen.getByText("No scores yet")).toBeTruthy();
  });

  it("Edge recovery: after a failed fetch the Retry action transitions Error -> Loading -> Success", async () => {
    let pageCalls = 0;
    let resolveRetry!: (value: Response) => void;
    const retryResponse = new Promise<Response>((resolve) => {
      resolveRetry = resolve;
    });

    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        if (scoresRoute(input)) return Promise.resolve(jsonResponse([]));
        pageCalls += 1;
        if (pageCalls === 1) {
          return Promise.reject(new TypeError("Failed to fetch"));
        }
        return retryResponse;
      }),
    );

    render(<AdminRoomDashboardPage />);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/Network error/i);

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    await waitFor(() => {
      expect(screen.queryByRole("alert")).toBeNull();
    });
    const spinnerDuringRetry = screen.queryByTestId("loading-spinner");

    resolveRetry(jsonResponse(emptyAdminRoom()));
    await browserFindRoomOne();

    expect(spinnerDuringRetry).not.toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

async function browserFindRoomOne() {
  await screen.findByText("Room One");
}
