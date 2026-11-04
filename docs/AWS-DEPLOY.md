# Deploying to AWS

Target architecture (managed services everywhere, no servers to patch):

```
                CloudFront (optional)
                        |
        ┌───────────────┴───────────────┐
        |              ALB              |   HTTPS, ACM cert, health check /health/live
        └───────────┬───────────────────┘
                    |
        ┌───────────┴───────────┐
        |    ECS Fargate task   |   backend (gunicorn, 1 worker) + optional ML sidecar
        |     (API only)        |
        └───────┬───────┬───────┘
                |       |
        ┌───────┴──┐ ┌──┴──────────┐
        | RDS      | | ElastiCache |   (optional - the app falls back to in-process cache)
        | Postgres | | Redis       |
        └──────────┘ └─────────────┘
```

The frontend can ride along on the same ALB (path routing: `/api/*` → backend,
everything else → the nginx frontend container) or be served from **S3 +
CloudFront** with `/api/*` forwarded to the ALB origin. Start with the first
option — it is one deployable unit and there is no CORS at all.

---

## 1. What the codebase already supports (no code changes needed)

| Concern | Support | Where |
|---|---|---|
| **RDS Postgres over TLS** | `POSTGRES_SSLMODE=require` (or `verify-full` + `POSTGRES_SSLROOTCERT`) | `backend/app/core/config.py` → `build_asyncpg_ssl()` / `asyncpg_connect_args()`; Alembic gets `sslmode` + `connect_timeout` on its sync URL |
| **RDS passwords with special characters** | `URL.create()` percent-encodes them | `backend/app/core/config.py` |
| **Idle connections dropped by RDS / proxies / firewalls** | `pool_pre_ping=True`, `pool_recycle=1800` | `backend/app/db/postgres.py` |
| **Concurrent starts racing migrations** | PostgreSQL advisory lock around `alembic upgrade head` | `backend/alembic/env.py` |
| **Redis over TLS** | `REDIS_SSL=true` → `rediss://`, `REDIS_USERNAME`/`REDIS_PASSWORD` URL-encoded | `backend/app/core/config.py` |
| **No Redis at all** | `REDIS_ENABLED=false`, or leave Redis unreachable → in-process fallback | `backend/app/db/redis_client.py` |
| **Load-balancer health checks by IP** | `GET /api/v1/health/live` touches nothing and is exempt from both the Host guard and the rate limiter | `backend/app/api/routes/health.py`, `backend/app/core/middleware.py` |
| **Host-header protection on a real domain** | `ALLOWED_HOSTS=["api.example.com","*.example.com"]` | `backend/app/core/config.py` |
| **Rate limiting shared across tasks** | `RATE_LIMIT_STORAGE_URI=redis://...` | `backend/app/core/config.py` (default `memory://` is per-process) |
| **Real client IP behind the ALB** | run with `--proxy-headers --forwarded-allow-ips=<ALB security-group IP/CIDR>` | `docker-compose.yml`, `backend/Dockerfile` CMD |
| **Secrets** | ECS task-definition `secrets` (Secrets Manager / SSM) — never bake `.env` into an image | this doc, §7 |
| **Low memory** | lightweight image (`requirements-base.txt`), 1 gunicorn worker, lazy ML imports, `PYTHONDONTWRITEBYTECODE=1`, `.dockerignore` excludes `venv/`, `.cache/`, `*.gguf` | `backend/Dockerfile`, `.dockerignore`, `docker-compose.yml` |
| **`/docs` in production** | `DOCS_ENABLED=false` | `backend/app/core/config.py` |

Two things you must decide **before** deploying:

1. **Workers.** Draft generation runs as an in-process `asyncio` background task,
   so keep **gunicorn `--workers 1`** (the image default). Two workers each run
   their own uncoordinated draft queue and duplicate work. Scale horizontally
   instead (more tasks behind the ALB), and set `RATE_LIMIT_STORAGE_URI` to your
   Redis so rate limits are shared.
2. **The JWT secret.** `SECRET_KEY` must be ≥ 32 characters and not a known
   default, or the app refuses to start with `DEBUG=false`.

---

## 2. Prerequisites

- An AWS account with IAM permissions for RDS, ECS, ECR, ELB, ACM, VPC, and
  (optionally) ElastiCache, S3 and CloudFront.
- AWS CLI v2, configured: `aws configure` (or `AWS_PROFILE` / SSO).
- Docker, to build and push images.
- A domain (Route 53 or any registrar) if you want HTTPS on your own domain.
  An `https://<alb-dns>` endpoint works without one, with an ACM certificate
  for the ALB DNS name.

```bash
aws sts get-caller-identity        # confirm the account/role
aws configure get region           # pick one region and keep it everywhere
```

---

## 3. Amazon RDS for PostgreSQL

