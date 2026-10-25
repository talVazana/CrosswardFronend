export interface Participant {
  playerId?: string;
  id?: string;
  displayName: string;
  color: string;
}

interface ParticipantListProps {
  players: Participant[];
}

export default function ParticipantList({ players }: ParticipantListProps) {
  if (players.length === 0) {
    return <p className="muted text-sm">No participants yet.</p>;
  }

  return (
    <ul className="flex flex-col gap-2" aria-label="Participants">
      {players.map((player) => {
        const key = player.playerId ?? player.id ?? player.displayName;
        return (
          <li
            key={key}
            className="glass-soft flex items-center gap-3 px-3 py-2"
          >
            <span
              data-testid="participant-color"
              className="inline-block h-4 w-4 rounded-full border border-blue-900/20 opacity-70"
              style={{ backgroundColor: player.color }}
            />
            <span className="text-sm font-medium text-blue-900">{player.displayName}</span>
          </li>
        );
      })}
    </ul>
  );
}
