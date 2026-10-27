import { test, expect, request, type BrowserContext, type Page } from "@playwright/test";
import * as path from "path";
import * as fs from "fs";

const ROOM_ID = "E2E-Room-1";
const BACKEND_URL = process.env.E2E_BACKEND_URL ?? "http://localhost:8001";

const DANA = { name: "Dana", color: "#DC2626" };
const AMIR = { name: "Amir", color: "#0D9488" };
const LEE = { name: "Lee", color: "#CA8A04" };

const ACROSS_CLUE = { clueId: "A7", number: 7, startCell: [3, 4] as const, answer: "WORLD" };
const DOWN_CLUE = { clueId: "D1", number: 1, startCell: [0, 4] as const, answer: "GO" };

function loadFixtureJson(relPath: string) {
  return JSON.parse(fs.readFileSync(path.resolve(__dirname, "..", "..", relPath), "utf-8"));
}

async function resetRoom() {
  const puzzle = loadFixtureJson("fixtures/puzzles/valid_sample_puzzle.json");
  const answers = loadFixtureJson("fixtures/puzzles/sample_official_answers.json");
  const api = await request.newContext({ baseURL: BACKEND_URL });
  try {
    const resetRes = await api.post("/test/reset");
    expect(resetRes.ok(), `reset should succeed: ${resetRes.status()}`).toBeTruthy();
    const res = await api.post("/e2e/seed", {
      data: { roomId: ROOM_ID, title: "E2E Room", puzzle, officialAnswers: answers, status: "active" },
    });
    expect(res.ok(), `reset seed should succeed: ${res.status()}`).toBeTruthy();
    const body = (await res.json()) as { adminSessionToken?: string };
    if (body.adminSessionToken) process.env.ADMIN_SESSION_TOKEN = body.adminSessionToken;
  } finally {
    await api.dispose();
  }
}

test.beforeEach(async () => {
  await resetRoom();
});

async function joinRoom(context: BrowserContext, displayName: string): Promise<Page> {
  const page = await context.newPage();
  await page.goto(`/rooms/${ROOM_ID}/join`);
  await page.getByRole("textbox", { name: "Display Name" }).fill(displayName);
  await page.getByRole("button", { name: "Join" }).click();
  await page.waitForURL(`**/rooms/${ROOM_ID}`);
  await expect(page.getByRole("heading", { name: "E2E Room" })).toBeVisible();
  return page;
}

async function selectClue(page: Page, startCell: readonly [number, number], direction: "across" | "down") {
  const [row, col] = startCell;
  await page.getByTestId(`cell-${row}-${col}`).click();
  if (direction === "down") {
    const active = page.getByRole("heading", { level: 2, name: /Across|Down/ });
    if ((await active.textContent())?.includes("Across")) {
      await page.getByTestId(`cell-${row}-${col}`).click();
    }
  }
}

async function activeClueHeading(page: Page): Promise<string> {
  return (await page.getByRole("heading", { level: 2, name: /Across|Down/ }).textContent()) ?? "";
}

async function submitAnswer(page: Page, answer: string) {
  await page.locator('[aria-label="Crossword grid"]').focus();
  await page.keyboard.type(answer);
  await page.getByRole("button", { name: "Submit" }).click();
}

function scoreboardRow(page: Page, name: string) {
  return page.locator("ul[aria-label='Scoreboard'] li").filter({ hasText: name });
}

async function expectScore(page: Page, name: string, score: number) {
  await expect(scoreboardRow(page, name).getByTestId("score-value")).toHaveText(String(score));
}

async function loginAsAdmin(context: BrowserContext): Promise<Page> {
  const adminToken = process.env.ADMIN_SESSION_TOKEN;
  expect(adminToken, "admin session token from global.setup should be present").toBeTruthy();
  await context.addCookies([
    { name: "Session-Token", value: adminToken as string, url: BACKEND_URL },
  ]);
  const page = await context.newPage();
  await page.goto(`/admin/rooms/${ROOM_ID}`);
  await expect(page.getByRole("heading", { name: "E2E Room" })).toBeVisible();
  return page;
}

