import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, cleanup } from "@testing-library/react";
import { useRoomLiveUpdates } from "../src/hooks/useRoomLiveUpdates";

type Listener = ((ev: unknown) => void) | null;

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  init: unknown;
  closed = false;
  onopen: Listener = null;
  onmessage: Listener = null;
  onerror: Listener = null;
  constructor(url: string, init?: unknown) {
    this.url = url;
    this.init = init;
    MockEventSource.instances.push(this);
    events.push("connect");
  }
  close() {
    this.closed = true;
  }
}

const ROOM_ID = "room-1";
const events: string[] = [];

function installMocks() {
  MockEventSource.instances = [];
  events.length = 0;

  vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);

  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    events.push("fetch");
    void input;
    return {
      ok: true,
      status: 200,
      json: async () => ({ roomId: ROOM_ID, status: "authoritative" }),
    } as Response;
  });
  vi.stubGlobal("fetch", fetchMock);

  return fetchMock;
}

function latest(): MockEventSource {
  const inst = MockEventSource.instances[MockEventSource.instances.length - 1];
  if (!inst) throw new Error("no EventSource instance created");
  return inst;
}

function fireOpen(inst: MockEventSource) {
  events.push("open");
  act(() => {
    inst.onopen?.({});
  });
}

function fireError(inst: MockEventSource) {
  act(() => {
    inst.onerror?.({});
  });
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("TASK-039 useRoomLiveUpdates", () => {
  it("Given the hook mounts, when the stream fires onopen, then connectionState is connected and fetch is triggered for GET /rooms/room-1/state", async () => {
    const fetchMock = installMocks();
    const { result } = renderHook(() => useRoomLiveUpdates({ roomId: ROOM_ID }));

    expect(result.current.connectionState).toBe("connecting");
    expect(MockEventSource.instances).toHaveLength(1);
    expect(latest().url).toContain(`/rooms/${ROOM_ID}/events`);
    expect(fetchMock).not.toHaveBeenCalled();

    fireOpen(latest());

    expect(result.current.connectionState).toBe("connected");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url] = fetchMock.mock.calls[0];
    expect(String(url)).toContain(`/rooms/${ROOM_ID}/state`);

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(result.current.connectionState).toBe("connected");
  });

  it("Given a connection is established, when onopen fires, then the authoritative fetch happens strictly after the connection opens", () => {
    const fetchMock = installMocks();
    renderHook(() => useRoomLiveUpdates({ roomId: ROOM_ID }));

    const connectIndex = events.indexOf("connect");
    expect(connectIndex).toBeGreaterThanOrEqual(0);

    fireOpen(latest());

    expect(events).toContain("open");
    expect(events).toContain("fetch");
    expect(events.indexOf("fetch")).toBeGreaterThan(events.indexOf("open"));
    expect(events.indexOf("fetch")).toBeGreaterThan(connectIndex);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("Given an active connection, when the stream fires onerror, then connectionState transitions to disconnected", () => {
    installMocks();
    const { result } = renderHook(() => useRoomLiveUpdates({ roomId: ROOM_ID }));

    fireOpen(latest());
    expect(result.current.connectionState).toBe("connected");

    fireError(latest());

    expect(result.current.connectionState).toBe("disconnected");
  });

  it("Given a disconnected state, when the reconnection timer fires, then a new connection attempt is made", () => {
    installMocks();
    const { result } = renderHook(() => useRoomLiveUpdates({ roomId: ROOM_ID }));

    fireOpen(latest());
    fireError(latest());
    expect(result.current.connectionState).toBe("disconnected");
    expect(MockEventSource.instances).toHaveLength(1);

    act(() => {
      vi.advanceTimersByTime(999);
    });
    expect(MockEventSource.instances).toHaveLength(1);

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(MockEventSource.instances).toHaveLength(2);
    expect(latest().url).toContain(`/rooms/${ROOM_ID}/events`);
    expect(latest().closed).toBe(false);
  });

  it("Edge: rapid flapping (repeated errors with reconnects) does not cause infinite fetch loops and fetch count stays bounded", () => {
    const fetchMock = installMocks();
    renderHook(() => useRoomLiveUpdates({ roomId: ROOM_ID }));

    fireError(latest());
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(MockEventSource.instances).toHaveLength(2);

    fireError(latest());
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(MockEventSource.instances).toHaveLength(3);

    fireError(latest());
    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(MockEventSource.instances).toHaveLength(4);

    expect(fetchMock).not.toHaveBeenCalled();

    fireOpen(latest());
    expect(fetchMock).toHaveBeenCalledTimes(1);

    act(() => {
      vi.advanceTimersByTime(60000);
    });
    expect(MockEventSource.instances).toHaveLength(4);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("Edge: mount without a roomId creates no connection and no fetch", () => {
    const fetchMock = installMocks();
    const { result } = renderHook(() => useRoomLiveUpdates({ roomId: "" }));

    expect(result.current.connectionState).toBe("connecting");
    expect(MockEventSource.instances).toHaveLength(0);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
