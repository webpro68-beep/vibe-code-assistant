"use client";
import React from "react";

export default function TemplateLibrary({ items = [] }: { items?: any[] }) {
  return (
    <div style={{ display: "grid", gap: 12 }}>
      {items.map((item) => (
        <div key={item.id} style={{ border: "1px solid #ddd", borderRadius: 12, padding: 16 }}>
          <div style={{ fontWeight: 700 }}>{item.template_name}</div>
          <div>Status: {item.status}</div>
          <div>Reusability: {item.reusability_score ?? "-"}</div>
        </div>
      ))}
    </div>
  );
}
