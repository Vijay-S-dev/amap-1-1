# AMAP Backend Specification

**Status:** FROZEN FOUNDATION CONTRACT  
**Version:** 0.1  
**Backend:** Python + FastAPI

---

## 1. Purpose

This document defines the AMAP backend foundation.

The backend is responsible for:

- HTTP/API request handling
- application configuration
- request validation
- authorization enforcement
- business logic
- service orchestration
- database integration
- logging
- error handling
- future integration with interaction and AI services

This document defines the backend foundation only.

It does not define the final database schema. The database schema is governed by `docs/DATABASE.md`.

---

## 2. Technology Decisions

The following decisions are approved:

```text
Language: Python
Framework: FastAPI
Database: PostgreSQL
Database development: Docker
Version control: Git + GitHub
Development OS: Windows

## 3. Backend Responsibilities :
Backend Responsibilities
Client Request
      ↓
Request Validation
      ↓
Authentication
      ↓
Authorization
      ↓
Organization Scope Validation
      ↓
Business Logic
      ↓
Database / Service Operations
      ↓
Response

4. Critical Security Boundary

AMAP must preserve:

Recognition
    ≠
Intent
    ≠
Authorization
    ≠
Execution

The future interaction flow is:

Gesture / Voice / UI
        ↓
Recognition
        ↓
Intent
        ↓
Validation
        ↓
Authorization
        ↓
Confirmation if required
        ↓
Action Execution

Recognition confidence must never grant permission.

The backend must remain the authority for authorization and execution validation.

5. Organization Isolation

AMAP is organization-scoped.

The backend must not rely on frontend filtering for tenant/organization isolation.

The future authorization flow is:

Authentication
      ↓
User Identity
      ↓
Role Assignment
      ↓
Permission
      ↓
Organization Scope
      ↓
Resource Validation
      ↓
Allow / Deny
6. Current Backend Scope

The first backend implementation phase includes:

Python environment
Dependency management
FastAPI application
Application entry point
Configuration system
Environment variable handling
API versioning foundation
Health endpoint
Centralized error handling
Logging foundation
Middleware foundation
CORS structure
Test framework
Backend run documentation
7. Current Backend Out of Scope

The backend foundation phase must NOT implement:

Database tables
Database migrations
Final ORM models
Authentication flows
RBAC implementation
Worker business APIs
Admin business APIs
Organization business APIs
Workflow business logic
Task business logic
Gesture recognition
Voice recognition
Intent recognition
Personalization logic
Production deployment

These will be implemented in later approved phases.

8. Repository Ownership

The backend engineer primarily owns:

backend/
├── app/
├── middleware/
├── models/
├── routes/
├── services/
├── tests/
└── utils/

Backend-specific configuration files may also be created where required.

The backend engineer must not modify database migrations or database infrastructure without coordination.

9. Application Structure Principles

The backend structure must support separation between:

Routes
    ↓
Request / Response handling


Services
    ↓
Business logic


Models
    ↓
Application / future database representations


Middleware
    ↓
Cross-cutting request processing


Utils
    ↓
Reusable utilities

Do not place all application logic inside route handlers.

Do not create premature business services before their specifications exist.

10. Configuration Rules

Configuration must:

come from environment/configuration sources
avoid hard-coded secrets
keep .env out of Git
provide .env.example
validate required settings appropriately
separate development and production concerns where needed

Never commit:

Passwords
Database credentials
API keys
Access tokens
Secrets
11. API Foundation

The backend should establish a versioning structure such as:

/api/v1/

This is a routing foundation only.

Final business endpoint paths must not be invented before API contracts are defined.

12. Health Endpoint

The initial backend must provide a basic health endpoint.

The endpoint should verify that the FastAPI application is running.

Database health must remain separate until backend-database integration.

13. Error Handling

The backend must provide centralized error handling.

Requirements:

consistent error responses
no unnecessary internal stack traces exposed
no secrets exposed
appropriate HTTP status codes
structured logging of server-side failures

Detailed final API error contracts may be defined later.

14. Logging

The backend foundation must support structured application logging.

Do not log:

Passwords
Secrets
Access tokens
Database credentials
Raw sensitive interaction data

Logging must support future debugging and operational monitoring.

15. Middleware Foundation

The backend may establish middleware foundations for future:

Request IDs
Logging
Security headers
CORS
Authentication
Organization context
Rate limiting

Only foundational middleware should be implemented initially.

Do not prematurely implement business-specific middleware.

16. CORS

CORS configuration must be environment-driven.

Do not permanently allow unrestricted origins in production configuration.

Development behavior and production behavior must remain configurable.

17. Database Integration

The backend will eventually connect to PostgreSQL.

Until the database foundation is complete:

backend must remain independently runnable
health checks must not require the database
backend engineers must not invent final database tables

Database integration begins only after the PostgreSQL schema and migration approach are approved.

18. Testing

The backend foundation must establish automated testing.

Initial tests should verify:

Application starts
Health endpoint responds
Basic error handling behaves correctly

Future tests will include:

Integration tests
Authorization tests
Organization isolation tests
API contract tests
Security tests
19. Backend Engineer Rules

The backend engineer must:

Preserve this document.
Not redesign database architecture.
Not invent undocumented business APIs.
Not implement authentication/RBAC prematurely.
Keep the application independently runnable.
Use environment-based configuration.
Avoid committing secrets.
Keep route handlers thin.
Add tests for implemented foundation behavior.
Report conflicts instead of silently changing architecture.
20. Conflict Reporting

If implementation cannot safely proceed, report:

ARCHITECTURE QUESTION

CURRENT CONTRACT:
What the project documents currently specify.

PROBLEM:
Why this prevents safe implementation.

OPTIONS:
Option A
Option B

RECOMMENDATION:
Recommended solution and reason.

Do not silently modify the architecture.

21. Backend Foundation Completion Criteria

The foundation is complete when:

Python environment works              [ ]
Dependencies install successfully     [ ]
FastAPI application starts            [ ]
Configuration loads                   [ ]
API versioning structure exists       [ ]
Health endpoint works                 [ ]
Centralized error handling exists     [ ]
Logging works                         [ ]
Test framework works                  [ ]
Foundation tests pass                 [ ]
No database required to start         [ ]
No secrets committed                  [ ]
Run instructions documented           [ ]
22. Status

Backend foundation contract: APPROVED FOR IMPLEMENTATION

The next backend phase after foundation completion is:

Database integration
        ↓
Authentication
        ↓
Authorization / RBAC
        ↓
Organization-scoped business APIs

These phases require separate implementation approval and must not be silently started during the foundation phase.



---


# 3. Important: avoid conflicts


Now your two real source-of-truth files are:


```text
docs/
├── DATABASE.md  🔒 Database contract — YOU
└── BACKEND.md   🔒 Backend foundation contract — YOUR MATE

And ownership is clean:

YOU
──────────────────────────
docs/DATABASE.md
database/
deployment/docker/
docker-compose.yml
database infrastructure




YOUR MATE
──────────────────────────
docs/BACKEND.md
backend/
backend foundation
backend tests
