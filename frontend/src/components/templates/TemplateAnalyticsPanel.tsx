"use client";
import React from "react";

export default function TemplateAnalyticsPanel({ data }: { data: any }) {
  return <pre>{JSON.stringify(data, null, 2)}</pre>;
}
