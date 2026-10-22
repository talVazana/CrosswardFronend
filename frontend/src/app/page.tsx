"use client";

import { useEffect, useState } from "react";

export default function Page() {
  const [text, setText] = useState("");

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
    fetch(`${base}/health`)
      .then(async (res) => {
        if (!res.ok || res.status < 200 || res.status >= 300) {
          setText("Offline");
          return;
        }
        const body = await res.json();
        if (body && body.status === "ok") {
          setText("Backend connected");
        } else {
          setText("Offline");
        }
      })
      .catch(() => {
        setText("Offline");
      });
  }, []);

  return (
    <main className="flex min-h-screen items-center justify-center">
      <p>{text}</p>
    </main>
  );
}
