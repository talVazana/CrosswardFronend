import { test, expect } from "@playwright/test";

test("infrastructure: root page loads and returns 200", async ({ page }) => {
  const response = await page.goto("/");
  expect(response, "navigation should return a response").not.toBeNull();
  expect(response?.status(), "root should respond with HTTP 200").toBe(200);
  await expect(page.locator("body")).toBeVisible();
});
