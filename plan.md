# Event Ticketing & Seat Reservation API — Project Plan

A small Ticketmaster-style backend built with **Python, FastAPI, Postgres and a DevOps pipeline**.

**The core challenge:** 2,000 people try to buy the last 50 seats at the same moment, and nobody gets double-booked.

---

## Stack

| Layer | Tools | What it teaches |
|---|---|---|
| API | Python, FastAPI, Pydantic | Async endpoints, dependency injection, schemas, JWT auth with roles, background tasks, WebSockets |
| Database | Postgres, SQLAlchemy, Alembic | Relational modeling, row locking (`SELECT … FOR UPDATE SKIP LOCKED`), constraints, transactions, indexes, migrations |
| Cache / queue | Redis, ARQ or Celery | Rate limiting, caching, background workers |
| DevOps | Docker, Docker Compose, GitHub Actions, Prometheus, Grafana | Containers, CI/CD, deployment, metrics, structured logging |
| Testing | pytest, Locust | Integration tests against real Postgres, load testing |

---

## Phase 0 — Project setup

- [ ] Initialise the git repo and a `.gitignore`
- [ ] Set up the project layout (`app/`, `tests/`, `alembic/`)
- [ ] Manage dependencies with `uv` or Poetry
- [ ] Write a `Dockerfile` for the API
- [ ] Write a `docker-compose.yml` for the API and Postgres (Redis comes later)
- [ ] Load config from environment variables (`pydantic-settings`, `.env.example`)
- [ ] Configure Alembic and create the first empty migration
- [ ] Add a `GET /health` endpoint
- [ ] Add linting and formatting with Ruff, and type checking with mypy
- [ ] Add pre-commit hooks

## Phase 1 — Core API (~1–2 weeks)

### Users & auth
- [ ] Create the `users` table with roles: `buyer`, `organizer`, `admin`
- [ ] Add a register endpoint with hashed passwords (argon2 or bcrypt)
- [ ] Add login that returns a JWT access token, plus a refresh token
- [ ] Add a `get_current_user` dependency and role-based permission checks

### Venues, events, seats
- [ ] Model the data: `venues`, `sections`, `seats`, `events`, `event_seats`
- [ ] Let organizers create, update and delete venues and seat layouts
- [ ] Let organizers create, publish and cancel events
- [ ] Let buyers list events with pagination, filters (date, city) and search
- [ ] Let buyers view an event's seat map with each seat's availability
- [ ] Add indexes for common queries

### Testing
- [ ] Run pytest against a real Postgres in Docker (no SQLite)
- [ ] Add fixtures for the test DB, auth'd client and sample events
- [ ] Test the auth flows and permission rules
- [ ] Reach about 80% test coverage on the core modules

## Phase 2 — Reservations & checkout (the interesting part)

### Seat holds
- [ ] Add `POST /events/{id}/holds`, which holds the selected seats for 10 minutes
- [ ] Use row-level locking (`SELECT … FOR UPDATE SKIP LOCKED`) inside a transaction
- [ ] Add a database constraint that prevents double-booking (e.g. a unique index on active bookings per seat)
- [ ] Release expired holds automatically with a background job or a check at query time
- [ ] Add `DELETE /holds/{id}` so a buyer can release a hold manually
- [ ] Add a per-user limit on how many seats can be held

### Checkout & orders
- [ ] Model `orders` and `order_items`
- [ ] Add `POST /checkout`, which turns a hold into an order
- [ ] Require an `Idempotency-Key` header so retries don't create duplicate orders
- [ ] Add a payment step: a mock, or Stripe in test mode
- [ ] Handle payment failure and timeout by releasing the hold
- [ ] Add order history for buyers and sales reports for organizers

### Testing
- [ ] Write concurrency tests where many parallel requests target the same seat and exactly one succeeds
- [ ] Test idempotency by sending the same key twice and getting one order
- [ ] Test that expired holds become available again

## Phase 3 — Production-grade

### Performance & reliability
- [ ] Add Redis to Docker Compose
- [ ] Add rate limiting on auth and hold endpoints
- [ ] Cache popular event pages and invalidate the cache when the event changes
- [ ] Set up a background worker (ARQ or Celery) for jobs
- [ ] Email order confirmations with a QR-code ticket
- [ ] Push live seat-map updates over WebSockets (optional)

### Observability
- [ ] Write structured JSON logs that carry request IDs
- [ ] Expose a Prometheus `/metrics` endpoint (request latency, error rate, holds and orders)
- [ ] Build a Grafana dashboard
- [ ] Add a readiness check that verifies DB and Redis connectivity

### CI/CD
- [ ] Have GitHub Actions run lint, type checks and tests (with a Postgres service container) on every PR
- [ ] Build the Docker image and push it to a registry (GHCR) on `main`
- [ ] Deploy automatically to a VPS or cloud (Fly.io, Render, Railway or a DigitalOcean droplet)
- [ ] Run database migrations automatically on deploy
- [ ] Keep secrets in GitHub Secrets or the platform's secret store, never in the repo
- [ ] Serve the site over HTTPS on a custom domain (optional)

## Phase 4 — Proof & polish

- [ ] Write a Locust load test where 1,000 users compete for 100 seats
- [ ] Record the results and check for **zero double-bookings**, plus p95 latency and throughput
- [ ] Add an architecture diagram to the README
- [ ] Write up the concurrency approach: the race condition, how it was fixed, and how the fix was proven
- [ ] Keep the OpenAPI docs at `/docs` clean, with examples
- [ ] Seed script with demo data
- [ ] Add one-command local setup (`docker compose up`)
- [ ] Add a live demo link and screenshots to the README

---

## Stretch goals

- [ ] Waitlist for sold-out events
- [ ] Refunds and cancellations
- [ ] Dynamic pricing tiers per section
- [ ] Minimal frontend (React or HTMX) for the seat map
- [ ] Kubernetes manifests or Helm chart
- [ ] Terraform for the infrastructure
