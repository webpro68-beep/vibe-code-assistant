"use client";
import React from "react";
import TemplateDetail from "../@/src/components/templates/TemplateDetail";
import TemplateGenerateForm from "../@/src/components/templates/TemplateGenerateForm";
import TemplateAnalyticsPanel from "../@/src/components/templates/TemplateAnalyticsPanel";

export default function TemplateDetailPage() {
  return (
    <main style={{ padding: 24, display: "grid", gap: 16 }}>
      <h1>Template Detail</h1>
      <TemplateDetail data={null} />
      <TemplateGenerateForm />
      <TemplateAnalyticsPanel data={{}} />
    </main>
  );
}
