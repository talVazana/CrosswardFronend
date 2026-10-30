import { getApp, getApps, initializeApp, type FirebaseApp } from "firebase/app";
import { getAuth, connectAuthEmulator, type Auth } from "firebase/auth";
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
  return initializeApp({
    projectId,
    apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY ?? "demo-api-key",
    authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN ?? "localhost",
    appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  });
}

let firestoreInstance: Firestore | null = null;

export function getDb(): Firestore {
  if (firestoreInstance) {
    return firestoreInstance;
  }
  const app = getFirebaseApp();
  const db = getFirestore(app);
  if (process.env.NEXT_PUBLIC_FIRESTORE_EMULATOR_HOST) {
    connectFirestoreEmulator(db, emulatorHost, emulatorPort);
  }
  firestoreInstance = db;
  return db;
}

let authInstance: Auth | null = null;
let authEmulatorConnected = false;

export function getFirebaseAuth(): Auth {
  if (authInstance) {
    return authInstance;
  }
  const app = getFirebaseApp();
  const auth = getAuth(app);
  const authEmulatorHost = process.env.NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST;
  if (authEmulatorHost && !authEmulatorConnected) {
    connectAuthEmulator(auth, authEmulatorHost);
    authEmulatorConnected = true;
  }
  authInstance = auth;
  return auth;
}
