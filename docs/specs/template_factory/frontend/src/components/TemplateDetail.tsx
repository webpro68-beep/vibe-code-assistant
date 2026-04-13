"use client";
import React from "react";

export default function TemplateDetail({ data }: { data: any }) {
  if (!data) return <div>No template selected.</div>;
  return (
    <div style={{ display: "grid", gap: 12 }}>
      <h2>{data.template?.template_name}</h2>
      <pre>{JSON.stringify(data.active_version, null, 2)}</pre>
      <pre>{JSON.stringify(data.components, null, 2)}</pre>
    </div>
  );
}
