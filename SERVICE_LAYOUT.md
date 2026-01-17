# FINAL DOCKER-FIRST SERVICE LAYOUT

## 1. Services, Roles, and Ports

| # | Service | Role | Port | Image / Build |
|---|---------|------|------|---------------|
| 1 | **frontend** | React SPA; all UI; talks only to api-gateway | 80 (nginx) / 3000 (dev) | `./frontend` |
| 2 | **api-gateway** | Single HTTP entry for frontend; proxies to auth, gmail-connector, classifier; JWT verification | 8000 | `./services/api-gateway` |
| 3 | **auth-service** | Google OAuth + backend JWT only; `/auth/login`, `/auth/callback`, `/auth/me`, `/auth/logout` | 8001 | `./services/auth-service` |
| 4 | **gmail-connector-service** | Raw Gmail fetch only; pagination until `nextPageToken` null; no classification | 8002 | `./services/gmail-connector-service` |
| 5 | **classifier-service** | Two-stage pipeline; input: raw/message data; output: exactly 5 categories; ghosted logic | 8003 | `./services/classifier-service` |
| 6 | **database** | PostgreSQL; all persistent state | 5432 | `postgres:15-alpine` |

---

## 2. Allowed HTTP Dependencies (No Circular)

```
                    +------------------+
                    |     frontend     |
                    |  (React, :80)    |
                    +--------+---------+
                             |
                             | HTTP only to api-gateway
                             v
                    +------------------+
                    |   api-gateway    |
                    |     (:8000)      |
                    +--------+---------+
                             |
         +-------------------+-------------------+
         |                   |                   |
         v                   v                   v
+----------------+  +------------------+  +------------------+
|  auth-service  |  | gmail-connector  |  | classifier-      |
|    (:8001)     |  |   -service      |  |   service       |
|                |  |    (:8002)       |  |   (:8003)        |
+-------+--------+  +--------+---------+  +--------+---------+
        |                   |                   |
        |                   +----------+---------+
        |                              |
        v                              v
+----------------+              +------------------+
|   database     |<-------------+  (Postgres)      |
|  (Postgres)    |   (optional) |   gmail can call  |
|   (:5432)      |   classifier|   classifier for  |
+----------------+   for labels |   per-msg or      |
        ^                     |   batch; classifier|
        |                     |   does NOT call    |
        +---------------------+   Gmail or Auth    |
          auth, gmail, classifier
          may connect to DB
```

**Allowed calls:**

| From | To | Purpose |
|------|-----|---------|
| frontend | api-gateway only | All API requests |
| api-gateway | auth-service | /auth/* proxy |
| api-gateway | gmail-connector-service | /sync/*, /status, /applications, /clear, etc. |
| api-gateway | classifier-service | /classify (single or batch) |
| auth-service | database | Users, sessions, tokens |
| gmail-connector-service | database | Applications, SyncState, raw cache |
| gmail-connector-service | classifier-service | Optional: send message data, get 5 categories |
| classifier-service | database | Optional: read/write classification metadata only; never Gmail or Auth |

**Disallowed (no circular, no bypass):**

- frontend → auth-service, gmail-connector, classifier, database: **forbidden**
- api-gateway → database: **no direct DB**; only via auth, gmail, classifier
- classifier-service → auth-service, gmail-connector: **forbidden**
- auth-service → gmail-connector, classifier: **forbidden**
- gmail-connector → auth-service: **forbidden**

---

## 3. Rules (Enforced by This Layout)

- **Frontend:** NEVER calls gmail-connector, auth-service, or classifier directly; ONLY api-gateway.
- **api-gateway:** Single entry point for the frontend; proxies to auth, gmail-connector, and classifier; verifies JWT for protected routes.
- **auth-service:** Owns Google OAuth and JWT only; NO Gmail, NO classification logic.
- **gmail-connector-service:** Raw Gmail fetch only; NO classification; NO filtering; NO limits; paginate until `nextPageToken == null`.
- **classifier-service:** Receives raw/message data (from gmail-connector or via gateway); returns exactly 5 categories (Applied, Rejected, Interview, Offer/Accepted, Ghosted); does NOT call Gmail or Auth.

---

## 4. Repo Folder Structure

```
<project-root>/
├── docker-compose.yml
├── .env.example
├── SERVICE_LAYOUT.md          # this document
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   ├── nginx.conf             # for production serve
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── router/
│       ├── context/
│       ├── pages/
│       ├── components/
│       ├── services/          # only api-gateway base URL
│       └── styles/
│
├── services/
│   ├── api-gateway/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py
│   │       ├── config.py
│   │       ├── middleware/
│   │       └── routers/
│   │
│   ├── auth-service/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py
│   │       ├── jwt.py
│   │       └── google_oauth.py
│   │
│   ├── gmail-connector-service/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py
│   │       ├── gmail_client.py
│   │       ├── sync_engine.py
│   │       ├── database.py
│   │       └── state.py
│   │
│   └── classifier-service/
│       ├── Dockerfile
│       ├── requirements.txt
│       └── app/
│           ├── main.py
│           ├── classifier.py
│           ├── stage1_high_recall.py
│           ├── stage2_high_precision.py
│           └── ghosted.py
│
└── (database: Postgres image only; no app folder)
```

---

## 5. Port Summary

| Service | Port |
|---------|------|
| frontend | 3000 (host) → 80 (container) or 5173 (vite dev) |
| api-gateway | 8000 |
| auth-service | 8001 |
| gmail-connector-service | 8002 |
| classifier-service | 8003 |
| database (Postgres) | 5432 |

---

*This layout is authoritative for Step 3 (Docker Compose + base Dockerfiles) and all later steps. No service boundaries or allowed-call matrix may change without updating this document.*
