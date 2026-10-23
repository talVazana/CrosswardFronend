import { defineConfig, devices } from "@playwright/test";
import * as path from "path";

const repoRoot = path.resolve(__dirname, "..");
const backendDir = path.join(repoRoot, "backend");
const frontendDir = __dirname;

const BACKEND_PORT = 8001;
const FRONTEND_PORT = 3000;
const backendUrl = `http://127.0.0.1:${BACKEND_PORT}`;

const pythonCmd = process.platform === "win32" ? "py -3" : "python3";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    trace: "retain-on-failure",
  },
  expect: {
    timeout: 10_000,
  },
  globalSetup: require.resolve("./e2e/global.setup.ts"),
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        contextOptions: {
          ignoreHTTPSErrors: true,
        },
      },
    },
  ],
  webServer: [
    {
      name: "backend",
      command: `${pythonCmd} -m uvicorn app.main:app --host 127.0.0.1 --port ${BACKEND_PORT}`,
      cwd: backendDir,
      url: `${backendUrl}/health`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      name: "frontend",
      command: `npm run dev -- --port ${FRONTEND_PORT}`,
      cwd: frontendDir,
      url: `http://localhost:${FRONTEND_PORT}`,
      reuseExistingServer: false,
      timeout: 60_000,
      env: {
        NEXT_PUBLIC_BACKEND_URL: backendUrl,
      },
    },
  ],
});