```bash
# Private subnets only - never a public subnet.
aws rds create-db-instance \
  --db-instance-identifier legal-draft-db \
  --db-instance-class db.t4g.micro \
  --engine postgres --engine-version 15 \
  --master-username legaluser \
  --master-user-password "$RDS_PASSWORD" \
  --allocated-storage 20 --storage-type gp3 \
  --no-publicly-accessible \
  --db-subnet-group-name legal-draft-subnets \
  --vpc-security-group-ids sg-db \
  --enable-performance-insights
```

Notes:

- **No public IP.** The Fargate tasks reach it over the VPC.
- **TLS:** RDS enforces SSL only if you set `rds.force_ssl=1` in the parameter
  group — then your app must use `POSTGRES_SSLMODE=require` (see §7). The app
  works either way; prefer forcing SSL.
- `db.t4g.micro` is the free-tier shape; `db.t4g.small` is the first realistic
  size for this app (the pool is small on purpose: 3 + 2 connections).

Security group `sg-db` — allow `5432` **only** from the ECS task security group:

```bash
aws ec2 authorize-security-group-ingress \
  --group-id sg-db --protocol tcp --port 5432 \
  --source-group sg-ecs-tasks
```

---

## 4. (Optional) Amazon ElastiCache for Redis

You can skip this: the app falls back to a bounded in-process cache
(`REDIS_FALLBACK_MAX_KEYS=500`). You *do* want real Redis if you run more than
one task and care about shared rate limits or SSE progress pub/sub.

```bash
aws elasticache create-replication-group \
  --replication-group-id legal-draft-redis \
  --engine redis --cache-node-type cache.t4g.micro --num-cache-clusters 1 \
  --transit-encryption-enabled \
  --auth-token "$ELASTICACHE_TOKEN" \
  --subnet-group-name legal-draft-subnets \
  --security-group-ids sg-redis
```

Then set `REDIS_SSL=true`, `REDIS_HOST=<endpoint>`, `REDIS_PORT=6379`,
`REDIS_PASSWORD=<token>` (or `REDIS_USERNAME` for ElastiCache RBAC users).

---

## 5. Build and push the images

```bash
cd backend
docker build -t "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/legal-draft-backend:latest" .
docker push "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/legal-draft-backend:latest"

cd ../frontend
docker build \
  --build-arg VITE_API_URL="" \
  --build-arg VITE_GOOGLE_CLIENT_ID="$GOOGLE_CLIENT_ID" \
  -t "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/legal-draft-frontend:latest" .
docker push "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/legal-draft-frontend:latest"
```

Create the ECR repositories first (`aws ecr create-repository --repository-name legal-draft-backend`, etc.).

**`VITE_API_URL` stays empty on purpose.** The browser then calls `/api/v1` on
the same origin and nginx proxies it to the backend — no CORS, no baked-in host
name, and the build is portable between environments. Set it only for a split
deploy where the frontend and API are on different origins.

For the ML/RAG image, build `backend/Dockerfile.ml` instead and give that task
~2 GB of memory.

---

## 6. Run on ECS Fargate behind an ALB

```bash
aws ecs create-cluster --cluster-name legal-draft
aws ecs register-task-definition --family legal-draft-backend \
  --network-mode awsvpc --requires-compatibilities FARGATE \
  --cpu 1024 --memory 2048 \
  --execution-role-arn "$EXEC_ROLE" \
  --task-role-arn "$TASK_ROLE" \
  --container-definitions '[
    {
      "name": "backend",
      "image": "<account>.dkr.ecr.<region>.amazonaws.com/legal-draft-backend:latest",
      "portMappings": [{"containerPort": 8000}],
      "essential": true,
      "command": ["gunicorn","main:app","-k","uvicorn.workers.UvicornWorker","--workers","1","--bind","0.0.0.0:8000","--proxy-headers","--forwarded-allow-ips=ALB-SG-CIDR"],
      "secrets": [
        {"name":"SECRET_KEY","valueFrom":"<secrets-manager-arn>:SECRET_KEY::"},
        {"name":"POSTGRES_PASSWORD","valueFrom":"<secrets-manager-arn>:POSTGRES_PASSWORD::"},
        {"name":"REDIS_PASSWORD","valueFrom":"<secrets-manager-arn>:REDIS_PASSWORD::"},
        {"name":"GROQ_API_KEY","valueFrom":"<secrets-manager-arn>:GROQ_API_KEY::"}
      ],
      "environment": [
        {"name":"POSTGRES_HOST","value":"<rds-endpoint>"},
        {"name":"POSTGRES_PORT","value":"5432"},
        {"name":"POSTGRES_DB","value":"legal_draft_db"},
        {"name":"POSTGRES_USER","value":"legaluser"},
        {"name":"POSTGRES_SSLMODE","value":"require"},
        {"name":"REDIS_ENABLED","value":"true"},
        {"name":"REDIS_HOST","value":"<elasticache-endpoint>"},
        {"name":"REDIS_SSL","value":"true"},
        {"name":"DEBUG","value":"false"},
        {"name":"DOCS_ENABLED","value":"false"},
        {"name":"ALLOWED_HOSTS","value":"[\"api.example.com\"]"},
        {"name":"ALLOWED_ORIGINS","value":"[\"https://app.example.com\"]"},
        {"name":"RATE_LIMIT_STORAGE_URI","value":"redis://:<token>@<elasticache-endpoint>:6379/0"}
      ],
      "logConfiguration": {"logDriver":"awslogs","options":{"awslogs-group":"/ecs/legal-draft","awslogs-region":"<region>","awslogs-stream-prefix":"backend"}},
      "healthCheck": {"command":["CMD-SHELL","python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/live')\""],"interval":30,"timeout":5,"retries":3,"startPeriod":60}
    }
  ]'
```

