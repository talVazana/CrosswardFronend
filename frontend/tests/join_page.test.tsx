import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import Page from "../src/app/rooms/[roomId]/join/page";

const { mockPush } = vi.hoisted(() => ({ mockPush: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    refresh: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    prefetch: vi.fn(),
  }),
  useParams: () => ({ roomId: "room-42" }),
}));

function submitWith(name: string) {
  const { container } = render(<Page />);
  const nameInput = screen.getByRole("textbox");
  fireEvent.change(nameInput, { target: { value: name } });
  const form = container.querySelector("form") as HTMLFormElement;
  fireEvent.submit(form);
  return { container, form };
}

beforeEach(() => {
  mockPush.mockReset();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("TASK-012 join page", () => {
  it("Given the join form, when the user types Amir and submits, then fetch is POSTed with the display name and credentials include", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({}),
    });
    vi.stubGlobal("fetch", mockFetch);

    submitWith("Amir");

    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(1));
    const [url, init] = mockFetch.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("include");
    expect(String(url)).toContain("/rooms/room-42/join");
    expect(JSON.parse(init.body)).toEqual({ displayName: "Amir" });
  });

  it("Given the join form, then no color picker is shown because colors are assigned by the system", () => {
    const { container } = render(<Page />);
    expect(container.querySelector('input[type="color"]')).toBeNull();
    expect(screen.queryByText("Color")).toBeNull();
    expect(screen.getByText(/assigned automatically/i)).toBeTruthy();
  });

  it("Given a successful fetch response (200), when the form is submitted, then router.push is called with the target room URL", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ status: 200, ok: true, json: async () => ({}) })
    );

    submitWith("Amir");

    await waitFor(() => expect(mockPush).toHaveBeenCalledTimes(1));
    expect(mockPush).toHaveBeenCalledWith("/rooms/room-42");
  });

  it("Given a failed fetch response (404), when the form is submitted, then an error message containing error or not found appears", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        status: 404,
        ok: false,
        json: async () => ({ detail: "Room not found" }),
      })
    );

    submitWith("Amir");

    const alert = await screen.findByRole("alert");
    expect(alert.textContent ?? "").toMatch(/error|not found/i);
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("Edge: submitting with an empty name does not trigger fetch", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({}),
    });
    vi.stubGlobal("fetch", mockFetch);

    submitWith("");

    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    expect(mockFetch).not.toHaveBeenCalled();
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("Edge: network error during fetch displays an Offline or Network Error message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    submitWith("Amir");

    const alert = await screen.findByRole("alert");
    expect(alert.textContent ?? "").toMatch(/offline|network error/i);
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("Acceptance: 422 validation error response renders its error text without crashing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        status: 422,
        ok: false,
        json: async () => ({ detail: "Validation error" }),
      })
    );

    const { container } = submitWith("Amir");

    const alert = await screen.findByRole("alert");
    expect(alert.textContent ?? "").toMatch(/validation error/i);
    expect(container.querySelector("form")).toBeTruthy();
    expect(mockPush).not.toHaveBeenCalled();
  });
});
