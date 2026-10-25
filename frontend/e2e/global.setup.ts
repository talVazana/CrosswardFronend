import { request, FullConfig, APIRequestContext } from "@playwright/test";
import * as path from "path";
import * as fs from "fs";

const BACKEND_URL = process.env.E2E_BACKEND_URL ?? "http://localhost:8001";
const ROOM_ID = "E2E-Room-1";
const PUZZLE_ID = "e2e-puzzle-001";

async function waitForBackend(backend: APIRequestContext) {
  for (let i = 0; i < 60; i++) {
    try {
      const res = await backend.get("/health");
      if (res.ok()) return;
    } catch {}
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error(`Backend at ${BACKEND_URL} did not become healthy`);
}

function loadFixtureJson(relPath: string) {
  const full = path.resolve(__dirname, "..", "..", relPath);
  return JSON.parse(fs.readFileSync(full, "utf-8"));
}

export default async function globalSetup(_config: FullConfig) {
  const backend = await request.newContext({ baseURL: BACKEND_URL });
  try {
    await waitForBackend(backend);

    const puzzle = loadFixtureJson("fixtures/puzzles/valid_sample_puzzle.json");
    puzzle.puzzleId = PUZZLE_ID;
    if (puzzle.width !== 5 || puzzle.height !== 5) {
      throw new Error(
        `Fixture puzzle must be 5x5, got ${puzzle.width}x${puzzle.height}`,
      );
    }

    const answers = loadFixtureJson("fixtures/puzzles/sample_official_answers.json");
    answers.puzzleId = PUZZLE_ID;

    const seedRes = await backend.post("/e2e/seed", {
      data: {
        roomId: ROOM_ID,
        title: "E2E Room",
        puzzle,
        officialAnswers: answers,
        status: "active",
      },
    });
  if (!seedRes.ok()) {
    throw new Error(`Failed to seed room: ${seedRes.status()} ${await seedRes.text()}`);
  }
  const seedBody = (await seedRes.json()) as { adminSessionToken?: string };
  if (seedBody.adminSessionToken) {
    process.env.ADMIN_SESSION_TOKEN = seedBody.adminSessionToken;
  }

    const stateRes = await backend.get(`/rooms/${ROOM_ID}/state`);
    if (!stateRes.ok()) {
      throw new Error(`Room ${ROOM_ID} not reachable after seed: ${stateRes.status()}`);
    }
    const state = await stateRes.json();
    if (state.status !== "active") {
      throw new Error(`Room ${ROOM_ID} is not active after seed (status: ${state.status})`);
    }
  } finally {
    await backend.dispose();
  }
}
