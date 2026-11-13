FROM node:22-bookworm-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm test && npm run build

FROM python:3.12-slim-bookworm AS checks
WORKDIR /app
COPY requirements*.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY backend/ ./backend/
COPY tests/ ./tests/
RUN python -m unittest discover -s tests -v && touch /app/quality-passed

FROM python:3.12-slim-bookworm
WORKDIR /app
COPY --from=checks /app/quality-passed ./quality-passed
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY --from=frontend /app/frontend/dist ./frontend/dist
RUN useradd --system app
USER app
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port \"${PORT:-8000}\""]
