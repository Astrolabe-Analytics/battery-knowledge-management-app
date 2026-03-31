# Battery Knowledge Management App — AWS Deployment Plan

**Created:** 2026-03-30
**Author:** Sebastian (plan), reviewed by deployment specialist sub-agent
**For:** Hardik (cloud engineer)
**Status:** Draft — pending team review
**Source repo:** `Astrolabe-Analytics/battery-knowledge-management-app`

---

## 1. Architecture Assessment

### 1.1 Is this a "totally frontend / Node-only" app?

**No.** This is a full-stack Python + React application with three distinct layers:

| Layer             | Technology                                          | Runtime                                            |
| ----------------- | --------------------------------------------------- | -------------------------------------------------- |
| **Frontend**      | React 19 + Vite (SPA)                               | Built into image, served as static files by uvicorn |
| **Backend API**   | FastAPI + Uvicorn (Python 3.13)                     | Python process, long-running                       |
| **Database**      | PostgreSQL 16 + pgvector 0.8.0                      | Managed database (RDS)                             |
| **Embeddings**    | sentence-transformers/all-MiniLM-L6-v2              | Runs inside the Python process (CPU, ~100MB model) |
| **LLM**           | Claude via Anthropic API                            | External API call (no local GPU)                   |
| **External APIs** | CrossRef, Semantic Scholar                          | Outbound HTTP                                      |
| **File storage**  | S3 (`papers/` prefix, ~2,000 PDFs)                  | `PAPERS_STORAGE=s3` env var activates S3 mode      |

The legacy Streamlit interface (`app.py` + `pages/`) is superseded by the React + FastAPI stack and excluded from deployment.

### 1.2 Single-container approach

The app runs as **one container** — identical to how the data-visualization-tool works. Uvicorn (FastAPI) serves both:
- All `/api/*` routes
- The built React SPA (`dist/`) as static files via `StaticFiles(directory="dist", html=True)`

No nginx sidecar needed. This is cheaper, simpler, and matches the existing data-viz-tool pattern.

---

## 2. Infrastructure Design

### 2.1 Target Architecture

```
                    ┌─────────────────────┐
                    │     ALB (HTTPS)      │
                    │  knowledge.astrolabe │
                    │  -analytics.com      │
                    └──────────┬───────────┘
                               │
                        port 8003
                               │
                    ┌──────────▼───────────┐
                    │   ECS Fargate Task    │
                    │                      │
                    │  ┌────────────────┐  │
                    │  │   uvicorn      │  │
                    │  │   port 8003    │  │
                    │  │                │  │
                    │  │ FastAPI app:   │  │
                    │  │  /api/*        │  │
                    │  │  /* → React    │  │
                    │  │    SPA (dist/) │  │
                    │  └──────┬─────────┘  │
                    └─────────┼────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
        ┌─────▼─────┐  ┌─────▼─────┐  ┌──────▼──────┐
        │ RDS        │  │ S3         │  │ External    │
        │ PostgreSQL │  │ PDFs       │  │ APIs        │
        │ + pgvector │  │ bucket     │  │ (Anthropic, │
        │            │  │            │  │  CrossRef,  │
        └────────────┘  └────────────┘  │  S. Scholar)│
                                        └─────────────┘
```

### 2.2 Component Decisions

| Concern         | Decision                                  | Rationale                                                               |
| --------------- | ----------------------------------------- | ----------------------------------------------------------------------- |
| **Compute**     | ECS Fargate (single task, 1 container)    | Matches data-viz-tool pattern; no nginx sidecar needed                  |
| **Database**    | RDS PostgreSQL 16 with pgvector extension | Managed, backups included, pgvector available on RDS since PG 15        |
| **PDF storage** | S3 bucket (`astrolabe-knowledge-pdfs`)    | ~2,000 PDFs; S3 is cheaper and already familiar                         |
| **Frontend**    | Served by FastAPI `StaticFiles` mount     | `dist/` baked into image; no nginx, no second container                 |
| **Auth**        | Share data-viz-tool's auth infrastructure | Same ALB perimeter, same legacy bypass, same Cognito path               |
| **Secrets**     | AWS Secrets Manager                       | Anthropic API key, DB password, Semantic Scholar key                    |
| **DNS**         | `knowledge.astrolabe-analytics.com`       | Follows existing `data.astrolabe-analytics.com` pattern                 |
| **Staging**     | `knowledge-stage.astrolabe-analytics.com` | Follows existing `-stage` convention                                    |

