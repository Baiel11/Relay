# Relay — Real-Time Chat Backend

---

## What it is

A real-time chat API where users can:
- Register / login with JWT auth (access + refresh tokens in HttpOnly cookies)
- Create 1-on-1 conversations
- Send messages with idempotency protection
- See online status and typing indicators
- Mark conversations as read (read receipts)

Architecture: **FastAPI** (HTTP + WS) + **PostgreSQL** (persistent state) + **Redis** (presence, unread counters, Pub/Sub distribution, rate limiting).

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Web Framework | FastAPI 0.115 + Python 3.12 |
| ORM | SQLAlchemy 2.0 (async/await) |
| Database | PostgreSQL 16 |
| Realtime | Redis 7 (Pub/Sub, presence, rate limiting) |
| Auth | PyJWT (HS256) + argon2 password hashing |
| ASGI Server | Uvicorn + uvloop |
| Migrations | Alembic |
| Rate Limiting | Redis Lua scripts (sliding window) |

---

## How it works

### 1. Startup
```
docker-compose up --build
# or: alembic upgrade head && uvicorn app.main:app
```
- Applies DB migrations
- Starts PostgreSQL + Redis + FastAPI backend

### 2. Request Flow
```
Client → FastAPI → Dependency Injection
  │
  ├── rate_limit (Redis Lua: 5/min register, 10/min login, 30/min users search)
  ├── get_current_user (JWT decode + DB lookup)
  ├── auth_service (register/login/refresh/logout)
  └── route handler (conversations, messages, WS)
```

### 3. WebSocket Flow
```
Client: ws://host/ws?token=<jwt>

1. Authenticate JWT from query param
2. connection_manager.connect(user_id, ws)
   → Set online presence (TTL=60s, refreshed on ping)
   → Broadcast presence_sync to all clients
3. Receive JSON frames with `type` field:
   - "send_message" → rate-limited → persist to Postgres → broadcast to subscribers
   - "subscribe" → toggle conversation subscription
   - "typing" → update Redis typing key (4s auto-expire)
   - "mark_read" → update Postgres read timestamp + reset Redis unread
4. disconnect → set offline → broadcast presence
```

### 4. Cross-Instance Delivery
Events are published to Redis channel `relay:events`. Each FastAPI instance runs a background listener that:
- Delivers messages/typing/read-receipts to locally connected sockets
- Filters out self-published events (via `origin_instance` UUID)

---

## Installation

### Option A: Docker (recommended)
```bash
# From project root
docker-compose up --build
```
- Starts postgres, redis, and backend at `http://localhost:8000`
- Swagger docs at `http://localhost:8000/docs`

### Option B: Local Development
```bash
# 1. Install deps
cd backend && pip install -r requirements.txt

# 2. Set env (copy .env.example → .env)
cp .env.example .env

# 3. Start services
docker compose up -d postgres redis   # or ensure they run locally
# 4. Apply migrations
cd backend && alembic upgrade head
# 5. Run server
uvicorn app.main:app --reload
```

### 3. Frontend
```bash
cd frontend && npm install && npm run dev
```
- Vite dev server at `http://localhost:5173`
- Proxies `/api` and `/ws` to backend

---

## Key Endpoints

| Method | Endpoint | Auth | Rate Limit |
|--------|----------|------|-----------|
| POST | `/api/v1/auth/register` | ❌ | 5/min |
| POST | `/api/v1/auth/login` | ❌ | 10/min |
| POST | `/api/v1/auth/refresh` | ✅ | — |
| GET | `/api/v1/auth/me` | ✅ | — |
| GET | `/ws?token=<jwt>` | ✅ | — |
| POST | `/api/v1/conversations` | ✅ | — |
| GET | `/api/v1/messages` | ✅ | — |

---

## Design Highlights

- **Normalized conversation pairs** — `normalize_pair()` sorts UUIDs to guarantee exactly one conversation per user pair, enforced by a DB unique constraint.
- **Idempotent messages** — `client_message_id` + unique constraint on `(sender_id, client_message_id)` prevents duplicate messages from network retries.
- **Redis TTL keys** — presence (60s), typing (4s), unread (24h) auto-expire; no cleanup jobs needed; resilient to Redis restarts.
- **Multi-instance Pub/Sub** — Redis `relay:events` channel distributes WebSocket events across multiple FastAPI workers/servers.
- **Lua-scripted rate limiting** — atomic sliding-window using sorted sets; used for HTTP endpoints + WS message anti-spam.
- **Refresh token rotation** — one-time JTI stored in Postgres; each refresh revokes the old JTI and issues a new pair.
- **Graceful shutdown** — lifespan handler cancels Pub/Sub listener, closes Redis pool, disposes SQLAlchemy engine.
- **Postgres fallback for Redis** — unread counters cached in Redis with a `db_fallback` callable that recomputes from Postgres if evicted.

---

## Project Layout

```
relay/
├── backend/              ← FastAPI backend
│   ├── app/              ← Source code
│   │   ├── main.py       ← Entry point, lifespan, middleware, routers
│   │   ├── core/         ← Config, DB, deps, Redis, security
│   │   ├── models/       ← SQLAlchemy ORM models
│   │   ├── schemas/      ← Pydantic v2 validation
│   │   ├── repositories/ ← CRUD + query layer
│   │   ├── services/     ← Business logic
│   │   ├── redis/        ← Redis services (pubsub, presence, typing, unread, rate_limiter)
│   │   └── api/          ← Route definitions
│   ├── requirements.txt  ← Python dependencies
│   └── docker-compose.yml ← postgres + redis + backend
├── frontend/             ← React + TS + Vite (SPA)
└── docs/                 ← Design notes
```

---
