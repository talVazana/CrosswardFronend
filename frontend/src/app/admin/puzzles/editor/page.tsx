"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import CrosswordGrid, { Clue, Puzzle } from "@/components/CrosswordGrid";

interface ParseResponse {
  puzzle?: Puzzle;
  validation_errors?: string[];
}

interface SaveErrorBody {
  detail?: string | { errors?: string[] } | unknown;
}

function formatErrors(detail: SaveErrorBody["detail"]): string[] {
  if (typeof detail === "string") return [detail];
  if (detail && typeof detail === "object") {
    const errors = (detail as { errors?: unknown }).errors;
    if (Array.isArray(errors)) return errors.map(String);
    return [JSON.stringify(detail)];
  }
  return ["Unknown server error"];
}

export default function PuzzleEditorPage() {
  const router = useRouter();

  const [puzzle, setPuzzle] = useState<Puzzle | null>(null);
  const [clueTexts, setClueTexts] = useState<Record<string, string>>({});
  const [officialAnswers, setOfficialAnswers] = useState<Record<string, string>>({});
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const loadFromFixture = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);
    setValidationErrors([]);
    try {
      const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
      const res = await fetch(`${base}/admin/puzzles/parse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ use_fixture: true }),
      });
      if (!res.ok) {
        setError(`Failed to load test fixture (status ${res.status})`);
        return;
      }
      const body = (await res.json()) as ParseResponse;
      if (!body.puzzle) {
        setError("Server returned no puzzle data");
        return;
      }
      setPuzzle(body.puzzle);
      setClueTexts(
        Object.fromEntries(body.puzzle.clues.map((clue) => [clue.clueId, clue.text])),
      );
      setOfficialAnswers({});
      setValidationErrors(body.validation_errors ?? []);
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  const savePuzzle = useCallback(async () => {
    if (!puzzle) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    setValidationErrors([]);
    try {
      const updatedClues: Clue[] = puzzle.clues.map((clue) => ({
        ...clue,
        text: clueTexts[clue.clueId] ?? clue.text,
      }));
      const payload = {
        puzzle: { ...puzzle, clues: updatedClues },
        officialAnswers: {
          puzzleId: puzzle.puzzleId,
          answers: Object.fromEntries(
            puzzle.clues.map((clue) => [
              clue.clueId,
              (officialAnswers[clue.clueId] ?? "").trim(),
            ]),
          ),
        },
      };
      const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
      const res = await fetch(`${base}/admin/puzzles`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        router.push("/admin/rooms");
        return;
      }
      const body = (await res.json().catch(() => ({}))) as SaveErrorBody;
      setValidationErrors(formatErrors(body.detail));
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setSaving(false);
    }
  }, [puzzle, clueTexts, officialAnswers, router]);

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-6 p-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold">Puzzle Editor</h1>
        <p className="text-sm text-gray-600">
          Load a puzzle, edit clues and official answers, then save.
        </p>
      </header>

      {validationErrors.length > 0 ? (
        <div
          role="alert"
          className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-700"
        >
          <p className="font-semibold">Validation errors</p>
          <ul className="list-disc pl-5">
            {validationErrors.map((message, index) => (
              <li key={index}>{message}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {error ? (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      ) : null}
      {success ? (
        <p role="status" className="text-sm text-green-700">
          {success}
        </p>
      ) : null}

      <div className="flex gap-3">
        <button
          type="button"
          onClick={() => void loadFromFixture()}
          disabled={loading}
          className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {loading ? "Loading..." : "Load from Test Fixture"}
        </button>
        <button
          type="button"
          onClick={() => void savePuzzle()}
          disabled={!puzzle || saving}
          className="rounded bg-green-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save Puzzle"}
        </button>
      </div>

      {puzzle ? (
        <>
          <section className="flex flex-col gap-2">
            <h2 className="text-lg font-medium">Grid Preview</h2>
            <CrosswordGrid roomId="editor-preview" puzzle={puzzle} />
          </section>

          <section className="flex flex-col gap-3">
            <h2 className="text-lg font-medium">Clues</h2>
            {puzzle.clues.length === 0 ? (
              <p className="text-sm text-gray-500">No clues.</p>
            ) : (
              <ul className="flex flex-col gap-3" aria-label="Clues">
                {puzzle.clues.map((clue) => (
                  <li
                    key={clue.clueId}
                    className="flex flex-col gap-2 rounded-lg border border-gray-200 p-3"
                  >
                    <span className="text-sm font-medium">
                      {clue.number} {clue.direction === "across" ? "Across" : "Down"}{" "}
                      <span className="text-gray-500">({clue.answerLength} letters)</span>
                    </span>
                    <label className="flex flex-col gap-1">
                      <span className="text-xs text-gray-500">Clue text</span>
                      <input
                        type="text"
                        aria-label={`Clue text ${clue.clueId}`}
                        value={clueTexts[clue.clueId] ?? clue.text}
                        onChange={(e) =>
                          setClueTexts((prev) => ({
                            ...prev,
                            [clue.clueId]: e.target.value,
                          }))
                        }
                        className="rounded border border-gray-300 px-3 py-2"
                      />
                    </label>
                    <label className="flex flex-col gap-1">
                      <span className="text-xs text-gray-500">Official answer</span>
                      <input
                        type="text"
                        aria-label={`Official answer ${clue.clueId}`}
                        value={officialAnswers[clue.clueId] ?? ""}
                        onChange={(e) =>
                          setOfficialAnswers((prev) => ({
                            ...prev,
                            [clue.clueId]: e.target.value,
                          }))
                        }
                        className="rounded border border-gray-300 px-3 py-2"
                        placeholder="Official answer"
                      />
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      ) : (
        <p className="text-sm text-gray-500">
          No puzzle loaded. Click &quot;Load from Test Fixture&quot; to begin.
        </p>
      )}
    </main>
  );
}