### 2.3 Sizing

| Resource        | Spec           | Rationale                                                                                                                              |
| --------------- | -------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| ECS task CPU    | 1024 (1 vCPU)  | Embedding model is CPU-bound but only runs during ingestion; normal API is I/O-bound                                                   |
| ECS task memory | 2048 MB (2 GB) | sentence-transformers model ~100MB × 2 workers = ~200MB + Python overhead + React static serving                                      |
| RDS instance    | db.t4g.micro   | ~2,000 rows + vector index; tiny workload. Upgrade to t4g.small if slow                                                                |
| RDS storage     | 20 GB gp3      | Vectors are ~1.5KB each × 2K papers = ~3MB; 20GB covers growth                                                                         |
| S3              | Standard tier  | PDFs average ~2MB × 2,000 = ~4GB total                                                                                                 |

**Estimated monthly cost:** ~$56-65/month:

| Service          | Calculation                                                                   | Monthly  |
| ---------------- | ----------------------------------------------------------------------------- | -------- |
| Fargate          | 1 vCPU × $0.04048/hr + 2GB × $0.004445/hr/GB = $0.0534/hr × 730 hrs          | ~$39     |
| RDS db.t4g.micro | On-demand, single-AZ                                                          | ~$15     |
| S3               | ~4GB Standard, minimal requests                                               | ~$1      |
| Secrets Manager  | 2 secrets × $0.40                                                             | ~$1      |
| ALB              | Shared with data-viz-tool (split overhead)                                    | ~$5      |
| **Total**        |                                                                               | **~$61** |

---

## 3. Dockerization

### 3.1 Dockerfile (2-stage)

See `Dockerfile` at repo root. Key design decisions:

- **Stage 1 (`frontend-build`):** node:20-slim, `npm ci`, `npm run build` → produces `dist/`
- **Stage 2 (`api`):** python:3.13-slim, installs deps, **pre-downloads sentence-transformers model** after pip / before code copy (critical for cache layering), copies `api/`, `lib/`, `scripts/`, and `dist/` from stage 1
- No nginx stage — uvicorn serves the static files

```dockerfile
# ── Stage 1: Frontend build ──
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ── Stage 2: Python API (serves React frontend + API on port 8003) ──
FROM python:3.13-slim AS api
RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev gcc && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Pre-download model — cached layer, only re-runs when requirements.txt changes
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
COPY api/ ./api/
COPY lib/ ./lib/
COPY scripts/ ./scripts/
COPY --from=frontend-build /app/frontend/dist ./dist
EXPOSE 8003
HEALTHCHECK --interval=15s --timeout=5s --start-period=45s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8003/api/health')"
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8003", "--workers", "2"]
```

### 3.2 FastAPI static file mount (`api/main.py`)

The React SPA is mounted after all `/api` routes:

```python
from fastapi.staticfiles import StaticFiles
import os

# Mount AFTER all /api routes — serve React SPA including html=True for SPA routing
_dist = os.path.join(os.path.dirname(__file__), "..", "dist")
if os.path.isdir(_dist):
    app.mount("/", StaticFiles(directory=_dist, html=True), name="static")
```

The `html=True` flag handles SPA routing — unknown paths return `index.html`. The `os.path.isdir` guard means local dev (no `dist/`) still works with the Vite dev server.

### 3.3 Local development (`docker-compose.yml`)

See `docker-compose.yml` at repo root. Local dev uses a **separate Vite dev server** (port 5173) for hot-reload. The `api` container runs with `--reload` and volume-mounted source directories. The single-container pattern only applies to production.

To start:
```bash
cp .env.example .env          # add ANTHROPIC_API_KEY
docker compose up -d          # postgres + api + frontend
# App: http://localhost:5173  | API: http://localhost:8003
```

To test S3 code path with LocalStack:
```bash
docker compose --profile s3 up -d localstack
./scripts/setup_localstack.sh
# Add to .env: PAPERS_STORAGE=s3 and AWS_ENDPOINT=http://localhost:4566
docker compose restart api
```

### 3.4 Key Docker Considerations

