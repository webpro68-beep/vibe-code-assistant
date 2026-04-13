"use client";

import { useEffect } from "react";

export function useProjectEvents(projectId: string, onEvent: (event: any) => void) {
  useEffect(() => {
    if (!projectId) return;

    const base = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") || "http://localhost:8000";
    const url = `${base}/api/v1/projects/${projectId}/events/stream`;
    const es = new EventSource(url);

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onEvent(data);
      } catch {}
    };

    es.onerror = () => {
      console.warn("SSE disconnected, retrying...");
    };

    return () => es.close();
  }, [projectId, onEvent]);
}
