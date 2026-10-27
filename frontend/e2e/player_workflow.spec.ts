import { test, expect, request, type BrowserContext, type Page } from "@playwright/test";
import * as path from "path";
import * as fs from "fs";

const ROOM_ID = "E2E-Room-1";
const BACKEND_URL = process.env.E2E_BACKEND_URL ?? "http://localhost:8001";

const DANA = { name: "Dana", color: "#DC2626" };
const AMIR = { name: "Amir", color: "#0D9488" };

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

// RTL clue: A7 starts at (3,4) and fills right-to-left: (3,4) (3,3) (3,2) (3,1) (3,0).
// Black cell at (1,1) blocks ArrowUp from row 2.
const ACROSS_CLUE = { clueId: "A7", number: 7, startCell: [3, 4] as const, answer: "WORLD" };

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

function participantRow(page: Page, name: string) {
  return page.locator("ul[aria-label='Scoreboard'] li").filter({ hasText: name });
}

// Numbered start cell renders "<number><letter>" in one button; assert only the draft letter.
function expectDraftLetter(page: Page, row: number, col: number, letter: string, isNumberedCell: boolean) {
  const cell = page.getByTestId(`cell-${row}-${col}`);
  return isNumberedCell
    ? expect(cell).toHaveText(new RegExp(`^${ACROSS_CLUE.number}${letter}$`))
    : expect(cell).toHaveText(letter);
}

async function expectEmptyCell(page: Page, row: number, col: number, isNumberedCell: boolean) {
  const cell = page.getByTestId(`cell-${row}-${col}`);
  if (isNumberedCell) {
    await expect(cell).toHaveText(String(ACROSS_CLUE.number));
  } else {
    await expect(cell).toHaveText("");
  }
}

test.describe("E2E-002 / E2E-009 Join, isolate and reconnect", () => {
  test("Dana and Amir join the room; names and colors appear in the lobby; refreshing Dana does not duplicate her", async ({ browser }) => {
    const danaContext = await browser.newContext();
    const amirContext = await browser.newContext();
    try {
      const dana = await joinRoom(danaContext, DANA.name);
      const amir = await joinRoom(amirContext, AMIR.name);

      await expect(participantRow(dana, DANA.name)).toHaveCount(1);
      await expect(participantRow(dana, AMIR.name)).toHaveCount(1);
      await expect(participantRow(amir, DANA.name)).toHaveCount(1);
      await expect(participantRow(amir, AMIR.name)).toHaveCount(1);

      const danaRow = participantRow(amir, DANA.name);
      await expect(danaRow.getByTestId("score-color")).toHaveCSS(
        "background-color",
        "rgb(220, 38, 38)",
      );
      const amirRow = participantRow(dana, AMIR.name);
      await expect(amirRow.getByTestId("score-color")).toHaveCSS(
        "background-color",
        "rgb(13, 148, 136)",
      );

      await dana.reload();
      await expect(dana.getByRole("heading", { name: "E2E Room" })).toBeVisible();
      await expect(participantRow(dana, DANA.name)).toHaveCount(1);
      await expect(participantRow(dana, AMIR.name)).toHaveCount(1);
      await expect(participantRow(amir, DANA.name)).toHaveCount(1);
      await expect(participantRow(amir, AMIR.name)).toHaveCount(1);
    } finally {
      await danaContext.close();
      await amirContext.close();
    }
  });
});

