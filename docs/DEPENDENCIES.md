# Dependencies

## Backend Python packages
```txt
alembic
boto3
botocore
celery[redis]
fastapi
flower
google-genai
httpx
kombu
psycopg[binary]
PyJWT
pydantic
python-docx
python-dotenv
python-multipart
redis
sqlalchemy
uvicorn[standard]
```

## Frontend npm packages
```json
{
  "name": "render-core-frontend",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "15.0.0",
    "react": "18.3.1",
    "react-dom": "18.3.1",
    "recharts": "2.12.7"
  },
  "devDependencies": {
    "typescript": "5.6.3",
    "@types/node": "22.7.4",
    "@types/react": "18.3.3",
    "@types/react-dom": "18.3.0"
  }
}
```
