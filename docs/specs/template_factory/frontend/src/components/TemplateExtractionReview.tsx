"use client";
import React from "react";

export default function TemplateExtractionReview({ extraction }: { extraction: any }) {
  return (
    <div style={{ display: "grid", gap: 12 }}>
      <h3>Extraction Review</h3>
      <pre>{JSON.stringify(extraction, null, 2)}</pre>
    </div>
  );
}
