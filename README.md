# Access Hub

Access Hub is a minimal yet production-minded platform inspired by Netflix ConsoleMe. It centralizes AWS role discovery, self-service access requests, temporary credential vending, and auditing for multi-account AWS environments.

## Architecture Overview

- **API**: FastAPI application backed by SQLAlchemy and Postgres for persistence. Provides endpoints for authentication, catalog, approval workflow, STS credential vending, console federation, and policy linting.
- **Web UI**: React + TypeScript (Vite) frontend that offers a request wizard, catalog search, audit views, and device approval for the CLI.
- **CLI**: Typer-based Python CLI (`hub`) that performs device-code login, lists roles, and emits temporary credentials in both shell export and `credential_process` formats.
- **Infra**: Docker Compose for local development (API, Postgres, Redis, Vite dev server) and Terraform stubs for IAM permission boundaries.

Short-lived credentials are enforced via STS AssumeRole with per-role duration caps. MFA is required (validated through IdP claims) before vending credentials or launching the AWS console. All critical actions (requests, approvals, sessions, console launches) are recorded to an immutable audit log.

## Getting Started

### Prerequisites

- Python 3.11+
- Node 20+
- Docker (optional but recommended for local infra)

### Environment Variables

Create an `.env` in `api/` to configure the API:

```
DATABASE_URL=postgresql+asyncpg://access_hub:access_hub@localhost:5432/access_hub
JWT_SECRET_KEY=change-me
OIDC_ISSUER=https://your-idp.example.com/oauth2/default
OIDC_AUDIENCE=access-hub
CORS_ORIGINS=http://localhost:3000
AWS_REGION=us-east-1
PUBLIC_APP_URL=http://localhost:3000
```

For local development without a real IdP, omit `OIDC_ISSUER` to enable the development JWT mode. Use the seed script to create demo data and users.

### Running with Docker Compose

```bash
cd infra
docker compose up --build
```

This starts Postgres, Redis, the FastAPI service on `http://localhost:8000`, and the Vite dev server on `http://localhost:3000` with API proxying.

### Running Services Manually

1. **API**

   ```bash
   cd api
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

2. **Seed Data**

   ```bash
   cd api
   python -m app.seed
   ```

3. **Web UI**

   ```bash
   cd web
   npm install
   npm run dev
   ```

4. **CLI**

   ```bash
   cd cli
   pip install -r requirements.txt
   cd ..
   ./hub login
   ./hub roles
   ```

### OIDC & Authentication Flow

- Users authenticate via the `/auth/oidc/callback` endpoint. In development mode, POST an ID token generated with the configured `JWT_SECRET_KEY` to create a session.
- CLI login uses the `/auth/device/start` and `/auth/device/activate` endpoints. Run `./hub login` (or add the repository root to your `PATH` for a plain `hub` command) to obtain a device code, approve it via the `/device` page in the web UI, then the CLI stores a short-lived access token locally.

### AWS Integration

The API uses `boto3` to call `AssumeRole`. Configure AWS credentials for the API process (environment variables or IAM role) that permit assuming the target roles. The console federation URL is built with embedded temporary credentials to avoid long-lived access keys.

### CLI Credential Process

Add the following profile to your `~/.aws/config` to leverage the CLI credential-process integration:

```
[profile access-hub]
credential_process = ./hub credential-process arn:aws:iam::123456789012:role/AccessHubReadOnly
```

Run `aws --profile access-hub sts get-caller-identity` to confirm.

### Testing

```bash
cd api
pytest
```

### Security Considerations

- MFA is enforced by checking the configured OIDC MFA claim. Without MFA the API denies credential vending and console access.
- Approval workflow is deny-by-default; only approved requests can vend credentials.
- Policy linting rejects wildcard actions/resources unless a break-glass keyword is present in the justification and toggled by the approver.
- JWT cookies are HttpOnly, Secure, and SameSite=Strict to mitigate CSRF.
- Audit log captures requests, approvals, session issuance, and console launches for traceability.

### Future Enhancements

- Integrate with AWS Organizations or IAM Identity Center for automatic account/role discovery.
- Expand the worker queue for Slack/email notifications on approvals.
- Add OpenTelemetry tracing and structured JSON logging.

## Repository Structure

```
api/        FastAPI backend
web/        React frontend
cli/        Python Typer CLI
infra/      Docker Compose + Terraform stubs
```