| Concern                                  | Approach                                                                                                                                                                           |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **sentence-transformers model download** | Baked into image via `RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"` in Dockerfile — eliminates cold-start delay  |
| **PDF files**                            | Mount as volume locally; in production, uses S3 with a presigned-URL approach (`PAPERS_STORAGE=s3`)                                                                                |
| **Database migrations**                  | SQLAlchemy `create_all_tables()` runs on startup; safe for initial deploy. Add Alembic for future schema changes                                                                   |
| **ChromaDB (legacy)**                    | Excluded from Docker. The PostgreSQL + pgvector stack fully replaces it. `chromadb` has been removed from `requirements.txt`                                                       |
| **Graceful shutdown**                    | `docker stop` sends SIGTERM → uvicorn finishes in-flight requests within 30s (ECS default stop timeout)                                                                            |

---

## 4. Authentication Strategy

### 4.1 Current State

The data-visualization-tool has a three-tier auth system:

1. **ALB perimeter auth** — Basic auth via ALB (legacy, active in production)
2. **API key system** — DynamoDB-backed Bearer tokens (implemented, not yet live)
3. **Cognito OIDC** — Planned Phase 2, ALB-injected OIDC headers (designed, not deployed)

The knowledge management app currently has **no authentication at all**.

### 4.2 Recommended Auth Approach

**Phase 1 (launch):** Share the ALB perimeter auth with the data-viz-tool.

- Deploy behind the **same ALB** as `data.astrolabe-analytics.com`
- Add a new listener rule for `knowledge.astrolabe-analytics.com` → knowledge ECS target group
- Apply the same Basic auth or Cognito authentication rule at the ALB level
- Set `LEGACY_AUTH_BYPASS=true` in the task definition — all requests reaching uvicorn are already authenticated by the ALB

This is exactly how the data-viz-tool works today.

**Phase 2 (when Cognito is active on data-viz-tool):** Add auth middleware to FastAPI.

```python
# api/middleware/auth.py
from fastapi import Request, HTTPException
import base64, json, os

async def extract_identity(request: Request):
    oidc_data = request.headers.get("x-amzn-oidc-data")
    if oidc_data:
        payload = json.loads(base64.b64decode(oidc_data.split(".")[1] + "=="))
        return {
            "sub": payload["sub"],
            "email": payload["email"],
            "groups": payload.get("cognito:groups", []),
        }
    if os.environ.get("LEGACY_AUTH_BYPASS") == "true":
        return {"sub": "legacy", "email": "admin@astrolabe-analytics.com", "groups": ["admins"]}
    raise HTTPException(status_code=401, detail="Not authenticated")
```

---

## 5. PDF Storage

### 5.1 S3 abstraction (`lib/s3_storage.py`)

`PAPERS_STORAGE=s3` activates S3 mode. The abstraction is already implemented:

- `save_pdf(filename, content)` — writes locally + uploads to S3 (in s3 mode)
- `pdf_exists(filename)` — checks local filesystem or S3 (with 60s TTL cache to avoid N head_object calls)
- `get_presigned_url(filename)` — generates a 1-hour GET URL
- `serve_pdf` endpoint returns `RedirectResponse(presigned_url, 302, headers={"Cache-Control": "no-store"})`

Local filesystem mode (default / dev) requires no env vars and no AWS credentials.

### 5.2 PDF Migration

Run `scripts/migrate_pdfs_to_s3.py` to upload Robert's existing `papers/` directory to S3:

```bash
# Dry run first
python scripts/migrate_pdfs_to_s3.py --dry-run

# Execute
python scripts/migrate_pdfs_to_s3.py --write
```

The script is idempotent — it skips files already present in S3.

---

## 6. Database Setup

### 6.1 RDS PostgreSQL with pgvector

```bash
aws rds create-db-instance \
  --db-instance-identifier astrolabe-knowledge-db \
  --db-instance-class db.t4g.micro \
  --engine postgres \
  --engine-version 16.4 \
  --master-username postgres \
  --master-user-password <from-secrets-manager> \
  --allocated-storage 20 \
  --storage-type gp3 \
  --vpc-security-group-ids <sg-id> \
  --db-subnet-group-name <subnet-group> \
  --no-publicly-accessible \
  --backup-retention-period 7 \
  --region us-west-2
```

