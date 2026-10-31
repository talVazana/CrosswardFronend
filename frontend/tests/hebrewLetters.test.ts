import { describe, expect, it } from "vitest";
import { toRegularHebrewLetters } from "../src/utils/crossword";

describe("toRegularHebrewLetters", () => {
  it("converts all Hebrew final letters to their regular forms", () => {
    expect(toRegularHebrewLetters("ךםןףץ")).toBe("כמנפצ");
  });

  it("leaves regular letters and non-Hebrew characters unchanged", () => {
    expect(toRegularHebrewLetters("אבגדה 123")).toBe("אבגדה 123");
  });

  it("normalizes a word ending in a final letter", () => {
    expect(toRegularHebrewLetters("שלום")).toBe("שלומ");
  });
});
