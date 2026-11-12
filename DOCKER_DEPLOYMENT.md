# Docker Deployment — InsightAgent

## Architecture

Docker Compose starts three services:
- `warehouse-init`: creates `data/warehouse.db` with `run_pipeline.py` only when the database is missing.
- `api`: FastAPI on port 8000.
- `dashboard`: Streamlit on port 8501.

All services mount the same `./data` directory. This is intentional: the API and dashboard must use the same SQLite warehouse, and generated database/CSV changes must survive container recreation.

## Prerequisites

- Docker Desktop installed and running.
- Windows users should run these commands in PowerShell from this directory.

## 1. Configure environment

```powershell
Copy-Item .env.example .env
notepad .env
```

Set `GEMINI_API_KEY` if you want live Gemini responses. Leaving the placeholder keeps the app in its built-in heuristic fallback mode. Do not commit `.env`.

## 2. Build and start

```powershell
docker compose config
docker compose up --build -d
```

First build downloads Python dependencies. The one-time initialization service reuses the checked-in SQLite warehouse if present; otherwise it runs the analytics pipeline to create it.

## 3. Verify

```powershell
docker compose ps
docker compose logs warehouse-init
docker compose logs api
docker compose logs dashboard
```

Open:
- Dashboard: http://localhost:8501
- API root: http://localhost:8000
- Swagger docs: http://localhost:8000/docs
- API health: http://localhost:8000/health

## 4. Useful operations

```powershell
# Follow logs
docker compose logs -f

# Stop containers (keeps data)
docker compose down

# Restart
docker compose up -d

# Rebuild after changing requirements or source
docker compose up --build -d

# Run the automated test suite inside the API container
docker compose exec api python -m unittest test_system.py -v
```

## 5. Data persistence

`./data:/app/data` is a bind mount. The SQLite warehouse and Power BI exports stay in the project `data` folder on the host. `docker compose down` does not delete them.

Do not use `docker compose down -v` as a routine cleanup command; named volumes are not used here, but deleting or replacing the host `data` directory can still destroy your warehouse and exports.

## Notes

- The application uses SQLite, not MySQL. No database container is needed for this repository's current implementation.
- Apache is not required: Streamlit serves the dashboard and Uvicorn serves the FastAPI API.
- `python-multipart` was added because the FastAPI batch-upload route accepts `UploadFile`.
- `httpx` was added for FastAPI's `TestClient` test dependency.
- `.venv`, Python bytecode, `.git`, and `.env` are excluded from the Docker build context.
