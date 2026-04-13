import { defineConfig } from "@playwright/test";

const frontendBaseUrl = process.env.FRONTEND_BASE_URL || "http://localhost:3000";
const backendBaseUrl = process.env.BACKEND_BASE_URL || "http://localhost:8000";
const edgeBaseUrl = process.env.EDGE_BASE_URL || "http://localhost:8080";
const shard = process.env.ARTIFACT_SHARD || "default";

export default defineConfig({
  testDir: "./tests",
  timeout: 180_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: `../artifacts/playwright/${shard}/html-report` }],
    ["json", { outputFile: `../artifacts/playwright/${shard}/results.json` }],
    ["junit", { outputFile: `../artifacts/playwright/${shard}/results.xml` }]
  ],
  outputDir: `../artifacts/playwright/${shard}/test-results`,
  use: {
    baseURL: frontendBaseUrl,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { browserName: "chromium" },
    },
  ],
  metadata: {
    frontendBaseUrl,
    backendBaseUrl,
    edgeBaseUrl,
    shard,
  },
});
