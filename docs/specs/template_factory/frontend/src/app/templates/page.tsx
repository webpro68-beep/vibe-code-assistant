"use client";
import React from "react";
import TemplateLibrary from "../../components/TemplateLibrary";

export default function TemplatesPage() {
  return (
    <main style={{ padding: 24 }}>
      <h1>Template Library</h1>
      <TemplateLibrary items={[]} />
    </main>
  );
}
