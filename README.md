# MockWithUs

MockWithUs is a full-stack mock interview platform scaffold built with a FastAPI backend and a Next.js frontend.

## Quick Start

1. Copy `backend/.env.example` to `backend/.env`.
2. Copy `frontend/.env.local.example` to `frontend/.env.local`.
3. Start backend + database from root: `docker compose up --build`.
4. Start frontend: `cd frontend && npm install && npm run dev`.
5. Optional DB UI (dev-only): `docker compose --profile devtools up -d adminer` then open `http://localhost:8080`.
6. Optional frontend E2E: `cd frontend && npm run test:e2e`.

## Security Notes

- Code execution isolation strategy: [`backend/docs/code-execution-isolation.md`](backend/docs/code-execution-isolation.md)

## Project Structure

Note: This structure documents source files only (generated folders like `frontend/.next/` and `frontend/node_modules/` are intentionally excluded).

```text
mockwithus/ - Monorepo root containing backend, frontend, and local infra config.
├── .gitignore - Git ignore rules for secrets, build artifacts, and local-only files.
├── README.md - Project overview, setup steps, and file/folder documentation.
├── docker-compose.yml - Local Docker orchestration for backend service and Postgres/pgvector.
├── backend/ - FastAPI backend service, database models, API routers, and tests.
│   ├── .env - Local backend environment variables (not meant for version control).
│   ├── .env.example - Example backend environment file used as a setup template.
│   ├── Dockerfile - Backend container build instructions.
│   ├── ER_DIAGRAM.md - Mermaid ER diagram for backend entities and relationships.
│   ├── alembic.ini - Alembic migration tool configuration.
│   ├── requirements.txt - Python dependencies for backend runtime.
│   ├── uploads/ - Runtime storage directory for uploaded files.
│   ├── tests/ - Backend test suite.
│   │   ├── test_auth.py - Tests for auth flow and token-protected endpoints.
│   │   ├── test_evaluator.py - Tests for evaluation service behavior.
│   │   ├── test_health.py - Tests for API health/status endpoint behavior.
│   │   ├── test_matching.py - Tests for matching service and ranking logic.
│   │   └── test_resume.py - Tests for resume parsing/upload-related behavior.
│   └── app/ - Main backend application package.
│       ├── main.py - FastAPI app initialization, router registration, and lifecycle hooks.
│       ├── config.py - Pydantic settings model and environment-driven app configuration.
│       ├── database.py - SQLAlchemy engine/session setup and DB dependency helpers.
│       ├── core/ - Shared core utilities used across backend modules.
│       │   ├── exceptions.py - Shared/custom exception definitions.
│       │   └── security.py - Auth dependency helpers for current-user resolution.
│       ├── migrations/ - Alembic migration environment and migration scripts.
│       │   ├── README - Alembic migration usage notes.
│       │   ├── env.py - Alembic runtime environment wiring for metadata + DB connection.
│       │   ├── script.py.mako - Template used to generate new migration files.
│       │   └── versions/ - Versioned database migration revisions.
│       │       └── 20260327_000001_initial_schema.py - Initial database schema migration.
│       ├── models/ - SQLAlchemy ORM models representing domain entities.
│       │   ├── __init__.py - Model package exports/import wiring.
│       │   ├── answer.py - ORM model for interview answers submitted by candidates.
│       │   ├── evaluation.py - ORM model for per-answer evaluation feedback/results.
│       │   ├── interview.py - ORM model for interview sessions and metadata.
│       │   ├── job.py - ORM model for job descriptions/roles under interview context.
│       │   ├── question.py - ORM model for interview questions.
│       │   ├── resume.py - ORM model for uploaded resume records.
│       │   ├── types.py - Shared SQLAlchemy custom types and reusable typed columns.
│       │   └── user.py - ORM model for platform users/auth accounts.
│       ├── routers/ - FastAPI route modules grouped by resource.
│       │   ├── __init__.py - Router package export/aggregation setup.
│       │   ├── answers.py - Endpoints for creating and retrieving interview answers.
│       │   ├── audio.py - Endpoints for audio upload/processing workflow.
│       │   ├── auth.py - Authentication endpoints (signup/login/current user).
│       │   ├── evaluations.py - Endpoints exposing evaluation feedback data.
│       │   ├── interviews.py - Endpoints for interview session management.
│       │   ├── jobs.py - Endpoints for job description CRUD/lookup operations.
│       │   └── resumes.py - Endpoints for resume upload and resume data operations.
│       ├── schemas/ - Pydantic request/response contracts for API validation.
│       │   ├── __init__.py - Schema package exports for easier imports.
│       │   ├── auth.py - Auth request/response schemas and token payload models.
│       │   ├── evaluation.py - Evaluation and feedback response schemas.
│       │   ├── interview.py - Interview session request/response schemas.
│       │   └── resume.py - Resume upload/parse request and response schemas.
│       └── services/ - Business/domain service layer called by routers.
│           ├── auth_service.py - User auth and token utility logic.
│           ├── embedding_service.py - Embedding generation abstraction/service boundary.
│           ├── evaluator.py - Answer evaluation orchestration/service logic.
│           ├── matcher.py - Resume-to-job matching logic abstraction.
│           ├── question_generator.py - Interview question generation orchestration.
│           └── resume_parser.py - Resume text extraction/parsing orchestration.
└── frontend/ - Next.js frontend app for authentication, interview flow, and dashboard UI.
    ├── .env.local - Local frontend environment variables (not meant for version control).
    ├── .env.local.example - Example frontend env file used as a setup template.
    ├── package.json - Frontend dependencies, scripts, and package metadata.
    ├── package-lock.json - Exact npm dependency lockfile for reproducible installs.
    ├── next-env.d.ts - Next.js generated TypeScript ambient type declarations.
    ├── next.config.mjs - Next.js runtime/build configuration.
    ├── postcss.config.js - PostCSS plugin configuration (used by Tailwind pipeline).
    ├── tailwind.config.ts - Tailwind CSS theme/content scanning configuration.
    ├── tsconfig.json - TypeScript compiler configuration for the frontend app.
    ├── middleware.ts - Next.js middleware for route protection/request interception.
    ├── public/ - Static assets served directly by Next.js.
    ├── types/ - Shared frontend TypeScript domain and API type definitions.
    │   └── index.ts - Central type exports used across frontend modules.
    ├── lib/ - Frontend utility modules for API/auth/helpers.
    │   ├── api.ts - Fetch client helpers for calling backend endpoints.
    │   ├── auth.ts - Auth token/session helpers for frontend usage.
    │   └── utils.ts - Shared generic utility helpers.
    ├── hooks/ - Reusable React hooks encapsulating client-side logic.
    │   ├── useAuth.ts - Hook for auth state and auth actions.
    │   └── useInterview.ts - Hook for interview flow state and related actions.
    ├── components/ - Reusable UI and feature-level React components.
    │   ├── dashboard/ - Dashboard-specific component module namespace.
    │   ├── interview/ - Interview-specific component module namespace.
    │   ├── layout/ - Shared layout shell/nav structural component namespace.
    │   ├── ui/ - Generic UI primitives/component namespace.
    │   └── upload/ - Upload flow component namespace.
    └── app/ - Next.js App Router pages, route segments, and global styles.
        ├── globals.css - Global styles and Tailwind base/style layer imports.
        ├── layout.tsx - Root app layout wrapper applied across all routes.
        ├── page.tsx - Landing/home page for the application.
        ├── (auth)/ - Grouped auth routes for login/signup pages.
        │   ├── login/ - Login route segment.
        │   │   └── page.tsx - Login page UI and form workflow.
        │   └── signup/ - Signup route segment.
        │       └── page.tsx - Signup page UI and registration workflow.
        ├── dashboard/ - User dashboard route segment.
        │   └── page.tsx - Dashboard page UI for user interview overview.
        └── interview/ - Interview flow routes and nested dynamic segments.
            ├── new/ - Route segment for starting a new interview.
            │   └── page.tsx - New interview setup page (resume/job input flow).
            ├── [sessionId]/ - Dynamic route segment for an active interview session.
            │   └── page.tsx - Interview session page keyed by session ID.
            └── results/ - Results route namespace for completed interviews.
                └── [sessionId]/ - Dynamic route segment for interview results pages.
                    └── page.tsx - Interview results page keyed by session ID.
```
