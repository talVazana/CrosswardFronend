import { getApp, getApps, initializeApp, type FirebaseApp } from "firebase/app";
import {
  connectFirestoreEmulator,
  getFirestore,
  type Firestore,
} from "firebase/firestore";

const projectId =
  process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID ?? "demo-crossword-arena";
const emulatorHost =
  process.env.NEXT_PUBLIC_FIRESTORE_EMULATOR_HOST ?? "127.0.0.1";
const emulatorPort = Number(
  process.env.NEXT_PUBLIC_FIRESTORE_EMULATOR_PORT ?? "8080",
);

function getFirebaseApp(): FirebaseApp {
  if (getApps().length > 0) {
    return getApp();
  }
  return initializeApp({ projectId });
}

let firestoreInstance: Firestore | null = null;

export function getDb(): Firestore {
  if (firestoreInstance) {
    return firestoreInstance;
  }
  const app = getFirebaseApp();
  const db = getFirestore(app);
  connectFirestoreEmulator(db, emulatorHost, emulatorPort);
  firestoreInstance = db;
  return db;
}
