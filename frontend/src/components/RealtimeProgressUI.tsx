"use client";
import { useState } from 'react';
import { useProjectEvents } from '../lib/useProjectEvents';

export default function RealtimeProgressUI({ projectId }: { projectId: string }) {
  const [events, setEvents] = useState<any[]>([]);
  const [sceneProgress, setSceneProgress] = useState<Record<string, number>>({});

  useProjectEvents(projectId, (evt) => {
    setEvents((prev) => [evt, ...prev].slice(0, 30));
    if (evt.scene_id && typeof evt.progress === 'number') {
      setSceneProgress((prev) => ({ ...prev, [evt.scene_id]: evt.progress }));
    }
  });

  return (
    <div className="space-y-4 rounded-2xl border border-white/10 bg-white/5 p-5">
      <h2 className="text-lg font-semibold">Realtime Progress</h2>
      <div className="space-y-3">
        {Object.entries(sceneProgress).map(([sceneId, progress]) => (
          <div key={sceneId} className="rounded-xl border border-white/10 bg-black/20 p-3">
            <div className="mb-2 flex items-center justify-between text-sm">
              <span>{sceneId}</span><span>{progress}%</span>
            </div>
            <div className="h-2 rounded-full bg-white/10"><div className="h-2 rounded-full bg-emerald-400" style={{ width: `${progress}%` }} /></div>
          </div>
        ))}
      </div>
      <div className="max-h-64 space-y-2 overflow-auto">
        {events.map((evt, i) => <pre key={i} className="rounded-xl bg-black/20 p-3 text-xs text-white/70">{JSON.stringify(evt, null, 2)}</pre>)}
      </div>
    </div>
  );
}