After creation:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 6.2 Staging Database

Create a separate database on the same RDS instance:
```sql
CREATE DATABASE astrolabe_staging;
\c astrolabe_staging
CREATE EXTENSION IF NOT EXISTS vector;
```

Staging ECS service uses `DATABASE_URL` pointing to `astrolabe_staging` on the same RDS host. Data isolation without extra cost.

### 6.3 Data Migration

**Pre-flight (on throwaway database first):**
1. Check pgvector version compatibility: `SELECT extversion FROM pg_extension WHERE extname = 'vector';` on Robert's machine and on RDS
2. Test restore on a throwaway database:
   ```bash
   pg_dump --format=custom --no-owner --no-acl astrolabe > astrolabe_dump.pgcustom
   pg_restore --dbname=astrolabe_test --no-owner --no-acl astrolabe_dump.pgcustom
   ```
3. Run 3 sample RAG queries against restored test DB — compare results to Robert's local

**Production migration:**
1. `pg_dump --format=custom --no-owner --no-acl astrolabe > astrolabe_dump.pgcustom`
2. Upload to `s3://astrolabe-knowledge-pdfs/migration/`
3. `pg_restore` into RDS
4. `SELECT count(*) FROM papers;` — expect ~2,018
5. Reindex vector index: `REINDEX INDEX CONCURRENTLY idx_chunks_embedding;`
6. Run test RAG query end-to-end

**Rollback:** Drop and recreate the database, then re-run `pg_restore`. Robert's local copy is source of truth until migration is verified. After migration is live, use RDS automated snapshots for point-in-time recovery:
```bash
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier astrolabe-knowledge-db-restore \
  --db-snapshot-identifier <snapshot-id>
```

---

## 7. Environment Variables & Secrets

### 7.1 Secrets Manager Setup (Hardik)

```bash
# Full SQLAlchemy connection string — stored as plain string, not JSON
aws secretsmanager create-secret \
  --name knowledge-app/db-url \
  --secret-string 'postgresql+psycopg2://postgres:CHANGE_ME@astrolabe-knowledge-db.xxxxx.us-west-2.rds.amazonaws.com:5432/astrolabe' \
  --region us-west-2

# API keys — JSON, individual keys extracted via ":json-key::" syntax in task def
aws secretsmanager create-secret \
  --name knowledge-app/api-keys \
  --secret-string '{"anthropic_api_key":"sk-ant-CHANGE_ME","semantic_scholar_api_key":"OPTIONAL"}' \
  --region us-west-2
```

> **Important:** After `create-secret`, note the full ARN in the output — it includes a random 6-character suffix (e.g., `knowledge-app/db-url-aBcDeF`). Use the full ARN in the task definition. Run `aws secretsmanager list-secrets --filter Key=name,Values=knowledge-app` to find ARNs.

### 7.2 ECS Task Definition

See `deployment/ecs-task-definition.json` at repo root. Single container summary:

```json
{
  "family": "knowledge-app",
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [{
    "name": "app",
    "image": "ACCOUNT_ID.dkr.ecr.us-west-2.amazonaws.com/knowledge-app:latest",
    "portMappings": [{ "containerPort": 8003 }],
    "environment": [
      { "name": "PAPERS_STORAGE", "value": "s3" },
      { "name": "PAPERS_S3_BUCKET", "value": "astrolabe-knowledge-pdfs" },
      { "name": "AWS_REGION", "value": "us-west-2" },
      { "name": "LEGACY_AUTH_BYPASS", "value": "true" }
    ],
    "secrets": [
      { "name": "DATABASE_URL", "valueFrom": "arn:...:knowledge-app/db-url-SUFFIX" },
      { "name": "ANTHROPIC_API_KEY", "valueFrom": "arn:...:knowledge-app/api-keys-SUFFIX:anthropic_api_key::" }
    ]
  }]
}
```

Replace `SUFFIX` with the actual suffix from `aws secretsmanager list-secrets`.

### 7.3 IAM Task Role Policy

`knowledgeAppTaskRole` needs:

```json
{
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"],
    "Resource": [
      "arn:aws:s3:::astrolabe-knowledge-pdfs",
      "arn:aws:s3:::astrolabe-knowledge-pdfs/*"
    ]
  }]
}
```

