# Local development

## 1. Bootstrap
```bash
cp backend/.env.example backend/.env.dev
cp frontend/.env.local.example frontend/.env.local
```

## 2. Boot the stack
```bash
docker compose up --build
```

## 3. Run migrations manually if needed
```bash
docker compose exec api alembic upgrade head
```

## 4. Open services
- Frontend: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/healthz`
- Flower: `http://localhost:5555`
- MinIO: `http://localhost:9001`

## 5. Smoke test flow
- Upload a `.txt` or `.docx` file on `/script-upload`
- Validate and confirm preview
- Build render payloads for provider
- Create render job
- Poll `/api/v1/render/jobs/{job_id}` until terminal