- **Health check path:** `/api/v1/health/live` — it touches no dependency, so a
  database blip never gets the container killed. Point the ALB target-group
  health check there too (this is why the Host guard exempts that path: ALB
  probes by IP).
- **Secrets** come from Secrets Manager / SSM via `secrets`, one per key.
  Never put a real `.env` in the image — `backend/.dockerignore` already
  excludes it and `.env.*`.
- **Migrations** run automatically at container start (advisory-locked, so
  several tasks starting at once are safe). If you prefer not to migrate in the
  app container, run `alembic upgrade head` as a one-off ECS task with the same
  task definition instead.
- If you run the frontend in the same task, add a second container
  (`legal-draft-frontend`, port 5173) and two ALB target groups with path rules
  `/api/*` → backend, `/*` → frontend. nginx already proxies `/api/` and sets
  `proxy_read_timeout 600s` for long draft/SSE requests.

---

## 7. Environment variables for AWS

| Variable | Value on AWS |
|---|---|
| `POSTGRES_HOST` | RDS endpoint (`xxx.rds.amazonaws.com`) |
| `POSTGRES_SSLMODE` | `require` (or `verify-full`) |
| `POSTGRES_SSLROOTCERT` | path to the RDS CA bundle (`global-bundle.pem`) for `verify-full` |
| `POSTGRES_PASSWORD` | Secrets Manager |
| `REDIS_HOST` / `REDIS_PORT` | ElastiCache endpoint |
| `REDIS_SSL` | `true` (in-transit encryption) |
| `REDIS_PASSWORD` | ElastiCache AUTH token |
| `REDIS_ENABLED` | `false` to run with no Redis at all |
| `RATE_LIMIT_STORAGE_URI` | `redis://...` when you have more than one task |
| `ALLOWED_HOSTS` | `["api.example.com","*.example.com"]` |
| `ALLOWED_ORIGINS` | `["https://app.example.com"]` |
| `DOCS_ENABLED` | `false` |
| `FORWARDED_ALLOW_IPS` / gunicorn `--forwarded-allow-ips` | the ALB security-group CIDR |
| `SECRET_KEY` | ≥ 32 random characters, from Secrets Manager |

---

## 8. Moving local data to RDS

```powershell
# 1) dump the local database (Docker or local Postgres)
pg_dump -h localhost -U legaluser -d legal_draft_db -Fc -f legal_dump.dump

# 2) restore into RDS - needs a network path into the VPC (bastion, VPN, or an
#    SSM port-forward to a bastion in the same subnets)
pg_restore -h <rds-endpoint> -U legaluser -d legal_draft_db \
  --no-owner --clean --if-exists legal_dump.dump
```

`--no-owner` avoids ownership mismatches (the dump carries the local role name).

---

## 9. Approximate monthly cost (single region, low traffic)

| Item | Approx. |
|---|---|
| RDS `db.t4g.micro` (free tier for 6 months), then `db.t4g.small` | $0 → ~$25–30 |
| ElastiCache `cache.t4g.micro` | ~$12 |
| ECS Fargate (1 vCPU / 2 GB, always on) | ~$30 |
| ALB | ~$16 + LCU |
| Data transfer | ~$0.09/GB out |
| **Total** | **~$80–100/month** after free tier |

Cheaper alternative: a single `t3.small` **EC2** instance running
`docker compose up` with the same images (~$15/month). Use the managed path
above when you want zero operational burden.

---

## 10. Checklist before going live

- [ ] `SECRET_KEY` rotated and stored in Secrets Manager (never in `.env` or the image)
- [ ] `DOCS_ENABLED=false`, `DEBUG=false`
- [ ] `ALLOWED_HOSTS` / `ALLOWED_ORIGINS` set to your domains
- [ ] RDS: `POSTGRES_SSLMODE=require`, security group allows 5432 only from the task SG
- [ ] ALB health check path = `/api/v1/health/live`
- [ ] `RATE_LIMIT_STORAGE_URI` points at Redis if you run more than one task
- [ ] HTTPS certificate (ACM) attached to the ALB listener
- [ ] Rotate any key that has ever been pasted into a chat, commit message or
      ticket — including the Groq / Hugging Face keys