Execution role additionally needs `secretsmanager:GetSecretValue` on `arn:aws:secretsmanager:us-west-2:ACCOUNT_ID:secret:knowledge-app/*`.

RDS access is network-level (security group) — no IAM policy needed for RDS.

---

## 8. Networking & Load Balancer

### 8.1 Security Groups

| SG Name                | Inbound                  | Outbound                                           |
| ---------------------- | ------------------------ | -------------------------------------------------- |
| `knowledge-app-alb-sg` | 443 from 0.0.0.0/0       | All                                                |
| `knowledge-app-ecs-sg` | 8003 from ALB SG only    | All (API calls to Anthropic, CrossRef, S. Scholar) |
| `knowledge-app-rds-sg` | 5432 from ECS SG only    | None                                               |

### 8.2 ALB Target Group & Health Check

| Setting              | Value                                   |
| -------------------- | --------------------------------------- |
| Target type          | IP (Fargate)                            |
| Port                 | **8003** (uvicorn directly)             |
| Health check path    | `/api/health`                           |
| Health check port    | 8003                                    |
| Healthy threshold    | 2                                       |
| Unhealthy threshold  | 3                                       |
| Interval             | 30s                                     |
| Timeout              | 10s                                     |
| Deregistration delay | 120s (allows in-flight RAG queries to finish) |

### 8.3 ALB Listener Rule Deployment Sequence

1. Create target group (no targets yet)
2. Create DNS CNAME → ALB
3. Deploy ECS service → targets register → health checks pass
4. Add ALB listener rule: `Host: knowledge.astrolabe-analytics.com` → target group (no auth initially)
5. Verify app is reachable and functional
6. **Then** add Basic auth rule to the listener rule

### 8.4 DNS

| Record                                    | Type  | Target       |
| ----------------------------------------- | ----- | ------------ |
| `knowledge.astrolabe-analytics.com`       | CNAME | ALB DNS name |
| `knowledge-stage.astrolabe-analytics.com` | CNAME | ALB DNS name |

---

## 9. Logging & Monitoring

### 9.1 CloudWatch Log Group

```bash
aws logs create-log-group \
  --log-group-name /ecs/knowledge-app \
  --retention-in-days 30 \
  --region us-west-2
```

Log stream: `/ecs/knowledge-app/app/<task-id>`

### 9.2 CloudWatch Alarms

```bash
aws sns create-topic --name knowledge-app-alerts --region us-west-2
aws sns subscribe --topic-arn <TOPIC_ARN> \
  --protocol email --notification-endpoint team@astrolabe-analytics.com
```

| Alarm           | Metric                          | Threshold         | Period |
| --------------- | ------------------------------- | ----------------- | ------ |
| ECS task crash  | `ECS/RunningTaskCount` = 0      | < 1 for 2 minutes | 1 min  |
| API 5xx spike   | ALB `HTTPCode_Target_5XX_Count` | > 10 in 5 min     | 5 min  |
| RDS CPU         | `CPUUtilization`                | > 80% for 10 min  | 5 min  |
| RDS connections | `DatabaseConnections`           | > 20 for 5 min    | 1 min  |
| RDS storage     | `FreeStorageSpace`              | < 2 GB            | 5 min  |

### 9.3 Rollback Protocol

```bash
# 1. Find previous working revision
aws ecs describe-services --cluster data-viz-tool --services knowledge-app

# 2. Revert
aws ecs update-service --cluster data-viz-tool --service knowledge-app \
  --task-definition knowledge-app:<previous-revision>

# 3. Verify
curl https://knowledge.astrolabe-analytics.com/api/health

# 4. Investigate failed task
# CloudWatch Logs → /ecs/knowledge-app/app/
```

---

## 10. Deployment Checklist

### Phase 0: Dockerization ✅ (complete)

