# AutoTasker

AutoTasker is a web application for turning natural-language goals into actionable task plans, confirming drafts before execution, and tracking progress through a kanban workflow and focus sessions.

The project uses `FastAPI + SQLAlchemy + LangChain` on the backend and serves a browser-based frontend from the same application.

## Highlights

- User registration and login with JWT-based authentication
- Goal analysis with AI-generated task drafts
- Multi-turn draft discussion and iterative plan adjustment
- Draft confirmation before tasks enter the execution board
- Kanban-style task management
- Pomodoro session tracking
- Progress metrics and AI-assisted review suggestions
- MySQL-ready persistence with Alembic migrations
- Support for multiple LLM providers and OpenAI-compatible endpoints

## Architecture

### Backend

- `FastAPI` application and REST API
- `SQLAlchemy 2.0` models and session management
- `Alembic` database migrations
- `LangChain` model integration
- JWT authentication and password hashing

### Frontend

- Static HTML/CSS/JavaScript UI served by FastAPI
- Draft workspace and local state helpers for plan editing
- Browser-side AI configuration for provider selection and API key entry

## Supported AI Providers

The application supports these providers through the backend integration layer:

- OpenAI
- Azure OpenAI
- DeepSeek
- Qwen / DashScope-compatible endpoint
- GLM / Zhipu
- Gemini
- Custom OpenAI-compatible endpoints

## Project Structure

```text
app/
  api.py
  config.py
  database.py
  deps.py
  main.py
  models.py
  schemas.py
  security.py
  services/
    ai.py
    integrations.py
    metrics.py
alembic/
  env.py
  versions/
scripts/
  pre_release_check.sh
static/
  app.js
  new.html
  state-helpers.js
  styles.css
tests/
tests_js/
.github/workflows/
server.py
startup.sh
requirements.txt
```

## Getting Started

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in the required values.

Minimum recommended configuration:

```env
SECRET_KEY=replace-with-a-long-random-secret
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=autotasker
```

If MySQL variables are not provided, the application falls back to a local SQLite database.

Optional server-side AI variables include:

- `OPENAI_API_KEY`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_VERSION`
- `DEEPSEEK_API_KEY`
- `QWEN_API_KEY`
- `DASHSCOPE_API_KEY`
- `ZHIPU_API_KEY`
- `GOOGLE_API_KEY`
- `GEMINI_API_KEY`

### 3. Run database migrations

```bash
python3 -m alembic upgrade head
```

### 4. Start the application

```bash
python3 server.py
```

Or run it directly with Uvicorn:

```bash
python3 -m uvicorn app.main:app --reload
```

Default local address:

- [http://127.0.0.1:8000](http://127.0.0.1:8000)

## Database Behavior

- MySQL is the preferred production database
- SQLite is available as a zero-setup fallback for local development
- When a SQLite database URL is used, the application creates the parent directory automatically
- Alembic migration files are stored under `alembic/versions`

## Main API Endpoints

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/bootstrap`
- `GET /api/integrations/status`
- `PUT /api/preferences`
- `POST /api/goals/analyze`
- `POST /api/goals/discuss`
- `POST /api/goals/confirm`
- `PATCH /api/tasks/{id}/status`
- `PATCH /api/tasks/{id}`
- `POST /api/tasks/postpone`
- `POST /api/pomodoro/start`
- `POST /api/pomodoro/finish`
- `POST /api/review/generate`
- `GET /api/health`

## Testing

Run the backend and frontend checks locally:

```bash
python3 -B -m unittest discover -s tests -v
node --check static/state-helpers.js
node --check static/app.js
node --test tests_js/*.cjs
```

A combined validation script is also available:

```bash
bash scripts/pre_release_check.sh
```

## CI

GitHub Actions workflow:

- `.github/workflows/ci.yml`

The workflow runs:

- Python unit and integration tests
- Frontend syntax checks
- Pre-release validation script

## Deployment Notes

- `startup.sh` provides a production startup entrypoint
- The application can be deployed behind `gunicorn` with `uvicorn.workers.UvicornWorker`
- Production deployments should use a strong `SECRET_KEY` and a managed MySQL instance
- Public deployments should avoid storing personal or provider credentials in the repository

## License

Add a project license here if the repository is intended for public distribution.
