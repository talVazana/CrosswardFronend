import { collection, doc, onSnapshot } from "firebase/firestore";
import { getDb } from "./firebase";
import type { Cell } from "@/utils/grid";
import type { RoomSummary } from "@/utils/rooms";

export interface RoomClue {
  clueId: string;
  number: number;
  direction: "across" | "down";
  text: string;
  answerLength: number;
}

export interface RoomPuzzle {
  puzzleId: string;
  title: string;
  width: number;
  height: number;
  cells: Cell[];
  clues: RoomClue[];
  displayClues?: RoomClue[];
}

export interface RoomPlayer {
  id: string;
  displayName: string;
  color: string;
}

export interface ScoreEntry {
  playerId: string;
  displayName: string;
  color: string;
  totalPoints: number;
}

export interface SolvedClue {
  clueId: string;
  firstSolverColor: string;
}

export interface RoomDoc {
  roomId: string;
  id?: string;
  title: string;
  status: string;
  width: number;
  height: number;
  clueCount: number;
  playerCount: number;
  puzzle?: RoomPuzzle;
  solvedClues?: SolvedClue[];
  players?: RoomPlayer[];
  scores?: ScoreEntry[];
}

export function subscribeRooms(
  onNext: (rooms: RoomSummary[]) => void,
  onError?: (error: Error) => void,
): () => void {
  const db = getDb();
  return onSnapshot(
    collection(db, "rooms"),
    (snapshot) => {
      const rooms = snapshot.docs.map(
        (snap) => snap.data() as RoomSummary,
      );
      onNext(rooms);
    },
    (error) => onError?.(error),
  );
}

export function subscribeRoom(
  roomId: string,
  onNext: (room: RoomDoc | null) => void,
  onError?: (error: Error) => void,
): () => void {
  const db = getDb();
  return onSnapshot(
    doc(db, "rooms", roomId),
    (snapshot) => {
      onNext(snapshot.exists() ? (snapshot.data() as RoomDoc) : null);
    },
    (error) => onError?.(error),
  );
}