- [x] Remove `chromadb` from `requirements.txt` (replaced by pgvector)
- [x] Verify no Python code imports chromadb: `rg "import chromadb|from chromadb" api/ lib/`
- [x] Create `Dockerfile` (2-stage: frontend-build → api)
- [x] Create `docker-compose.yml` (dev stack: postgres + api + frontend Vite)
- [x] Create `.dockerignore`
- [x] Create `.env.example`
- [x] Create `lib/s3_storage.py` (S3 PDF abstraction with local fallback)
- [x] Create `scripts/setup_localstack.sh`
- [x] Create `scripts/migrate_pdfs_to_s3.py` (idempotent, --dry-run default)
- [x] Modify PDF endpoints to use S3 presigned URLs
- [x] Modify import flow to upload PDFs to S3
- [x] Create `deployment/ecs-task-definition.json` (single container)
- [ ] First local Docker test: `docker compose up -d`, import a paper, run a RAG query
- [ ] Test with LocalStack S3 (`--profile s3`)
- [ ] Verify sentence-transformers model bakes into image without errors
- [ ] Commit all Docker + deployment files

**Gate: Phase 1 cannot start until local Docker test passes.**

### Phase 1: AWS Infrastructure (Hardik)

- [ ] Create CloudWatch log group `/ecs/knowledge-app` (30 day retention)
- [ ] Create S3 bucket `astrolabe-knowledge-pdfs`
- [ ] Create RDS PostgreSQL 16 instance with pgvector (Section 6.1)
- [ ] Enable pgvector: `CREATE EXTENSION IF NOT EXISTS vector;`
- [ ] Create `astrolabe_staging` database on same RDS instance
- [ ] Create Secrets Manager entries (Section 7.1)
- [ ] Create ECR repository: `knowledge-app` (single repo)
- [ ] Create IAM task role `knowledgeAppTaskRole` with S3 policy (Section 7.3)
- [ ] Add Secrets Manager access to execution role
- [ ] Create security groups (Section 8.1)
- [ ] Create ALB target group (port **8003**, IP type, health check per Section 8.2)
- [ ] Create DNS CNAME records (Section 8.4)
- [ ] Register ECS task definition (`deployment/ecs-task-definition.json`)
- [ ] Create ECS service in existing cluster

### Phase 1.5: Monitoring (Hardik)

- [ ] Create SNS topic for alerts
- [ ] Create CloudWatch alarms (Section 9.2)

### Phase 2: Data Migration (Sebastian + Robert)

