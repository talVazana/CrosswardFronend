import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";

const { mockUseParams } = vi.hoisted(() => ({
  mockUseParams: vi.fn(() => ({ roomId: "room-1" })),
}));

vi.mock("next/navigation", () => ({
  useParams: mockUseParams,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("@/lib/auth", () => ({
  adminFetch: (path: string, init?: RequestInit) => {
    const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
    return fetch(`${base}${path}`, { ...init, credentials: "include" });
  },
  onAuthChange: (cb: (user: unknown) => void) => {
    cb({ uid: "admin", email: "admin@example.com" });
    return () => {};
  },
}));

import AdminRoomDashboardPage from "../src/app/admin/rooms/[roomId]/page";

function response(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

function room(status: string) {
  return {
    roomId: "room-1",
    title: "Room One",
    status,
    participants: [{ playerId: "p1", displayName: "Alice", color: "#ff0000" }],
    pendingSubmissions: [],
    scores: [],
  };
}

function makeFetch(options: { getStatus: string; postResponse?: () => Response }) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    if (method === "POST") {
      return options.postResponse ? options.postResponse() : response(200, room("active"));
    }
    return response(200, room(options.getStatus));
  });
}

function postCalls(mockFetch: ReturnType<typeof vi.fn>) {
  return mockFetch.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === "POST");
}

function button(name: string): HTMLButtonElement {
  return screen.getByRole("button", { name }) as HTMLButtonElement;
}

