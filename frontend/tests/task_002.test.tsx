import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import Page from "../src/app/page";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("TASK-002 Page backend connectivity", () => {
  it("fetch resolves 200 {status: ok} -> renders Backend connected", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ status: "ok" }),
      })
    );
    render(<Page />);
    expect(await screen.findByText("Backend connected")).toBeTruthy();
  });

  it("fetch rejects with Error(network) -> renders Offline", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("network"))
    );
    render(<Page />);
    expect(await screen.findByText("Offline")).toBeTruthy();
  });

  it("fetch resolves non-2xx 500 -> renders Offline", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500 })
    );
    render(<Page />);
    expect(await screen.findByText("Offline")).toBeTruthy();
  });

  it("NEXT_PUBLIC_BACKEND_URL unset -> fetch called with http://localhost:8000 prefix", async () => {
    delete process.env.NEXT_PUBLIC_BACKEND_URL;
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: "ok" }),
    });
    vi.stubGlobal("fetch", mockFetch);
    render(<Page />);
    await screen.findByText("Backend connected");
    expect(mockFetch).toHaveBeenCalled();
    const url = String(mockFetch.mock.calls[0][0]);
    expect(url.startsWith("http://localhost:8000")).toBe(true);
  });
});

describe("TASK-002 project files", () => {
  it(".env.example contains the exact backend URL line", () => {
    const content = readFileSync(resolve(__dirname, "../.env.example"), "utf8");
    expect(content.trim()).toBe("NEXT_PUBLIC_BACKEND_URL=http://localhost:8000");
  });

  it("package.json lists required dependencies and devDependencies", () => {
    const pkg = JSON.parse(
      readFileSync(resolve(__dirname, "../package.json"), "utf8")
    );
    for (const dep of ["next", "react", "react-dom"]) {
      expect(pkg.dependencies?.[dep], `dependency ${dep}`).toBeTruthy();
    }
    for (const dep of [
      "typescript",
      "@types/react",
      "@types/react-dom",
      "@types/node",
      "tailwindcss",
      "postcss",
      "autoprefixer",
      "vitest",
      "jsdom",
      "@testing-library/react",
      "@vitejs/plugin-react",
    ]) {
      expect(pkg.devDependencies?.[dep], `devDependency ${dep}`).toBeTruthy();
    }
  });
});
