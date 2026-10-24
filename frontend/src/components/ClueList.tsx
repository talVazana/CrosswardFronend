import type { Clue } from "./CrosswordGrid";

interface ClueListProps {
  clues: Clue[];
  activeClueId?: string | null;
  solvedClueIds?: ReadonlySet<string>;
  onSelectClue?: (clue: Clue) => void;
}

export default function ClueList({
  clues,
  activeClueId = null,
  solvedClueIds,
  onSelectClue,
}: ClueListProps) {
  if (clues.length === 0) {
    return <p className="text-sm text-gray-500">No clues.</p>;
  }

  return (
    <ul className="flex flex-col gap-1" aria-label="Clues">
      {clues.map((clue) => {
        const isActive = clue.clueId === activeClueId;
        const isSolved = solvedClueIds?.has(clue.clueId) ?? false;
        return (
          <li
            key={clue.clueId}
            aria-current={isActive ? "true" : undefined}
            aria-label={`Clue ${clue.number} ${clue.direction === "across" ? "Across" : "Down"}${isSolved ? ", solved" : ""}`}
            className={`rounded border px-3 py-2 text-sm ${
              isActive
                ? "border-blue-500 bg-blue-50 font-medium"
                : "border-gray-200"
            } ${isSolved ? "text-gray-500 line-through" : ""}`}
          >
            {onSelectClue ? (
              <button
                type="button"
                onClick={() => onSelectClue(clue)}
                aria-current={isActive ? "true" : undefined}
                className="w-full text-left"
              >
                <span className="font-medium">
                  {clue.number} {clue.direction === "across" ? "Across" : "Down"}
                </span>{" "}
                <span>{clue.text}</span>
              </button>
            ) : (
              <>
                <span className="font-medium">
                  {clue.number} {clue.direction === "across" ? "Across" : "Down"}
                </span>{" "}
                <span>{clue.text}</span>
              </>
            )}
          </li>
        );
      })}
    </ul>
  );
}