async function renderLoaded(status: string) {
  const mockFetch = makeFetch({ getStatus: status });
  vi.stubGlobal("fetch", mockFetch);
  render(<AdminRoomDashboardPage />);
  await screen.findByRole("button", { name: "Start" });
  return mockFetch;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("TASK-034 admin dashboard UI", () => {
  it("lobby state: Start enabled, Pause/Resume disabled", async () => {
    await renderLoaded("lobby");
    expect(button("Start").disabled).toBe(false);
    expect(button("Pause").disabled).toBe(true);
    expect(button("Resume").disabled).toBe(true);
  });

  it("click Start sends POST to /admin/rooms/room-1/start", async () => {
    const mockFetch = await renderLoaded("lobby");
    fireEvent.click(button("Start"));
    await waitFor(() => expect(postCalls(mockFetch).length).toBe(1));
    const [url, init] = postCalls(mockFetch)[0];
    expect(String(url).endsWith("/admin/rooms/room-1/start")).toBe(true);
    expect(init?.credentials).toBe("include");
  });

  it("active state: Finish with confirm=false never sends a POST request", async () => {
    const mockFetch = await renderLoaded("active");
    const confirm = vi.fn(() => false);
    vi.stubGlobal("confirm", confirm);
    expect(button("Finish").disabled).toBe(false);
    fireEvent.click(button("Finish"));
    await waitFor(() => expect(confirm).toHaveBeenCalledTimes(1));
    await new Promise((r) => setTimeout(r, 50));
    expect(postCalls(mockFetch).length).toBe(0);
  });

  it("active state: Finish with confirm=true sends POST to /admin/rooms/room-1/finish", async () => {
    const mockFetch = makeFetch({
      getStatus: "active",
      postResponse: () => response(200, room("finished")),
    });
    vi.stubGlobal("fetch", mockFetch);
    vi.stubGlobal("confirm", vi.fn(() => true));
    render(<AdminRoomDashboardPage />);
    await screen.findByRole("button", { name: "Finish" });
    fireEvent.click(button("Finish"));
    await waitFor(() => expect(postCalls(mockFetch).length).toBe(1));
    const [url, init] = postCalls(mockFetch)[0];
    expect(String(url).endsWith("/admin/rooms/room-1/finish")).toBe(true);
    expect(init?.credentials).toBe("include");
  });

  it("edge: 400 Invalid Transition shows an alert without breaking the dashboard", async () => {
    const mockFetch = makeFetch({
      getStatus: "active",
      postResponse: () => response(400, { detail: "Invalid Transition" }),
    });
    vi.stubGlobal("fetch", mockFetch);
    vi.stubGlobal("confirm", vi.fn(() => true));
    render(<AdminRoomDashboardPage />);
    await screen.findByRole("button", { name: "Finish" });
    fireEvent.click(button("Finish"));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/Failed to finish room/i);
    expect(button("Finish")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Room One" })).toBeTruthy();
  });

  it("close requires confirmation: confirm=false sends no POST", async () => {
    const mockFetch = await renderLoaded("finished");
    const confirm = vi.fn(() => false);
    vi.stubGlobal("confirm", confirm);
    expect(button("Close").disabled).toBe(false);
    fireEvent.click(button("Close"));
    await waitFor(() => expect(confirm).toHaveBeenCalledTimes(1));
    await new Promise((r) => setTimeout(r, 50));
    expect(postCalls(mockFetch).length).toBe(0);
  });

  it("close after confirmation sends POST to /admin/rooms/room-1/close", async () => {
    const mockFetch = await renderLoaded("finished");
    vi.stubGlobal("confirm", vi.fn(() => true));
    fireEvent.click(button("Close"));
    await waitFor(() => expect(postCalls(mockFetch).length).toBe(1));
    const [url] = postCalls(mockFetch)[0];
    expect(String(url).endsWith("/admin/rooms/room-1/close")).toBe(true);
  });

  it("successful action refreshes state and updates button availability", async () => {
    let phase = 0;
    const mockFetch = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        phase = 1;
        return response(200, room("active"));
      }
      return response(200, room(phase === 0 ? "lobby" : "active"));
    });
    vi.stubGlobal("fetch", mockFetch);
    render(<AdminRoomDashboardPage />);
    await screen.findByRole("button", { name: "Start" });
    expect(button("Start").disabled).toBe(false);
    fireEvent.click(button("Start"));
    await waitFor(() => expect(button("Pause").disabled).toBe(false));
    expect(button("Start").disabled).toBe(true);
  });

  it("renders the crossword and approves an answer drafted in the admin grid", async () => {
    const puzzle = {
      puzzleId: "puzzle-1",
      title: "Admin puzzle",
      width: 3,
      height: 1,
      cells: [
        { row: 0, col: 0, type: "white", number: null, startsAcross: false, startsDown: false },
        { row: 0, col: 1, type: "white", number: null, startsAcross: false, startsDown: false },
        { row: 0, col: 2, type: "white", number: 1, startsAcross: true, startsDown: false },
      ],
      clues: [
        { clueId: "A1", number: 1, direction: "across", text: "Feline pet", answerLength: 3 },
      ],
    };
    const mockFetch = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "PUT") return response(200, { status: "ok" });
      return response(200, {
        ...room("active"),
        puzzleId: "puzzle-1",
        puzzle,
        officialAnswers: {},
        solvedClues: [],
      });
    });
    vi.stubGlobal("fetch", mockFetch);
    vi.stubGlobal("confirm", vi.fn(() => true));

    render(<AdminRoomDashboardPage />);
    const grid = await screen.findByRole("application", { name: "Admin crossword grid" });
    fireEvent.click(screen.getByTestId("admin-cell-0-2"));
    for (const letter of "CAT") {
      fireEvent.keyDown(grid, { key: letter });
    }
    const approve = screen.getByRole("button", { name: "Approve answer" });
    await waitFor(() => expect((approve as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(approve);

    await waitFor(() => {
      const puts = mockFetch.mock.calls.filter(
        ([, init]) => (init as RequestInit | undefined)?.method === "PUT",
      );
      expect(puts.length).toBe(1);
      const [url, init] = puts[0];
      expect(String(url).endsWith("/admin/puzzles/puzzle-1/clues/A1/answer")).toBe(true);
      expect(JSON.parse((init as RequestInit).body as string)).toEqual({ answer: "CAT" });
    });
  });

  it("approving a pending submission saves the answer for the room puzzle and reloads", async () => {
    const pendingRoom = {
      ...room("active"),
      puzzleId: "puzzle-1",
      pendingSubmissions: [{ clueId: "A1", playerId: "p1", answer: "APPLE" }],
    };
    let gets = 0;
    const mockFetch = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "PUT") return response(200, { status: "ok" });
      gets += 1;
      return response(
        200,
        gets === 1 ? pendingRoom : { ...pendingRoom, pendingSubmissions: [] },
      );
    });
    vi.stubGlobal("fetch", mockFetch);
    vi.stubGlobal("confirm", vi.fn(() => true));

    render(<AdminRoomDashboardPage />);
    const approve = await screen.findByRole("button", {
      name: /Approve clue A1 for Alice/i,
    });
    fireEvent.click(approve);

    await waitFor(() => {
      const puts = mockFetch.mock.calls.filter(
        ([, init]) => (init as RequestInit | undefined)?.method === "PUT",
      );
      expect(puts.length).toBe(1);
    });
    const [putUrl, putInit] = mockFetch.mock.calls.find(
      ([, init]) => (init as RequestInit | undefined)?.method === "PUT",
    )!;
    expect(String(putUrl).endsWith("/admin/puzzles/puzzle-1/clues/A1/answer")).toBe(true);
    expect(JSON.parse((putInit as RequestInit).body as string)).toEqual({
      answer: "APPLE",
    });
    await waitFor(() => expect(gets).toBeGreaterThanOrEqual(2));
  });

  it("rejecting a pending submission posts to the reject endpoint and reloads", async () => {
    const pendingRoom = {
      ...room("active"),
      puzzleId: "puzzle-1",
      pendingSubmissions: [
        { submissionId: "sub-1", clueId: "A1", playerId: "p1", answer: "APPLE" },
      ],
    };
    let gets = 0;
    const mockFetch = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") return response(200, { status: "rejected" });
      gets += 1;
      return response(
        200,
        gets === 1 ? pendingRoom : { ...pendingRoom, pendingSubmissions: [] },
      );
    });
    vi.stubGlobal("fetch", mockFetch);
    vi.stubGlobal("confirm", vi.fn(() => true));

    render(<AdminRoomDashboardPage />);
    const reject = await screen.findByRole("button", {
      name: /Reject answer for clue A1 from Alice/i,
    });
    fireEvent.click(reject);

    await waitFor(() => {
      const posts = mockFetch.mock.calls.filter(
        ([, init]) => (init as RequestInit | undefined)?.method === "POST",
      );
      expect(posts.length).toBe(1);
      expect(String(posts[0][0]).endsWith("/admin/rooms/room-1/submissions/sub-1/reject")).toBe(
        true,
      );
    });
    await waitFor(() => expect(gets).toBeGreaterThanOrEqual(2));
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: /Reject answer for clue A1 from Alice/i }),
      ).toBeNull(),
    );
  });
});
