"use client";
import React from "react";
import TemplateDetail from "../../../components/TemplateDetail";
import TemplateGenerateForm from "../../../components/TemplateGenerateForm";
import TemplateAnalyticsPanel from "../../../components/TemplateAnalyticsPanel";

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
