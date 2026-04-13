FROM mcr.microsoft.com/playwright:v1.52.0-jammy
WORKDIR /workspace/e2e
COPY e2e/package*.json ./
RUN npm install
COPY e2e ./
CMD ["npx", "playwright", "test"]
