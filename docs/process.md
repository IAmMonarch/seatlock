# Building SeatLock From Scratch

A step-by-step guide to building a production-style backend with **Python, FastAPI, Postgres and Docker**.

SeatLock is an event ticketing and seat reservation API. The hard problem it solves: many people try to book the same seat at the same moment, and nobody gets double-booked.

Each part follows the same pattern:

1. **The idea**: the concept, explained simply
2. **Do it**: the exact steps and code
3. **You should see**: how to know it worked
4. **Common mistakes**: what usually goes wrong, and the fix

Read the concepts. Don't just copy commands. If you understand *why* a step exists, you can fix it when it breaks.

> This is a living guide. It grows as the project grows. See [Progress](#progress) and [Changelog](#changelog) at the bottom.

---

## Contents

- [Part 0: Tools](#part-0-tools)
- [Part 1: Create the project](#part-1-create-the-project)
- [Part 2: Your first endpoint](#part-2-your-first-endpoint)
- [Part 3: Docker](#part-3-docker)
- [Part 4: Docker Compose](#part-4-docker-compose)
- [Part 5: Settings from environment variables](#part-5-settings-from-environment-variables)
- [Part 6: Database layer and Alembic](#part-6-database-layer-and-alembic)
- [Part 7: Code quality: Ruff, mypy and pre-commit](#part-7-code-quality-ruff-mypy-and-pre-commit)
- [Daily commands](#daily-commands)
- [Troubleshooting](#troubleshooting)
- [Progress](#progress)
- [Changelog](#changelog)

---

## Part 0: Tools

### The idea

You need four tools before writing any code:

| Tool | What it's for |
|---|---|
| **Python 3.12** | The language |
| **uv** | Installs Python packages and manages the virtual environment. A fast, modern replacement for `pip` + `venv` |
| **Docker Desktop** | Runs your app and database in containers |
| **Git** | Version control |

### Do it

Install each one, then check them:

```bash
python3 --version
uv --version
docker --version
git --version
```

### You should see

A version number for each one. If one fails, install that tool before moving on.

---

## Part 1: Create the project

### The idea

**A virtual environment** is a private folder of packages for one project. Project A can use FastAPI 0.100 while project B uses 0.159, and they never clash. uv creates it for you in `.venv/`.

**`pyproject.toml`** is your project's ID card: name, Python version and dependencies. It's like `package.json` in Node.

**`uv.lock`** records the *exact* version of every package, including the packages your packages depend on. Everyone who installs from it gets identical versions. **Always commit it.**

**The src layout** puts your code in `src/seatlock/` instead of the project root. This stops Python from accidentally importing your code from the wrong place, and it forces you to install the project properly. Most professional Python projects use it.

### Do it

```bash
uv init --package seatlock
cd seatlock
uv add fastapi uvicorn
uv add --dev pytest
git init
```

- `--package` creates the src layout.
- `uv add` installs a package *and* records it in `pyproject.toml`.
- `--dev` marks a package as needed only during development (tests, linters). It won't be installed in production.

### You should see

```
seatlock/
├── .python-version
├── pyproject.toml
├── uv.lock
├── README.md
└── src/
    └── seatlock/
        └── __init__.py
```

`pyproject.toml` lists `fastapi` and `uvicorn` under `dependencies`, and `pytest` under `[dependency-groups] dev`.

### Common mistakes

- **Using `pip install`.** It installs the package but doesn't record it in `pyproject.toml`, so nobody else gets it. Always use `uv add`.
- **Not committing `uv.lock`.** Then other machines install different versions, and "it works on mine" bugs begin.

---

## Part 2: Your first endpoint

### The idea

Before you add a database, Docker or anything else, prove the simplest version works. A **health endpoint** returns "I'm alive". Docker, load balancers and monitoring tools all use one.

- **FastAPI** is the web framework: it maps URLs to Python functions.
- **Uvicorn** is the server: it listens for HTTP requests and hands them to FastAPI.

### Do it

Create `src/seatlock/main.py`:

```python
from fastapi import FastAPI

app = FastAPI(title="SeatLock")


@app.get("/health")
def health():
    return {"status": "ok"}
```

Run it:

```bash
uv run uvicorn seatlock.main:app --reload
```

- `seatlock.main:app` means "in the module `seatlock.main`, use the variable `app`".
- `--reload` restarts the server every time you save a file. Use it only in development.
- `uv run` runs a command inside the project's virtual environment.

### You should see

- http://localhost:8000/health → `{"status":"ok"}`
- http://localhost:8000/docs → interactive API docs, generated automatically

---

## Part 3: Docker

### The idea

Your app runs on your machine. Docker makes it run the same on **any** machine: a teammate's laptop, a CI server, production.

It does this by packaging *everything* the app needs (OS libraries, Python, dependencies, code) into one unit.

| Term | Meaning | Analogy |
|---|---|---|
| **Image** | A frozen, read-only package of your app | A class, or a blueprint |
| **Container** | A running copy of an image | An instance of the class |
| **Dockerfile** | The recipe that builds an image | A build script |
| **Layer** | Each instruction in a Dockerfile creates one cached layer | A save point |

**Rules:**
- One container is always made from exactly one image.
- One image can start many containers.

**Layer caching is the most important idea.** Docker caches each step. If a step and everything before it are unchanged, Docker reuses the cache. Once one step changes, **every step after it reruns.**

So the order is:

> Things that rarely change go at the top (Python, dependencies).
> Things that change often go at the bottom (your code).

Get this right and rebuilds take seconds. Get it wrong and every code change reinstalls all your packages.

**CPU architecture matters.** Apple Silicon Macs are ARM (`arm64`). Most cloud servers are Intel/AMD (`amd64`). An image built on a Mac is ARM by default. When you deploy, build for the server's CPU with `--platform linux/amd64`.

### Do it

**1. Create `Dockerfile`** in the project root:

```dockerfile
# Base image: same Python version as .python-version
FROM python:3.12-slim

# Bring in uv from its official image
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first: this layer is cached until uv.lock changes
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# Code last: it changes often
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# Non-root user with a fixed UID and no login shell
ARG UID=10001
RUN useradd --uid "${UID}" --no-create-home --shell /usr/sbin/nologin appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "seatlock.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

> The `alembic` lines are added in [Part 6](#part-6-database-layer-and-alembic). Leave them out until then.

What each important line does:

| Line | Why |
|---|---|
| `python:3.12-slim` | About 150 MB vs 1 GB for the full image. Avoid `alpine` for Python; many packages don't install cleanly on it |
| `PYTHONUNBUFFERED=1` | Logs appear immediately in `docker logs` |
| `--locked` | The build fails if `uv.lock` is out of date. Production gets exactly what you tested |
| `--no-install-project` | Installs dependencies only. Editing your code won't trigger a reinstall |
| `--no-dev` | Keeps pytest and other dev tools out of the image |
| `README.md` in the `COPY` | `pyproject.toml` references it, so the build needs it |
| `--mount=type=cache` | Keeps uv's download cache between builds |
| `USER appuser` | If someone breaks into the app, they aren't root |
| `--host 0.0.0.0` | Accept connections from outside the container. `127.0.0.1` would only accept the container itself |
| `CMD [ ... ]` (list form) | uvicorn receives stop signals directly and shuts down cleanly |

**2. Create `.dockerignore`.** `COPY` sends your folder to Docker. This file keeps junk and secrets out:

```
# Note: README.md must NOT be ignored — pyproject.toml needs it to build.

# Python / tooling
**/.venv
**/__pycache__
**/*.pyc
**/.pytest_cache
**/.ruff_cache
**/.mypy_cache

# Secrets
**/.env
**/secrets*

# Git, editors, OS junk
**/.git
**/.gitignore
**/.vscode
**/.idea
**/.DS_Store

# Docker files themselves
**/.dockerignore
**/Dockerfile*
**/compose.y*ml
**/docker-compose*

# Not needed at runtime
tests/
loadtests/
plan.md
README.Docker.md
```

**3. Update `.gitignore`** so secrets and caches never reach git:

```
.venv
.env
__pycache__/
.pytest_cache/
.ruff_cache/
.mypy_cache/
.DS_Store
```

**4. Build the image:**

```bash
docker build -t seatlock .
```

| Part | Meaning |
|---|---|
| `-t seatlock` | Tag (name) the image `seatlock` |
| `.` | The build context: "use this folder". `COPY` can only see files inside it |

**5. Run a container:**

```bash
docker run --rm -p 8000:8000 seatlock
```

| Part | Meaning |
|---|---|
| `--rm` | Delete the container when it stops |
| `-p 8000:8000` | Port mapping, written as `YOUR_MACHINE:CONTAINER` |

### You should see

- The build output lists each step. On a rebuild, unchanged steps say `CACHED`.
- http://localhost:8000/health → `{"status":"ok"}`

Useful extra commands:

```bash
docker images                          # list images
docker run --rm -it seatlock bash      # open a shell inside a container
```

### Common mistakes

- **Using a generated Dockerfile without reading it.** Tools like `docker init` assume `pip` and a `requirements.txt` file. With uv the build fails with `"/requirements.txt": not found`. Generators are a starting point; adapt them to your project.
- **`COPY . .` with a src layout.** The code is copied but not installed, so `import seatlock` fails with `ModuleNotFoundError`. Install the project with `uv sync`.
- **Ignoring `README.md` in `.dockerignore`.** The uv build needs it. Files depend on each other: `Dockerfile`, `.dockerignore` and `pyproject.toml` must agree.
- **Shell-form `CMD`** (`CMD uvicorn ...`). The stop signal goes to the shell, not uvicorn, so `docker stop` waits 10 seconds and then kills it. Use the list form.
- **Forgetting to rebuild.** An image is a snapshot. After code changes, build again.
- **Ignoring build warnings.** Docker prints warnings like `JSONArgsRecommended` for a reason. Read them.

> **Tip:** commit before you run any tool that generates or overwrites files. If it makes a mess, `git restore <file>` brings your version back.

---

## Part 4: Docker Compose

### The idea

A real app needs several programs running together: the API, a database, and later a cache. Starting each with a long `docker run` command gets painful fast.

**Docker Compose** describes all of them in one file, `compose.yaml`, and starts them with one command.

`docker compose up` does this:

1. Reads `compose.yaml` and `.env`
2. Creates a private network
3. Creates volumes (first time only)
4. Gets an image for each service:
   - `image:` → downloads it if missing
   - `build:` → builds it from your Dockerfile if missing
5. Starts the containers in dependency order

**One service = one image = one container.** SeatLock has two services (`api` and `db`), so two containers.

#### What gets its own container?

> **One container per program that runs on its own and talks over the network.**

| Thing | What it is | Own container? |
|---|---|---|
| Postgres | A separate program; your app talks to it over the network | ✅ Yes |
| Redis | The same idea | ✅ Yes |
| Your API (uvicorn) | The program that serves your app | ✅ Yes, it's the `api` container |
| FastAPI, SQLAlchemy | **Libraries** your code `import`s | ❌ No, they live inside your image |
| pytest | A tool you run sometimes, not a long-running service | ❌ No |

Python's `import` only works within one process on one disk. It can't reach into another container. That's why libraries are installed *inside* your app's image.

#### Networking: services find each other by name

Compose puts all services on one private network. **Each service's name is its hostname.** The API reaches the database at `db`, not `localhost`.

Inside a container, `localhost` means *that container itself*. There's no Postgres inside the `api` container, so `localhost` won't work there.

#### Ports: the most confusing part, explained once

**Every container has its own private set of ports**, like a separate computer. Port 5432 inside a container never clashes with port 5432 on your machine.

A mapping opens a door from your machine into a container:

```yaml
ports:
  - "5433:5432"
#    ^^^^ your machine's side: must be free on your machine
#         ^^^^ container side: the port the program actually listens on
```

```
┌──────────────────── Your machine ────────────────────┐
│                                                       │
│  psql / TablePlus / uv run ...                        │
│        │ localhost:5433                               │
│        ▼                                              │
│   door 5433 ──┐                                       │
│               │   ┌──── Docker network ───────────┐   │
│               └──▶│  db: Postgres on 5432         │   │
│                   │        ▲                      │   │
│                   │        │ db:5432              │   │
│                   │  api container                │   │
│                   └───────────────────────────────┘   │
└───────────────────────────────────────────────────────┘
```

So the same database has two addresses, depending on who's asking:

| Connecting from | Address | Why |
|---|---|---|
| Inside Docker (the `api` container) | `db:5432` | Same network, so it uses the service name and the real port |
| Your machine | `localhost:5433` | Goes through the door you mapped |

No single address works from both sides. That's why the database URL lives in configuration, not in code ([Part 5](#part-5-settings-from-environment-variables)).

**Rule:** only change the **left** number. Leave the right one as the port the program inside really uses.

Here we map **5433** on the machine because a Postgres installed directly on the computer already uses 5432. Pick any free port.

#### Volumes: where the data lives

A container's files disappear when the container is removed. A **volume** is storage that lives outside the container. Without one, your database is wiped every time.

#### Health checks

`depends_on` alone only waits until the database container *starts*, not until Postgres is *ready*. A **health check** tells Compose how to test readiness. With `condition: service_healthy`, the API waits for it.

### Do it

**1. Create `compose.yaml`:**

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      # Inside Compose the database host is the service name "db", not localhost.
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-seatlock}:${POSTGRES_PASSWORD:-seatlock}@db:5432/${POSTGRES_DB:-seatlock}
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:17
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-seatlock}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-seatlock}
      POSTGRES_DB: ${POSTGRES_DB:-seatlock}
    ports:
      - "${POSTGRES_PORT:-5433}:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

| Syntax | Meaning |
|---|---|
| `${POSTGRES_USER:-seatlock}` | Use `POSTGRES_USER` from `.env`, or `seatlock` if it isn't set |
| `$${POSTGRES_USER}` | A literal `$`: the variable is read inside the container, not by Compose |
| `build: .` | Build this service from the Dockerfile |
| `image: postgres:17` | Use a ready-made image |

**2. Create `.env`** (never commit it):

```
POSTGRES_USER=seatlock
POSTGRES_PASSWORD=choose-a-password
POSTGRES_DB=seatlock
POSTGRES_PORT=5433
```

**3. Create `.env.example`** (commit it). It lists the keys with no real values, so others know what to set:

```
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=
POSTGRES_PORT=
```

**4. Start everything:**

```bash
docker compose up -d --build
```

- `-d` runs it in the background.
- `--build` rebuilds the API image. You need it after code changes; without it, Compose reuses the old image.

#### Do you need to create the database user?

**No.** The official Postgres image creates the user, password and database from `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB` automatically, **but only the first time it starts with an empty volume.** After that, the values are stored in the volume and the variables are ignored.

It does **not** create tables. Tables come from migrations ([Part 6](#part-6-database-layer-and-alembic)).

### You should see

```bash
docker compose ps
```

```
api   Up               0.0.0.0:8000->8000/tcp
db    Up (healthy)     0.0.0.0:5433->5432/tcp
```

Connect to the database from inside its container (no password needed):

```bash
docker compose exec db psql -U seatlock -d seatlock
```

### Common mistakes

- **`connection refused`.** Nothing is listening on that port. Usually the containers aren't running: start them with `docker compose up -d`.
- **`port is already allocated`.** Something on your machine already uses that port. Change the **left** number.
- **Connecting to the wrong database.** If a Postgres is also installed directly on your machine, `localhost:5432` reaches *that one*, not Docker's.
- **Using `localhost` inside a container.** Use the service name (`db`).
- **Using `db:5433`.** The `5433` exists only on your machine. Inside Docker, Postgres is on `5432`.
- **Changing `POSTGRES_*` and expecting it to apply.** Those values are used only once. To apply new ones, reset the volume (this **deletes the data**):
  ```bash
  docker compose down -v
  ```
- **Putting a full URL in `POSTGRES_DB`.** It's only the database *name*, like `seatlock`.
- **A `$` in a password.** Compose and the shell treat `$NAME` as a variable to look up. `321$ABC` silently becomes `321`. Avoid `$` in `.env` values, or wrap the value in single quotes. Compose warns you: `The "ABC" variable is not set`.

---

## Part 5: Settings from environment variables

### The idea

Some values change between environments:

- the database address (your machine vs Docker vs production)
- secret keys
- debug mode

Hard-coding them means editing code for every environment, and leaking secrets into git. Instead, the app reads them from **environment variables**.

**pydantic-settings** reads environment variables into a **typed, validated Python class**:

- `DEBUG=true` becomes the Python value `True`.
- A required value that's missing **crashes the app at start-up** with a clear error, instead of failing later during a request. This is called **failing fast**.

**Where values come from** (highest priority first):

1. Real environment variables (e.g. set by Compose or the server)
2. The `.env` file
3. Defaults in the code

This is what lets the same code use `localhost:5433` on your machine and `db:5432` in Docker:

| Where the app runs | Where `DATABASE_URL` comes from | Value |
|---|---|---|
| Your machine (`uv run ...`) | `.env` | `...@localhost:5433/seatlock` |
| The `api` container | `environment:` in `compose.yaml` | `...@db:5432/seatlock` |

The container never sees `.env`, because `.dockerignore` excludes it.

#### Secure by default

**Code defaults should be the safe, production values.** Development behaviour is switched on explicitly in `.env`.

| Default in code | If someone forgets to set it in production |
|---|---|
| `debug = False` | ✅ Safe |
| `debug = True` | ❌ Users see stack traces, file paths and SQL |

#### `ENVIRONMENT` vs `DEBUG`

| Setting | Question it answers | Values |
|---|---|---|
| `ENVIRONMENT` | **Where** is this running? | `local`, `test`, `staging`, `production` |
| `DEBUG` | **How much** should it show? | `true` / `false` |

`DEBUG` does nothing by itself; it only has an effect where your code reads it. Typical uses:

```python
app = FastAPI(debug=settings.debug)  # full tracebacks on errors
engine = create_async_engine(url, echo=settings.debug)  # print every SQL query
docs_url = (
    None if settings.environment == "production" else "/docs"
)  # hide docs in production
```

`--reload` is a uvicorn flag, not a setting. It's separate from `DEBUG`.

### Do it

**1. Install:**

```bash
uv add pydantic-settings
```

**2. Create `src/seatlock/config.py`:**

```python
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SeatLock"
    environment: Literal["local", "test", "staging", "production"] = "production"
    debug: bool = False

    database_url: str  # no default → required


settings = Settings()
```

| Part | Why |
|---|---|
| `env_file=".env"` | Also read `.env`. The path is relative to where you run the command, so run commands from the project root |
| `extra="ignore"` | `.env` also holds `POSTGRES_*` values meant for Docker. Don't complain about them |
| `Literal[...]` | Only these values are allowed. A typo like `prod` crashes at start-up |
| Field names | `database_url` reads `DATABASE_URL` (matching is case-insensitive) |

**3. Add to `.env`:**

```
ENVIRONMENT=local
DEBUG=true
DATABASE_URL=postgresql+asyncpg://seatlock:choose-a-password@localhost:5433/seatlock
```

The URL is built from the same values as the `POSTGRES_*` settings:

```
postgresql+asyncpg://  seatlock  :  choose-a-password  @  localhost  :  5433  /  seatlock
                       user         password              host          port     database
```

pydantic-settings does **not** expand `${...}` or `$` in `.env`. Write the full URL out.

**4. Add the same keys, without values, to `.env.example`:**

```
ENVIRONMENT=
DEBUG=
DATABASE_URL=
```

**5. Pass them to the container too.** The `api` container doesn't read `.env`, so add these lines to `api.environment` in `compose.yaml`:

```yaml
      ENVIRONMENT: ${ENVIRONMENT:-local}
      DEBUG: ${DEBUG:-false}
```

### You should see

```bash
uv run python -c "from seatlock.config import settings; print(settings)"
```

This prints your settings. Now remove `DATABASE_URL` from `.env` and run it again: you get a validation error. That's failing fast. Put it back afterwards.

### Common mistakes

- **Safe values as dev defaults** (`debug: bool = True` in code). Forgetting to override it in production exposes internals.
- **Running commands from a subfolder.** `.env` isn't found, so required values seem "missing".
- **Committing `.env`.** Secrets end up in git history forever. Commit `.env.example` instead.

---

## Part 6: Database layer and Alembic

### The idea

**SQLAlchemy** is an **ORM** (object-relational mapper). It maps Python classes to database tables, so `class User` becomes the `users` table.

Three pieces make up the database layer:

| Piece | What it is |
|---|---|
| **Engine** | Manages a pool of connections to Postgres |
| **Session** | One unit of work: queries plus a transaction |
| **Base** | The parent class for every model. `Base.metadata` is a registry of all your tables |

**asyncpg** is the Postgres driver for async code. It's the `+asyncpg` in the database URL.

**Alembic is version control for your database schema.** Without it, you'd create tables by hand, and nobody else could reproduce them: not CI, not production, not you after a reset. With Alembic, every schema change is a Python file in git:

```
alembic/versions/
├── 0001_initial_empty.py
├── 0002_create_users.py
└── 0003_create_events.py
```

Each migration has two functions:

```python
def upgrade():     # apply the change  (create a table, add a column…)
def downgrade():   # undo the change
```

Alembic stores the current version in a one-row table called **`alembic_version`**. `alembic upgrade head` runs every migration that hasn't been applied yet, in order.

```
Your models  ──autogenerate──▶  migration file  ──upgrade──▶  tables in Postgres
```

**Naming conventions.** If you don't name constraints (primary keys, foreign keys, unique constraints), Postgres invents names. Later migrations that need to drop or change them then break. Setting a naming convention on day one makes every name predictable. Changing it later is painful.

### Do it

**1. Install:**

```bash
uv add "sqlalchemy[asyncio]" asyncpg alembic
```

`[asyncio]` is an **extra**: an optional group of dependencies the package declares. It pulls in `greenlet`, which SQLAlchemy's async mode needs.

**2. Create `src/seatlock/database.py`:**

```python
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from seatlock.config import settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


engine = create_async_engine(settings.database_url)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
```

**3. Set up Alembic with the async template:**

```bash
uv run alembic init -t async alembic
```

This creates:

```
alembic.ini              ← Alembic's settings
alembic/
├── env.py               ← runs on every Alembic command
├── script.py.mako       ← template for new migrations
└── versions/            ← your migrations
```

**4. Connect Alembic to your settings.**

In `alembic.ini`, leave the URL empty. The real one comes from settings, and passwords must not be committed:

```ini
sqlalchemy.url =
```

In `alembic/env.py`, add these imports near the top:

```python
from seatlock.config import settings
from seatlock.database import Base
```

Right after `config = context.config`, add:

```python
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
```

And replace `target_metadata = None` with:

```python
target_metadata = Base.metadata
```

| Change | Why |
|---|---|
| `set_main_option(...)` | Alembic and the app use the same URL: one source of truth |
| `.replace("%", "%%")` | `alembic.ini` treats `%` as special, so a password containing `%` would break |
| `target_metadata` | Lets `--autogenerate` compare your models with the real database |

> Later, each feature's models must be imported in `env.py` (e.g. `import seatlock.auth.models`). Otherwise autogenerate can't see those tables.

**5. Create the first migration.** It's empty on purpose: there are no models yet. The goal is to prove the whole pipeline works before adding real tables.

```bash
docker compose up -d db
uv run alembic revision -m "initial empty migration"
uv run alembic upgrade head
```

**6. Make migrations available inside Docker.** Add the `alembic` lines to the Dockerfile after `COPY src ./src` (see [Part 3](#part-3-docker)), then rebuild:

```bash
docker compose up -d --build
docker compose exec api alembic upgrade head
```

Inside the container, `DATABASE_URL` comes from Compose (`db:5432`), so the same command works there.

### You should see

```bash
uv run alembic current
```

This prints the revision ID of your migration, marked `(head)`.

```bash
docker compose exec db psql -U seatlock -d seatlock -c '\dt'
```

This lists the `alembic_version` table.

### Alembic commands

| Command | What it does |
|---|---|
| `alembic revision -m "msg"` | Create an empty migration that you write yourself |
| `alembic revision --autogenerate -m "msg"` | Create a migration from the differences between your models and the database |
| `alembic upgrade head` | Apply all pending migrations |
| `alembic downgrade -1` | Undo the last migration |
| `alembic current` | Show the database's current revision |
| `alembic history` | List all migrations |

On your machine, prefix each with `uv run`.

### Rules

1. **Read every autogenerated migration before applying it.** Autogenerate misses things. For example, a renamed column becomes "drop and add", which **loses data**.
2. **Never edit a migration that's already applied** on a shared database. Make a new one.
3. **Commit a migration together with the model change** that caused it.
4. **Never create tables by hand.** If it isn't in a migration, it doesn't exist.

### Common mistakes

- **`No module named 'greenlet'`.** You installed `sqlalchemy` without the async extra. Fix: `uv add "sqlalchemy[asyncio]"`.
- **`password authentication failed`** (or `database "seatlock" does not exist`) right after changing `.env`. The database volume was created with the *old* values. Remember: `POSTGRES_*` only applies to an empty volume. Fix:
  ```bash
  docker compose down -v
  docker compose up -d
  ```
- **Reading a traceback from the top.** Read the **last line** first. That's the actual error. The lines above it only show the path the error took.

---

## Part 7: Code quality: Ruff, mypy and pre-commit

### The idea

Three kinds of tools check your code. Each catches a different kind of problem:

| Tool | Catches | Example |
|---|---|---|
| **Linter** (Ruff) | Bugs and bad habits | an unused import, an undefined name |
| **Formatter** (Ruff) | Inconsistent style | spacing, quotes, line breaks. It rewrites the file for you |
| **Type checker** (mypy) | Wrong types, *before* the code runs | passing a `str` where an `int` is expected |

In Node terms: Ruff is ESLint + Prettier, and mypy is TypeScript's `tsc`.

**Pre-commit** runs these tools automatically on every `git commit`. If a check fails, the commit is blocked until you fix it. Bad code never reaches git.

```
git commit ─▶ pre-commit ─▶ ruff check ─▶ ruff format ─▶ mypy ─▶ ✅ committed
                                                              └▶ ❌ blocked: fix, then commit again
```

Pre-commit is Python's equivalent of Node's **Husky**. You don't need Husky in a Python project.

Why bother, even alone? CI will run the same checks later. It's better to catch problems on your machine in seconds than in CI minutes later.

**Strict typing from day one.** With 4 files, strict mode costs a few type hints. With 40 files, switching to it means hundreds of errors. Start strict.

### Do it

**1. Install the tools as dev dependencies:**

```bash
uv add --dev ruff mypy pre-commit
```

**2. Configure them in `pyproject.toml`.** The config lives in the project, so everyone gets the same rules:

```toml
[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "F",    # pyflakes: unused imports, undefined names
    "I",    # import sorting
    "UP",   # modern Python syntax
    "B",    # bugbear: common bugs
    "SIM",  # simplifications
]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]
files = ["src"]
```

| Setting | Why |
|---|---|
| `select = [...]` | Ruff has hundreds of rules. This is a solid starting set; add more later |
| `strict = true` | Every function needs type hints |
| `pydantic.mypy` | Teaches mypy how pydantic fills fields from the environment |
| `files = ["src"]` | Type-check app code only, not generated migrations |

**3. Run Ruff.** First the linter:

```bash
uv run ruff check .
uv run ruff check . --fix
```

Then the formatter:

```bash
uv run ruff format .
```

Typical first-run fixes:

| Rule | Before | After |
|---|---|---|
| `I001` | imports in random order | sorted: standard library, third-party, your code |
| `F401` | `import sqlalchemy as sa` (unused) | removed |
| `UP007` | `Union[str, None]` | `str \| None` |
| `UP035` | `from typing import Sequence` | `from collections.abc import Sequence` |

Don't argue with the formatter. Its job is to end style debates.

**4. Run mypy:**

```bash
uv run mypy
```

Two errors are common on a new FastAPI project:

```
config.py: error: Missing named argument "database_url" for "Settings"
```
mypy thinks `Settings()` must be called with `database_url`. It doesn't know pydantic reads it from the environment. **Fix:** the `pydantic.mypy` plugin from step 2.

```
main.py: error: Function is missing a return type annotation
```
Strict mode needs return types. **Fix:**

```python
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

FastAPI also uses return types: they show up in `/docs`.

**5. Create `.pre-commit-config.yaml`** in the project root:

```yaml
repos:
  # General hygiene
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files
      - id: detect-private-key

  # Ruff: lint + format
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.17.1
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format

  # mypy: runs inside the project's environment
  - repo: local
    hooks:
      - id: mypy
        name: mypy
        entry: uv run --frozen mypy
        language: system
        types: [python]
        pass_filenames: false
```

| Part | Why |
|---|---|
| `pre-commit-hooks` | Small checks: stray whitespace, broken YAML/TOML, committed private keys |
| `rev:` | Pins each tool's version. `uv run pre-commit autoupdate` moves to the latest |
| `ruff-check` + `--fix` | Fixes what it can, blocks the commit on the rest |
| `repo: local` for mypy | mypy must see your installed packages (FastAPI, pydantic). `uv run` uses your `.venv` |
| `--frozen` | Use `uv.lock` as it is. A checking tool must never rewrite files |
| `pass_filenames: false` | Check the whole project (`files = ["src"]`), not just changed files |

**6. Install the git hook.** Everyone who clones the repo must run this once:

```bash
uv run pre-commit install
```

It writes a script into `.git/hooks/pre-commit`. Without this step, the config file does nothing.

**7. Run every hook on every file once:**

```bash
uv run pre-commit run --all-files
```

**8. Add the mypy cache to `.gitignore`:**

```
.mypy_cache/
```

**9. (Optional) Clean new migrations automatically.** Alembic generates files with unused imports and old syntax, which fail Ruff. In `alembic.ini`, under `[post_write_hooks]`:

```ini
hooks = ruff
ruff.type = module
ruff.module = ruff
ruff.options = check --fix REVISION_SCRIPT_FILENAME
```

Every new `alembic revision` now comes out clean.

### You should see

```
trim trailing whitespace.................Passed
fix end of files.........................Passed
check yaml...............................Passed
check toml...............................Passed
check for added large files..............Passed
detect private key.......................Passed
ruff check...............................Passed
ruff format..............................Passed
mypy.....................................Passed
```

From now on, these run on every `git commit`.

### How to read pre-commit results

| Result | Meaning | What to do |
|---|---|---|
| `Passed` | All good | Nothing |
| `Failed` + "files were modified by this hook" | The tool **fixed** something for you | `git add` again, then commit again |
| `Failed` + an error list | Something it can't fix | Fix it yourself, `git add`, commit again |

### Common mistakes

- **Forgetting `pre-commit install`.** The config exists, but nothing runs on commit.
- **Staging only part of your changes.** Pre-commit hides (stashes) unstaged changes while it runs. If a hook modifies a file that also has unstaged changes, you get `Stashed changes conflicted with hook auto-fixes... Rolling back fixes`, and every fix is undone. **Stage everything that belongs together** (`git add -A`), run the hooks, stage again, then commit.
- **Committing `pyproject.toml` without `uv.lock`.** They always change together, so commit them together.
- **`uv run mypy` without `--frozen` in the hook.** `uv run` may rewrite `uv.lock` first. The hook then "modifies files" even though mypy passed.
- **Using the `mirrors-mypy` hook.** It runs mypy in an isolated environment without your packages and reports false errors like `Cannot find module "fastapi"`. Use a `local` hook with `uv run`.
- **A file without a final newline.** `end-of-file-fixer` adds it and reports `Failed`. That's a fix, not an error: `git add` and commit again.
- **Installing packages with `uv pip install`.** The package lands in `.venv` but not in `pyproject.toml`, so nobody else gets it. Use `uv add`. To remove strays, run `uv sync`: it makes `.venv` match `pyproject.toml` exactly.
- **`git commit --no-verify` to skip the hooks.** It works in an emergency, but CI catches the same problems later anyway.

### FastAPI tip: write `Depends` with `Annotated`

Ruff's bugbear rules flag `B008` (a function call in a default argument) on this common pattern:

```python
def get_user(db: AsyncSession = Depends(get_db)): ...
```

Use the `Annotated` style instead. FastAPI recommends it, and it passes the linter:

```python
from typing import Annotated


def get_user(db: Annotated[AsyncSession, Depends(get_db)]): ...
```

### Editor setup

Install the **Ruff** extension for VS Code or Cursor and turn on **format on save**. Code is cleaned as you type, and pre-commit rarely has anything left to fix.

---

## Daily commands

```bash
# Start / stop
docker compose up -d --build      # start everything (rebuild the API image)
docker compose down               # stop everything, keep data
docker compose logs -f api        # follow the API logs

# Run the API on your machine with instant reload
docker compose up -d db
uv run uvicorn seatlock.main:app --reload

# Database
docker compose exec db psql -U seatlock -d seatlock         # SQL shell
uv run alembic revision --autogenerate -m "describe change" # new migration
uv run alembic upgrade head                                 # apply migrations

# Code quality
uv run ruff check . --fix         # lint and auto-fix
uv run ruff format .              # format
uv run mypy                       # type check
uv run pre-commit run --all-files # run every hook on every file

# Reset (⚠️ deletes all database data)
docker compose down -v
```

---

## Troubleshooting

| Error | Likely cause | Fix |
|---|---|---|
| `"/requirements.txt": not found` | A pip-based Dockerfile in a uv project | Use the uv Dockerfile |
| `ModuleNotFoundError: seatlock` in the container | Code copied but not installed | `uv sync` after `COPY src` |
| `connection refused` | Containers not running, or the wrong port | `docker compose ps`, then `up -d` |
| `port is already allocated` | Port in use on your machine | Change the left port number |
| `The "X" variable is not set` | A `$` inside a `.env` value | Remove the `$` or single-quote the value |
| `No module named 'greenlet'` | SQLAlchemy without the async extra | `uv add "sqlalchemy[asyncio]"` |
| `password authentication failed` | Volume created with old credentials | `docker compose down -v`, then `up -d` |
| `database "X" does not exist` | Same as above | Same as above |
| Code changes don't show up | Old image still running | `docker compose up -d --build` |
| `Missing named argument` for a pydantic `Settings` | mypy doesn't understand pydantic | Add `plugins = ["pydantic.mypy"]` |
| `Function is missing a return type annotation` | mypy strict mode | Add `-> ReturnType` |
| `Stashed changes conflicted with hook auto-fixes` | Unstaged changes in files a hook modified | `git add -A`, run hooks, `git add -A`, commit |
| mypy hook `Failed` but says `Success` | `uv run` rewrote `uv.lock` | Use `uv run --frozen mypy` in the hook |
| `B008` on `Depends(...)` | Function call in a default argument | Use `Annotated[Type, Depends(...)]` |
| A package in `.venv` but not in `pyproject.toml` | Installed with `uv pip install` | `uv sync` removes it; use `uv add` |

---

## Progress

- [x] Project created with uv (src layout)
- [x] `/health` endpoint
- [x] Dockerfile, `.dockerignore`, `.gitignore`
- [x] Compose: `api` + `db` (Postgres 17)
- [x] Settings with pydantic-settings
- [x] SQLAlchemy database layer
- [x] Alembic + first empty migration
- [x] Ruff (lint + format) and mypy (strict)
- [x] Pre-commit hooks
- [ ] `main.py` uses `settings` (`debug`, hide `/docs` in production)
- [ ] Pass `ENVIRONMENT` and `DEBUG` to `api` in `compose.yaml`
- [ ] Auth: `User` model + first real migration
- [ ] Register and login with JWT

The full roadmap is in [`plan.md`](../plan.md).

---

## Changelog

Newest first.

| Date | Change |
|---|---|
| 2026-10-22 | Added Ruff, mypy (strict + pydantic plugin), pre-commit hooks, and Ruff on new Alembic migrations |
| 2026-10-22 | Added settings (`config.py`), database layer (`database.py`), Alembic and the first empty migration |
| 2026-10-21 | Added Compose with `api` + `db`, `.env.example`, and a merged `.dockerignore` |
| 2026-10-21 | Added the uv Dockerfile and the `/health` endpoint |
| 2026-10-21 | Created the project plan |
