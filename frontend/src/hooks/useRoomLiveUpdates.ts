"use client";

import { useEffect, useRef, useState } from "react";

export type ConnectionState = "connecting" | "connected" | "disconnected";

export interface UseRoomLiveUpdatesOptions {
  roomId: string;
  onEvent?: (event: MessageEvent) => void;
  onStateFetched?: (state: unknown) => void;
}

export interface UseRoomLiveUpdatesResult {
  connectionState: ConnectionState;
}

const BASE_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 30000;

export function useRoomLiveUpdates(
  options: UseRoomLiveUpdatesOptions,
): UseRoomLiveUpdatesResult {
  const { roomId, onEvent, onStateFetched } = options;
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("connecting");

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptRef = useRef(0);
  const onEventRef = useRef(onEvent);
  const onStateFetchedRef = useRef(onStateFetched);
  onEventRef.current = onEvent;
  onStateFetchedRef.current = onStateFetched;

  useEffect(() => {
    if (!roomId) return;

    const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

    const fetchAuthoritativeState = () => {
      fetch(`${base}/rooms/${roomId}/state`, { credentials: "include" })
        .then((res) => (res.ok ? res.json() : null))
        .then((state) => {
          if (state !== null) onStateFetchedRef.current?.(state);
        })
        .catch(() => {});
    };

    const clearReconnectTimer = () => {
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    const connect = () => {
      clearReconnectTimer();
      setConnectionState("connecting");
      const es = new EventSource(`${base}/rooms/${roomId}/events`, {
        withCredentials: true,
      });
      eventSourceRef.current = es;

      es.onopen = () => {
        reconnectAttemptRef.current = 0;
        setConnectionState("connected");
        fetchAuthoritativeState();
      };

      es.onmessage = (event: MessageEvent) => {
        onEventRef.current?.(event);
      };

      es.onerror = () => {
        es.close();
        if (eventSourceRef.current === es) {
          eventSourceRef.current = null;
        }
        setConnectionState("disconnected");
        const delay = Math.min(
          BASE_BACKOFF_MS * 2 ** reconnectAttemptRef.current,
          MAX_BACKOFF_MS,
        );
        reconnectAttemptRef.current += 1;
        reconnectTimerRef.current = setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      clearReconnectTimer();
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
      setConnectionState("disconnected");
    };
  }, [roomId]);

  return { connectionState };
}

export default useRoomLiveUpdates;
