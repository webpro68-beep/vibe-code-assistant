"use client";
import React, { useState } from "react";

export default function TemplateGenerateForm({ onSubmit }: { onSubmit?: (payload: any) => void }) {
  const [topic, setTopic] = useState("");
  const [audience, setAudience] = useState("");
  return (
    <div style={{ display: "grid", gap: 12 }}>
      <input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Topic" />
      <input value={audience} onChange={(e) => setAudience(e.target.value)} placeholder="Audience" />
      <button onClick={() => onSubmit?.({ input_slots: { topic, audience }, auto_render: true, auto_upload: false })}>
        Generate
      </button>
    </div>
  );
}