**Pre-flight:**
- [ ] Verify pgvector version compatibility (Robert's local vs. RDS)
- [ ] Test `pg_dump` → `pg_restore` on a throwaway database
- [ ] Run 3 sample RAG queries against restored test DB

**Production:**
- [ ] `pg_dump --format=custom --no-owner --no-acl astrolabe > astrolabe_dump.pgcustom`
- [ ] Upload to `s3://astrolabe-knowledge-pdfs/migration/`
- [ ] `pg_restore` into RDS
- [ ] `SELECT count(*) FROM papers;` — expect ~2,018
- [ ] Reindex vector indexes
- [ ] Run `scripts/migrate_pdfs_to_s3.py --write` to upload PDFs from Robert's machine
- [ ] Verify PDF count in S3 matches local count
- [ ] Run end-to-end RAG query against RDS

### Phase 3: Staging Deployment & Verification

- [ ] Build image: `docker build -t ACCOUNT_ID.dkr.ecr.us-west-2.amazonaws.com/knowledge-app:latest .`
- [ ] Push to ECR: `docker push ACCOUNT_ID.dkr.ecr.us-west-2.amazonaws.com/knowledge-app:latest`
- [ ] Deploy to staging ECS service (`astrolabe_staging` database)
- [ ] Add ALB listener rule for `knowledge-stage.astrolabe-analytics.com` (no auth initially)
- [ ] Verify health: `curl https://knowledge-stage.astrolabe-analytics.com/api/health`
- [ ] Verify paper listing, detail view, PDF access (presigned URL redirect)
- [ ] Verify RAG query pipeline
- [ ] Verify import flow (DOI, URL, PDF upload → S3)
- [ ] Add Basic auth rule to ALB listener
- [ ] Verify auth is enforced

### Phase 3.5: Rollback Test

- [ ] Deploy a known-bad image
- [ ] Verify ALB returns 503
- [ ] Revert to previous task definition revision (Section 9.3)
- [ ] Verify health recovers

### Phase 4: Production Launch

- [ ] Build production image, push to ECR
- [ ] Deploy to production ECS service (`astrolabe` database)
- [ ] Add ALB listener rule for `knowledge.astrolabe-analytics.com` (no auth initially)
- [ ] Verify health and functionality
- [ ] Add Basic auth rule
- [ ] Share URL with team

---

## 11. Risks and Mitigations

| Risk                                 | Impact                                                | Mitigation                                                                                     |
| ------------------------------------ | ----------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| **sentence-transformers cold start** | First request after deploy takes 10-30s to load model | Baked into Docker image; health check `startPeriod=45s` allows warmup                          |
| **Anthropic API rate limits**        | RAG queries fail under load                           | Internal tool with ~3 users; retry logic in `lib/retry.py`                                    |
| **pgvector dump/restore corruption** | Vector search returns wrong results                   | Test restore on throwaway DB first; compare RAG results before production                      |
| **PDF migration data loss**          | PDFs not all transferred to S3                        | Migration script is idempotent; verify count matches; Robert keeps local copy until verified   |
| **Auth gap during deploy**           | App accessible without auth before rule applied       | Deploy ECS → verify health → add auth rule (Section 8.3 sequence)                              |
| **Database credentials leak**        | Hardcoded creds                                       | Secrets Manager with `valueFrom` in task def; never plain text                                 |
| **Python 3.13 compatibility**        | Build fails with sentence-transformers or psycopg2    | Test in Docker during Phase 0; fall back to Python 3.12 image if needed                        |
| **Graceful shutdown**                | In-flight RAG queries killed mid-stream               | Uvicorn graceful shutdown handles SIGTERM; ECS deregistration delay 120s                       |

---

## 12. Future Considerations

| Item                            | When                              | Notes                                                                    |
| ------------------------------- | --------------------------------- | ------------------------------------------------------------------------ |
| **Cognito integration**         | After data-viz-tool Phase 2 ships | Share user pool; add FastAPI middleware (Section 4.2)                    |
| **API key support**             | After Cognito                     | Programmatic access for agents                                           |
| **CI/CD pipeline**              | After initial manual deploy works | GitHub Actions: build → push ECR → deploy ECS                            |
| **Alembic migrations**          | Before next schema change         | `create_all_tables()` works for v1 but doesn't handle migrations         |
| **Paper-to-dataset linking**    | Product feature                   | Connect papers to data-viz-tool datasets via DOI/chemistry               |
| **Shared CloudWatch dashboard** | After both apps are on ECS        | Unified monitoring for data-viz-tool + knowledge app                     |

---

## Appendix A: Hardik Quick-Reference Card

**What is this app?** Internal tool for managing ~2,000 battery research papers with AI-powered search (RAG). Python + React + PostgreSQL.

**Is it frontend-only?** No. Python FastAPI backend, PostgreSQL + pgvector for embeddings, Anthropic API for AI answers, S3 for PDF files.

**Single container or two?** **One container.** Uvicorn serves both the FastAPI API (`/api/*`) and the built React frontend (`/*`) from `dist/`. No nginx needed. Same pattern as the data-viz-tool.

**What port?** **8003.** ALB target group and health check both point to port 8003.

**How does it relate to data-viz-tool?** Same team, same AWS account, same ALB, same auth strategy. Different database (PostgreSQL vs DuckDB).

**What's the minimum to deploy?** RDS PostgreSQL (pgvector), one ECR repo (`knowledge-app`), ECS task (1 container), ALB listener rule for `knowledge.astrolabe-analytics.com`, S3 bucket for PDFs, Secrets Manager for API keys, CloudWatch log group. Share existing ALB and cluster.

---

## Appendix B: Review History

| Round | Verdict    | Critical | Important | Action                                                                                                                                                                                                                                                                     |
| ----- | ---------- | -------- | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1     | NEEDS WORK | 7        | 10        | All addressed — added ECS task def, IAM policy, secrets commands, cost recalculation, CloudWatch logging/alarms, rollback protocol, migration pre-flight, staging DB strategy, ALB deploy sequence, container resource split, graceful shutdown, PDF migration script spec |
| 2     | NEEDS WORK | 2        | 5         | Fixed DATABASE_URL secret format, ARN suffix notes, Docker build commands, ChromaDB import verification, deregistration delay, RDS snapshot rollback                                                                                                                       |
| 3     | Architecture change | — | — | Collapsed to single container (uvicorn serves React SPA directly). Removed nginx stage, updated task def, ALB port changed from 80 → 8003, single ECR repo |
