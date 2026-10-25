export interface RoomSummary {
  roomId: string;
  id?: string;
  title: string;
  status: string;
  playerCount: number;
  width: number;
  height: number;
  clueCount: number;
}

export const ROOM_STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  lobby: "Lobby",
  active: "Active",
  paused: "Paused",
  finished: "Finished",
  closed: "Closed",
};

const ROOM_STATUS_STYLES: Record<string, string> = {
  active: "border-emerald-300/70 bg-emerald-100/80 text-emerald-800",
  lobby: "border-blue-300/70 bg-blue-100/80 text-blue-800",
  paused: "border-amber-300/70 bg-amber-100/80 text-amber-800",
  draft: "border-slate-300/70 bg-slate-100/80 text-slate-600",
  finished: "border-slate-300/70 bg-slate-100/80 text-slate-600",
  closed: "border-slate-300/70 bg-slate-200/80 text-slate-600",
};

export function roomStatusLabel(status: string): string {
  return ROOM_STATUS_LABELS[status] ?? status;
}

export function roomStatusTone(status: string): string {
  return ROOM_STATUS_STYLES[status] ?? ROOM_STATUS_STYLES.draft;
}

export function isRoomActive(status: string): boolean {
  return status === "active";
}
