import type { Clue } from "./CrosswordGrid";

interface ClueListProps {
  clues: Clue[];
  activeClueId?: string | null;
  solvedClueIds?: ReadonlySet<string>;
  playerSolvedClueIds?: ReadonlySet<string>;
  playerRevealedClueIds?: ReadonlySet<string>;
  onSelectClue?: (clue: Clue) => void;
}

export default function ClueList({
  clues,
  activeClueId = null,
  solvedClueIds,
  playerSolvedClueIds,
  playerRevealedClueIds,
  onSelectClue,
}: ClueListProps) {
  if (clues.length === 0) {
    return <p className="muted text-sm">No clues.</p>;
  }

  const columns = [
    { title: "Across", direction: "across" as const },
    { title: "Down", direction: "down" as const },
  ];

  return (
    <div className="grid grid-cols-1 items-start gap-5 sm:grid-cols-2">
      {columns.map((column) => {
        const columnClues = clues.filter(
          (clue) => clue.direction === column.direction,
        );
        return (
          <section key={column.direction} className="min-w-0">
            <h3 className="mb-2 border-b border-blue-200/60 pb-1 text-sm font-semibold uppercase tracking-wide text-blue-800">
              {column.title}
            </h3>
            {columnClues.length === 0 ? (
              <p className="muted text-sm">No clues.</p>
            ) : (
              <ul
                className="flex flex-col gap-1"
                aria-label={`${column.title} clues`}
              >
                {columnClues.map((clue) => {
                  const isActive = clue.clueId === activeClueId;
                  const isDone =
                    (solvedClueIds?.has(clue.clueId) ?? false) ||
                    (playerSolvedClueIds?.has(clue.clueId) ?? false) ||
                    (playerRevealedClueIds?.has(clue.clueId) ?? false);
                  return (
                    <li
                      key={clue.clueId}
                      aria-current={isActive ? "true" : undefined}
                      aria-label={`Clue ${clue.number} ${column.title}${isDone ? ", completed" : ""}`}
                      className={`glass-soft flex min-w-0 items-start gap-2 px-3 py-2 text-sm ${
                        isActive
                          ? "border-blue-400 bg-blue-100/60 font-medium text-blue-900"
                          : "text-blue-900/80"
                      } ${isDone ? "text-blue-900/40" : ""}`}
                    >
                      <input
                        type="checkbox"
                        checked={isDone}
                        disabled
                        readOnly
                        aria-label={`Clue ${clue.number} ${column.title} ${isDone ? "completed" : "not completed"}`}
                        className="mt-0.5 h-4 w-4 shrink-0 rounded border-blue-300 accent-emerald-500"
                      />
                      {onSelectClue ? (
                        <button
                          type="button"
                          onClick={() => onSelectClue(clue)}
                          aria-current={isActive ? "true" : undefined}
                          className="min-w-0 flex-1 whitespace-normal break-words text-start"
                        >
                          <span className="font-medium">{clue.number}.</span>{" "}
                          <span>{clue.text}</span>
                        </button>
                      ) : (
                        <span className="min-w-0 flex-1 whitespace-normal break-words text-start">
                          <span className="font-medium">{clue.number}.</span>{" "}
                          <span>{clue.text}</span>
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        );
      })}
    </div>
  );
}
