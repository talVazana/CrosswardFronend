import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import CrosswordGrid, { Puzzle } from "../src/components/CrosswordGrid";

const puzzle: Puzzle = {
  puzzleId: "test-puzzle",
  title: "Test",
  width: 3,
  height: 1,
  cells: [
    { row: 0, col: 0, type: "white", number: 1, startsAcross: true, startsDown: false },
    { row: 0, col: 1, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 0, col: 2, type: "white", number: null, startsAcross: false, startsDown: false },
  ],
  clues: [
    { clueId: "A1", number: 1, direction: "across", text: "Feline pet", answerLength: 3 },
  ],
};

function response(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

function renderGrid() {
  const utils = render(<CrosswordGrid roomId="room-1" puzzle={puzzle} />);
  fireEvent.click(screen.getByTestId("cell-0-0"));
  return utils;
}

function getInput(): HTMLInputElement {
  return screen.getByLabelText("Answer draft") as HTMLInputElement;
}

function getSubmit(): HTMLButtonElement {
  return screen.getByRole("button", { name: "Submit" }) as HTMLButtonElement;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("TASK-025 submission UI", () => {
  it("empty draft: Submit button is disabled", () => {
    renderGrid();
    expect(getSubmit().disabled).toBe(true);
  });

  it("empty draft: pressing Enter does not fire fetch", async () => {
    const mockFetch = vi.fn();
    vi.stubGlobal("fetch", mockFetch);
    renderGrid();
    const input = getInput();
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });
    await new Promise((r) => setTimeout(r, 50));
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("click Submit with correct status: shows Correct indicator", async () => {
    const mockFetch = vi.fn().mockResolvedValue(response(200, { status: "correct" }));
    vi.stubGlobal("fetch", mockFetch);
    renderGrid();
    fireEvent.change(getInput(), { target: { value: "cat" } });
    fireEvent.click(getSubmit());
    expect(await screen.findByText("Correct!")).toBeTruthy();
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0];
    expect(String(url)).toContain("/rooms/room-1/clues/A1/submissions");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("include");
    expect(JSON.parse(init.body)).toEqual({ answer: "cat" });
  });

  it("pressing Enter with incorrect status: shows error indicator and input stays active", async () => {
    const mockFetch = vi.fn().mockResolvedValue(response(200, { status: "incorrect" }));
    vi.stubGlobal("fetch", mockFetch);
    renderGrid();
    fireEvent.change(getInput(), { target: { value: "dog" } });
    fireEvent.keyDown(getInput(), { key: "Enter", code: "Enter" });
    expect(await screen.findByText("Incorrect, try again")).toBeTruthy();
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [, init] = mockFetch.mock.calls[0];
    expect(init.credentials).toBe("include");
    expect(JSON.parse(init.body)).toEqual({ answer: "dog" });
    const input = getInput();
    expect(input.disabled).toBe(false);
    expect(input.value).toBe("dog");
  });

  it("pending status: shows Waiting for Admin indicator", async () => {
    const mockFetch = vi.fn().mockResolvedValue(response(200, { status: "pending" }));
    vi.stubGlobal("fetch", mockFetch);
    renderGrid();
    fireEvent.change(getInput(), { target: { value: "cat" } });
    fireEvent.click(getSubmit());
    expect(await screen.findByText("Waiting for Admin")).toBeTruthy();
  });

  it("visual distinction: correct/incorrect/pending use different DOM indicators", async () => {
    const cases: Array<[string, string]> = [
      ["correct", "Correct!"],
      ["incorrect", "Incorrect, try again"],
      ["pending", "Waiting for Admin"],
    ];
    for (const [status, expected] of cases) {
      const mockFetch = vi.fn().mockResolvedValue(response(200, { status }));
      vi.stubGlobal("fetch", mockFetch);
      const { unmount } = renderGrid();
      fireEvent.change(getInput(), { target: { value: "cat" } });
      fireEvent.click(getSubmit());
      expect(await screen.findByText(expected)).toBeTruthy();
      const cell = screen.getByTestId("cell-0-0");
      const cls = cell.className;
      if (status === "correct") expect(cls).toContain("bg-green-400");
      if (status === "incorrect") expect(cls).toContain("bg-red-400");
      if (status === "pending") expect(cls).toContain("bg-yellow-200");
      unmount();
      cleanup();
      vi.unstubAllGlobals();
    }
  });

  it("network failure: shows an error message and grid remains usable", async () => {
    const mockFetch = vi.fn().mockRejectedValue(new Error("network down"));
    vi.stubGlobal("fetch", mockFetch);
    renderGrid();
    fireEvent.change(getInput(), { target: { value: "cat" } });
    fireEvent.click(getSubmit());
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toMatch(/network/i);
    expect(screen.getByTestId("cell-0-0")).toBeTruthy();
    expect(getInput().disabled).toBe(false);
    expect(getSubmit().disabled).toBe(false);
  });

  it("non-ok response: shows an error message without breaking grid", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(500, {})));
    renderGrid();
    fireEvent.change(getInput(), { target: { value: "cat" } });
    fireEvent.click(getSubmit());
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/failed/i);
    expect(screen.getByTestId("cell-0-0")).toBeTruthy();
  });
});
