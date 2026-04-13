"use client";
import React, { useState } from "react";

export default function TemplateBatchRunner({ onSubmit }: { onSubmit?: (payload: any) => void }) {
  const [itemsText, setItemsText] = useState("topic 1\ntopic 2\ntopic 3");
  return (
    <div style={{ display: "grid", gap: 12 }}>
      <textarea rows={8} value={itemsText} onChange={(e) => setItemsText(e.target.value)} />
      <button onClick={() => onSubmit?.({
        items: itemsText.split("\n").filter(Boolean).map((topic) => ({ topic })),
        auto_render: true,
        auto_upload: true,
      })}>
        Run Batch
      </button>
    </div>
  );
}