test.describe("E2E-003 Interact and navigate", () => {
  test("typing letters into the RTL across clue advances the cursor right-to-left, Backspace retreats, and an arrow toward a black cell stops the cursor", async ({ browser }) => {
    const danaContext = await browser.newContext();
    try {
      const dana = await joinRoom(danaContext, DANA.name);      const [r, c] = ACROSS_CLUE.startCell;

      await selectClue(dana, ACROSS_CLUE.startCell, "across");
      await expect(dana.getByRole("heading", { level: 2, name: /Across|Down/ })).toHaveText(
        `${ACROSS_CLUE.number} Across`,
      );

      await dana.getByTestId(`cell-${r}-${c}`).click();
      await expect(dana.getByTestId(`cell-${r}-${c}`)).toHaveClass(/bg-blue-200/);

      await dana.locator('[aria-label="Crossword grid"]').focus();
      await dana.keyboard.type("WOR");

      await expectDraftLetter(dana, r, c, "W", true);
      await expect(dana.getByTestId(`cell-${r}-${c - 1}`)).toHaveText("O");
      await expect(dana.getByTestId(`cell-${r}-${c - 2}`)).toHaveText("R");
      await expect(dana.getByTestId(`cell-${r}-${c - 2}`)).toHaveClass(/bg-blue-200/);
      await expect(dana.getByTestId(`cell-${r}-${c}`)).not.toHaveClass(/bg-blue-200/);

      await dana.keyboard.press("Backspace");
      await expectEmptyCell(dana, r, c - 2, false);
      await expect(dana.getByTestId(`cell-${r}-${c - 1}`)).toHaveClass(/bg-blue-200/);

      // Arrow toward a black cell must stop; arrow toward a white cell must move.
      await dana.getByTestId("cell-3-3").click();
      await expect(dana.getByTestId("cell-3-3")).toHaveClass(/bg-blue-200/);
      await dana.keyboard.press("ArrowDown");
      await expect(dana.getByTestId("cell-3-3")).toHaveClass(/bg-blue-200/);
      await expect(dana.getByTestId("cell-4-3")).toHaveClass(/bg-blue-400/);
      await dana.keyboard.press("ArrowLeft");
      await expect(dana.getByTestId("cell-3-2")).toHaveClass(/bg-blue-200/);
      await dana.keyboard.press("ArrowRight");
      await expect(dana.getByTestId("cell-3-3")).toHaveClass(/bg-blue-200/);
    } finally {
      await danaContext.close();
    }
  });
});

test.describe("E2E-004 Draft privacy", () => {
  test("Dana types HELLO into a clue; Amir's grid in a separate context does not contain HELLO", async ({ browser }) => {
    const danaContext = await browser.newContext();
    const amirContext = await browser.newContext();
    try {
      const dana = await joinRoom(danaContext, DANA.name);      const amir = await joinRoom(amirContext, AMIR.name);

      await selectClue(dana, ACROSS_CLUE.startCell, "across");
      await expect(dana.getByRole("heading", { level: 2, name: /Across|Down/ })).toHaveText(
        `${ACROSS_CLUE.number} Across`,
      );
      const [r, c] = ACROSS_CLUE.startCell;
      await dana.locator('[aria-label="Crossword grid"]').focus();
      await dana.keyboard.type("HELLO");

      await expectDraftLetter(dana, r, c, "H", true);
      await expect(dana.getByTestId(`cell-${r}-${c - 1}`)).toHaveText("E");
      await expect(dana.getByTestId(`cell-${r}-${c - 2}`)).toHaveText("L");
      await expect(dana.getByTestId(`cell-${r}-${c - 3}`)).toHaveText("L");
      await expect(dana.getByTestId(`cell-${r}-${c - 4}`)).toHaveText("O");

      await selectClue(amir, ACROSS_CLUE.startCell, "across");
      await expect(amir.getByRole("heading", { level: 2, name: /Across|Down/ })).toHaveText(
        `${ACROSS_CLUE.number} Across`,
      );
      for (let i = 0; i < ACROSS_CLUE.answer.length; i++) {
        await expectEmptyCell(amir, r, c - i, i === 0);
      }
      await expect(amir.locator("body")).not.toContainText("HELLO");

      await amir.reload();
      await expect(amir.getByRole("heading", { name: "E2E Room" })).toBeVisible();
      await selectClue(amir, ACROSS_CLUE.startCell, "across");
      for (let i = 0; i < ACROSS_CLUE.answer.length; i++) {
        await expectEmptyCell(amir, r, c - i, i === 0);
      }
      await expect(amir.locator("body")).not.toContainText("HELLO");
    } finally {
      await danaContext.close();
      await amirContext.close();
    }
  });
});