test.describe("E2E-005 Gameplay Loop (scoring)", () => {
  test("Dana scores 2 points first, Amir scores 1 point second in the DOM scoreboard, clue keeps Dana's color", async ({ browser }) => {
    const danaContext = await browser.newContext();
    const amirContext = await browser.newContext();
    try {
      const dana = await joinRoom(danaContext, DANA.name);
      const amir = await joinRoom(amirContext, AMIR.name);

      await expectScore(dana, DANA.name, 0);
      await expectScore(dana, AMIR.name, 0);

      await selectClue(dana, ACROSS_CLUE.startCell, "across");
      expect(await activeClueHeading(dana)).toContain(`${ACROSS_CLUE.number} Across`);
      await submitAnswer(dana, ACROSS_CLUE.answer);
      await expect(dana.getByText("Correct!")).toBeVisible();

      await dana.reload();
      await expect(dana.getByRole("heading", { name: "E2E Room" })).toBeVisible();
      await expectScore(dana, DANA.name, 2);

      const [r, c] = ACROSS_CLUE.startCell;
      await expect(dana.getByTestId(`cell-${r}-${c}`)).toHaveCSS(
        "box-shadow",
        /rgba\(220, 38, 38/,
      );

      await selectClue(amir, ACROSS_CLUE.startCell, "across");
      await submitAnswer(amir, ACROSS_CLUE.answer);
      await expect(amir.getByText("Correct!")).toBeVisible();

      await amir.reload();
      await expect(amir.getByRole("heading", { name: "E2E Room" })).toBeVisible();
      await expectScore(amir, AMIR.name, 1);
      await expectScore(amir, DANA.name, 2);

      await expect(amir.getByTestId(`cell-${r}-${c}`)).toHaveCSS(
        "box-shadow",
        /rgba\(220, 38, 38/,
      );
    } finally {
      await danaContext.close();
      await amirContext.close();
    }
  });
});

test.describe("E2E-006 Personal Reveal", () => {
  test("Lee's reveal shows letters and disables submit for Lee only; Dana unaffected", async ({ browser }) => {
    const leeContext = await browser.newContext();
    const danaContext = await browser.newContext();
    try {
      const lee = await joinRoom(leeContext, LEE.name);
      const dana = await joinRoom(danaContext, DANA.name);

      await selectClue(lee, DOWN_CLUE.startCell, "down");
      expect(await activeClueHeading(lee)).toContain(`${DOWN_CLUE.number} Down`);

      lee.on("dialog", (dialog) => dialog.accept());
      await lee.getByRole("button", { name: "Reveal Answer" }).click();

      const [r, c] = DOWN_CLUE.startCell;
      await expect(lee.getByTestId(`cell-${r}-${c}`)).toContainText(DOWN_CLUE.answer[0]);
      await expect(lee.getByTestId(`cell-${r + 1}-${c}`)).toContainText(DOWN_CLUE.answer[1]);
      await expect(lee.getByRole("button", { name: "Submit" })).toBeDisabled();

      await selectClue(dana, DOWN_CLUE.startCell, "down");
      await expect(dana.getByTestId(`cell-${r}-${c}`)).not.toContainText(DOWN_CLUE.answer[0]);
      await expect(dana.getByTestId(`cell-${r + 1}-${c}`)).not.toContainText(DOWN_CLUE.answer[1]);
      await dana.locator('[aria-label="Crossword grid"]').focus();
      await dana.keyboard.type("G");
      await expect(dana.getByTestId(`cell-${r}-${c}`)).toContainText("G");
      await dana.keyboard.type("O");
      await expect(dana.getByTestId(`cell-${r + 1}-${c}`)).toContainText("O");
      await expect(dana.getByRole("button", { name: "Submit" })).toBeEnabled();
    } finally {
      await leeContext.close();
      await danaContext.close();
    }
  });
});

test.describe("E2E-007 Room Lifecycle (pause/resume)", () => {
  test("Admin pauses the room: Dana cannot submit; Admin resumes: Dana can submit", async ({ browser }) => {
    const adminContext = await browser.newContext();
    const danaContext = await browser.newContext();
    try {
      const admin = await loginAsAdmin(adminContext);
      const dana = await joinRoom(danaContext, DANA.name);

      await admin.getByRole("button", { name: "Pause" }).click();
      await expect(admin.getByText("Paused")).toBeVisible();
      await expect(dana.getByText("Paused")).toBeVisible();

      await selectClue(dana, ACROSS_CLUE.startCell, "across");
      await expect(dana.getByRole("button", { name: "Submit" })).toBeDisabled();
      await dana.locator('[aria-label="Crossword grid"]').focus();
      await dana.keyboard.type("W");
      const [pr, pc] = ACROSS_CLUE.startCell;
      await expect(dana.getByTestId(`cell-${pr}-${pc}`)).not.toContainText("W");

      const cookies = await danaContext.cookies(BACKEND_URL);
      const session = cookies.find((ck) => ck.name === "Session-Token");
      expect(session).toBeTruthy();
      const api = await request.newContext({ baseURL: BACKEND_URL });
      try {
        const res = await api.post(`/rooms/${ROOM_ID}/clues/${ACROSS_CLUE.clueId}/submissions`, {
          headers: { "Content-Type": "application/json", Cookie: `Session-Token=${session!.value}` },
          data: { answer: ACROSS_CLUE.answer },
        });
        expect(res.status()).toBe(400);
      } finally {
        await api.dispose();
      }

      await admin.getByRole("button", { name: "Resume" }).click();
      await expect(admin.getByText("Active")).toBeVisible();

      await dana.reload();
      await expect(dana.getByRole("heading", { name: "E2E Room" })).toBeVisible();
      await selectClue(dana, ACROSS_CLUE.startCell, "across");
      await submitAnswer(dana, ACROSS_CLUE.answer);
      await expect(dana.getByText("Correct!")).toBeVisible();
    } finally {
      await adminContext.close();
      await danaContext.close();
    }
  });
});
