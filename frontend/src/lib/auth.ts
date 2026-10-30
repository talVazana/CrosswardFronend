import {
  GoogleAuthProvider,
  onAuthStateChanged,
  signInWithPopup,
  signOut,
  type User,
} from "firebase/auth";
import { getFirebaseAuth } from "./firebase";

const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export function signInWithGoogle(): Promise<unknown> {
  const provider = new GoogleAuthProvider();
  return signInWithPopup(getFirebaseAuth(), provider);
}

export async function getIdToken(): Promise<string | null> {
  const user = getFirebaseAuth().currentUser;
  if (!user) {
    return null;
  }
  return user.getIdToken();
}

export function onAuthChange(callback: (user: User | null) => void) {
  return onAuthStateChanged(getFirebaseAuth(), callback);
}

export function signOutGoogle(): Promise<void> {
  return signOut(getFirebaseAuth());
}

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getIdToken();
  if (!token) {
    throw new Error("Not signed in");
  }
  return { Authorization: `Bearer ${token}` };
}

export type Profile = { email: string; nickname: string | null };

export async function getProfile(): Promise<Profile> {
  const headers = await authHeaders();
  const res = await fetch(`${base}/me/profile`, { headers });
  if (!res.ok) {
    throw new Error(`Could not load profile (status ${res.status})`);
  }
  return (await res.json()) as Profile;
}

export async function saveProfile(nickname: string): Promise<Profile> {
  const headers = await authHeaders();
  const res = await fetch(`${base}/me/profile`, {
    method: "PUT",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify({ nickname }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Could not save nickname (status ${res.status})`);
  }
  return (await res.json()) as Profile;
}
