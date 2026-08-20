AMAP --- Master Project Specification

Project: AMAP --- Assistive Multimodal Accessibility Platform
Document: Master Specification / Single Source of Truth
Status: Draft --- Architecture Foundation
Version: 0.1.0
Last Updated: 2026-08-16

1. Purpose of This Document

This document is the single source of truth for the AMAP project.

All developers, AI assistants, IDE agents, documentation, architecture
decisions, API contracts, database design, testing plans, and deployment
work must follow this specification.

If an implementation conflicts with this document, the implementation
must not silently redefine the architecture. The conflict must be
identified and resolved through an explicit architecture decision.

Core rule

Do not invent project requirements, technologies, workflows, or
architectural changes without checking this specification first.

2. Project Definition

AMAP is a multimodal assistive workplace platform designed to reduce
unnecessary interaction difficulty for workers by allowing digital
workplace systems to be controlled through:

Gesture-based interaction

Voice interaction

Conventional user-interface interaction

AMAP provides three major product experiences:

Worker

Admin

Organization

The platform connects organization-level work configuration with
worker-level personalized interaction.

3. Core Problem

Traditional digital workplace interfaces can require workers to use
interaction methods that may be difficult, inefficient, or physically
demanding for them.

The problem AMAP addresses is not necessarily the worker's ability to
perform the real-world job.

The problem may be the digital interaction layer required to operate the
workplace software.

AMAP therefore aims to make the interaction layer more accessible,
flexible, and personalized.

Core principle

The system should adapt to the worker's interaction capabilities and
preferences rather than unnecessarily forcing the worker to adapt to a
rigid digital interface.

4. Core AMAP Concept

The core AMAP loop is:

Organization defines the environment.

Admin defines the work.

Worker performs the work.

AMAP observes interaction performance.

AMAP adapts the interaction when consistent difficulty is detected.

The worker continues working with the improved configuration.

Core loop

Organization → Work structure → Admin configuration → Worker assignment
→ Worker interaction → Action execution → Feedback → Performance data →
Personalization → Improved interaction

5. Product Sides

5.1 Worker Side

The worker is the primary end user of the assistive interaction system.

The worker can:

Access assigned work

View task guidance

Perform digital task actions

Use gesture interaction

Use voice interaction

Use conventional UI

Receive visual and voice feedback

Recover from interaction errors

Request assistance

Work using personalized interaction settings

Worker phases

Phase 1 --- Capability Discovery

Purpose:

Understand how the worker can comfortably interact with the system.

Phase 2 --- Job & Work Configuration

Purpose:

Match job/task requirements with the worker's interaction capabilities
and configure the appropriate interaction methods.

Phase 3 --- Work Execution

Worker login/work session

Personalized workspace

Task assignment/selection

Task guidance

Gesture + voice input

Multimodal command processing

Intent/action recognition

Action validation

Action execution

Real-time feedback

Error handling and recovery

Task completion

Work session data collection

Phase 4 --- Adaptation & Continuous Personalization

Purpose:

Detect repeated interaction difficulty and adjust the interaction
configuration to reduce effort and improve reliability.

The adaptation loop is:

Actual usage → Difficulty detection → Problem identification →
Adaptation decision → Gesture/voice adjustment → Worker re-test →
Improvement evaluation → Worker feedback → Configuration update →
Continuous monitoring

Personalization principles

Do not change configuration because of one isolated failure.

Use repeated evidence/patterns before automatic adaptation.

Balance ease of interaction with recognition reliability.

High-risk actions may require stricter recognition and/or
confirmation.

Personalization may adjust gesture sensitivity, movement tolerance,
recognition thresholds, voice interaction settings, confirmation
behavior, and other appropriate interaction parameters.

Partial movement may be supported when the worker's consistent
movement pattern demonstrates reliable intent.

Personalization should minimize physical and cognitive effort while
avoiding accidental activation.

6. Admin Side

The Admin manages operational work configuration and worker operations.

Admin flow

Admin Login

Admin Dashboard

Organization/Department Context

Job/Role Management

Job Responsibility Definition

Real-World Task Definition

Task & Workflow Creation

Action Identification

Action Requirement Analysis

Gesture & Voice Mapping

Action Risk Configuration

AI Template / Workflow Generation

Admin Review & Modification

Worker Assignment

Worker Monitoring

Worker Assistance / Support

Worker Configuration Monitoring

Task / Workflow Updates

Exception / Escalation Management

Admin Analytics

Access & Permission Management

Audit Logs

Accessibility Configuration

System Notifications & Alerts

Important Admin principle

AI-generated task/workflow configuration is a proposal.

The Admin reviews, modifies, and approves it before it becomes active.

AI must not be treated as the authority for organization policy or
action execution.

Worker monitoring principle

Admin monitoring should focus on operational state, such as:

Active/inactive status

Current task

Current step

Task progress

Errors/retries

Assistance requests

Configuration issues

Task completion

AMAP should not require continuous raw camera surveillance of workers.

7. Organization Side

The Organization provides the company-level structure and governance.

Organization flow

Organization Setup

Organizational Structure

Workforce Lifecycle

Accessibility Governance

Accommodation Governance

Organization Policies

Access & Permission Governance

Accessibility & Workforce Training

Organization Monitoring

Organization Analytics

Compliance & Audit

Integrations

Notifications & Alerts

Organization principle

The organization defines policies, structure, governance, and available
accessibility support.

The organization should not arbitrarily define a worker's physical
capability.

Worker-specific configuration is personalized using the worker's
capabilities, preferences, performance, and permitted organizational
settings.

8. Interaction Architecture

AMAP supports three interaction modes:

Gesture

Voice

Conventional UI

All three should ultimately map into a common application intent/action
layer.

Conceptual flow

Input → Recognition → Multimodal Processing → Intent/Action Recognition
→ Validation → Execution → Feedback

Gesture

Camera → Hand/body/movement detection → Gesture recognition →
Movement/stability analysis → Confidence → Intent/action

Voice

Microphone → Speech recognition → Command representation → Intent/action

Conventional UI

User interaction → Application intent/action

Important terminology decision

AMAP does not assume or require Indian Sign Language.

The project terminology is:

Gesture-based interaction

No ISL-specific dataset, vocabulary, or implementation should be
introduced unless explicitly approved later.

9. Multimodal Architecture

Gesture and voice may be used independently or together.

Examples:

Voice only

Voice: "Open shipment 10482"

→ Intent: OPEN_SHIPMENT → Target: 10482

Gesture only

Gesture: Open/select gesture

→ Intent: OPEN_SHIPMENT

Hybrid

Gesture: Select target

Voice: "Open this"

→ Intent: OPEN_SHIPMENT → Target: selected object

Conflict

If gesture and voice produce conflicting commands:

Do not blindly execute.

Possible outcomes:

Resolve from context if unambiguous

Ask for clarification

Require confirmation

Reject unsafe/conflicting input

10. Intent and Action Pipeline

The distinction between stages must remain clear.

Input

What did the system receive?

Multimodal processing

How do the available input signals relate?

Intent/action recognition

What does the worker intend to do?

Action validation

Is the intended action valid, permitted, safe, and appropriate in the
current task?

Action execution

Perform the approved application operation.

Feedback

Tell the worker what happened.

11. AI Boundaries

AI/ML is a component of AMAP, not the entire application.

AI/ML can:

Assist gesture recognition

Assist voice processing

Assist intent interpretation

Generate workflow/task proposals for Admin

Provide AI assistant responses

Analyze patterns for personalization

Recommend adaptations

Deterministic application logic must handle:

Authentication

Authorization

Permissions

Business rules

Action validation

High-risk action controls

Database writes

Workflow state transitions

Final action execution

Core safety principle

AI may recognize, recommend, summarize, or assist; the application
remains responsible for authorization, validation, and execution.

An LLM must not directly receive unrestricted authority to modify the
database or execute sensitive actions.

12. AI Assistant

The AI assistant is a support component.

Potential uses:

Worker

Explain the current task

Answer contextual questions

Provide guidance

Explain errors

Provide accessible feedback

Admin

Convert natural-language work descriptions into structured
task/workflow proposals

Suggest actions

Suggest interaction mappings

Explain configuration options

Organization

Summarize organization-level information

Explain policies or system configuration when authorized

AI assistant boundary

The AI assistant does not bypass permissions or validation.

13. Architecture Direction

AMAP will initially use a unified platform with modular internal
architecture.

Decision

Do not start with a large microservice architecture.

Use a modular application structure so that components can be separated
later if actual scale or technical requirements justify it.

Major layers

Presentation

API / Real-time

Backend business logic

AI/ML

Data/storage

Security

Observability

Deployment/infrastructure

Conceptual architecture

Users → Worker/Admin/Organization interfaces → Frontend → API /
WebSocket layer → Backend → AI/ML + Business Logic + Real-time →
PostgreSQL / Redis / Object Storage → External AI/voice services where
required

14. Technology Direction

The following is the current proposed stack. It remains subject to final
technology review before implementation.

Frontend

Next.js

React

TypeScript

Backend

Python

FastAPI

Database

PostgreSQL

Cache / transient state / event distribution

Redis

Object storage

S3-compatible storage / Supabase Storage

Gesture processing

OpenCV

MediaPipe or equivalent landmark/vision tooling

Custom gesture recognition model where required

LLM

Gemini API, subject to final evaluation

Authentication

Managed authentication solution initially, with backend
authorization

Real-time

WebSockets

Containers

Docker

CI/CD

GitHub Actions

Observability

OpenTelemetry

Error tracking system such as Sentry

These are architecture candidates, not permission to add packages
without review.

15. Database Direction

PostgreSQL is the proposed source of truth.

Major conceptual entities include:

Organization

Department

User

Worker

Admin

Role

Permission

Job

Responsibility

Task

Workflow

Workflow Step

Action

Action Requirement

Interaction Configuration

Gesture Configuration

Voice Configuration

Worker Capability Profile

Worker Personalization

Work Session

Interaction Event

Task Result

Assistance Request

Notification

Audit Event

Exact schema and relationships must be designed before application
implementation.

16. Multi-Tenancy / Organization Isolation

AMAP must prevent one organization from accessing another organization's
data.

Conceptually:

Organization → Users → Departments → Jobs → Tasks → Workers →
Configurations → Sessions → Analytics

Every organization-owned resource must have an explicit ownership
boundary.

Authorization must be enforced in backend logic and at the data-access
layer where appropriate.

17. Authentication vs Authorization

These are separate concerns.

Authentication

Who is the user?

Authorization

What is the user allowed to access or perform?

AMAP must use role and organization context when determining access.

Example:

Worker: - Own profile - Assigned work - Own interaction configuration -
Authorized assistance functions

Admin: - Operational management within assigned scope

Organization-level administrator: - Organization governance and broader
management

Exact permission matrix must be finalized before implementation.

18. API Direction

Normal application operations will use REST-style APIs.

Real-time state/events will use WebSockets where appropriate.

API contracts must be defined before frontend/backend modules are
developed independently.

Initial namespace direction:

/api/v1/auth /api/v1/organizations /api/v1/departments /api/v1/users
/api/v1/workers /api/v1/jobs /api/v1/tasks /api/v1/workflows
/api/v1/actions /api/v1/configurations /api/v1/sessions
/api/v1/analytics /api/v1/notifications /api/v1/ai

Real-time endpoints may include:

/ws/worker /ws/admin /ws/notifications

Exact endpoint names are not frozen until API contract design.

19. Real-Time Requirements

Real-time communication may be required for:

Worker status

Task progress

Action feedback

Assistance requests

Admin monitoring

Notifications

Configuration updates

Do not introduce real-time infrastructure where normal request/response
communication is sufficient.

20. Background Processing

Background processing may handle:

Analytics aggregation

Long-running AI processing

Report generation

Notifications

Adaptation analysis

Non-critical post-task processing

Worker-critical actions should not unnecessarily wait for background
processing.

21. Personalization Architecture

Personalization is based on observed interaction performance and worker
feedback.

Potential signals include:

Recognition confidence

Movement stability

Movement range

Partial movement patterns

Voice recognition success

Retry frequency

Correction frequency

Task completion time

Interaction switching

Assistance requests

Worker feedback

Important

Raw metrics alone do not automatically mean configuration changes.

AMAP should identify consistent patterns and evaluate whether adaptation
improves the interaction.

22. Privacy Direction

AMAP should minimize unnecessary collection of sensitive data.

For example, gesture interaction should not require continuous storage
of raw camera footage.

Prefer structured interaction events such as:

Gesture identifier

Confidence

Timestamp

Task/action context

Retry count

Recognition outcome

Raw media should only be stored when there is a defined, justified
requirement and appropriate permission/retention policy.

Exact retention policies must be finalized before production deployment.

23. Security Requirements

Security is cross-cutting.

Required areas include:

Secure authentication

Authorization

Organization isolation

Input validation

Rate limiting

Secure secrets management

HTTPS/TLS

Audit logging

Secure API design

Dependency/security scanning

Least privilege

Safe AI integration

Data protection

Error handling without sensitive information leakage

24. Accessibility Requirements

Accessibility is a core product requirement, not an optional feature.

The interface should consider:

Perceivable content

Operable controls

Understandable interactions

Robust implementation

Keyboard accessibility where applicable

Screen reader support

High contrast

Large interaction targets

Clear focus states

Voice feedback

Error recovery

Accessible forms

Appropriate feedback

Reduced unnecessary interaction effort

The project should use an appropriate accessibility standard as a
reference during implementation and testing.

25. Monitoring and Observability

AMAP should distinguish:

Worker operational monitoring

What is happening with the worker/task?

Configuration monitoring

Is the worker's interaction configuration working effectively?

Organization analytics

What are the broader operational/accessibility trends?

System observability should include:

Logs

Metrics

Traces

Error tracking

Alerts

Monitoring must not become unnecessary worker surveillance.

26. Testing Strategy

Testing must cover multiple layers.

Software

Unit tests

Integration tests

API tests

End-to-end tests

AI/ML

Recognition accuracy

Precision

Recall

F1

Confusion matrix

False activation rate

False rejection rate

Latency

Robustness

Accessibility

Keyboard testing where applicable

Screen reader testing

Contrast

Target sizes

Focus behavior

Error recovery

Voice interaction

User/system evaluation

Task completion rate

Task completion time

Interaction error rate

Retry rate

Assistance requests

Worker-reported difficulty

Improvement after adaptation

27. CI/CD Direction

GitHub will be the source-control platform.

Initial CI/CD direction:

Code → Pull Request → Lint/type checks → Tests → Security checks → Build
→ Deployment

No code should be merged into the main branch without passing required
automated checks once CI is established.

28. Development Rules for AI Assistants

Every AI assistant working on AMAP must:

Read the relevant specification before coding.

Respect the existing folder structure.

Avoid changing architecture without an explicit decision.

Avoid changing database structure without coordination.

Follow API contracts.

Avoid introducing unnecessary dependencies.

Explain assumptions.

Identify conflicts instead of silently resolving them.

Add/update tests for behavior it changes.

Document important architectural changes.

Never expose secrets.

Never commit .env files containing real credentials.

Never bypass authorization for convenience.

Never give an LLM uncontrolled database/action access.

Keep modules loosely coupled.

29. Source of Truth Hierarchy

When information conflicts, use this order:

Explicit approved project decision

MASTER_SPEC.md

Architecture decision records

API contract

Database specification

Module documentation

Implementation

AI-generated assumptions

Implementation must not silently override higher-level decisions.

30. Architectural Change Process

If a developer or AI assistant wants to change an established decision:

Required process

Identify current decision.

Explain the proposed change.

Explain why the current approach is insufficient.

Identify affected modules.

Compare alternatives.

Identify migration/rework cost.

Obtain project approval.

Update MASTER_SPEC.md.

Add/update DECISIONS.md.

Update affected implementation.

31. Current Explicit Decisions

DEC-001

AMAP has three product sides: - Worker - Admin - Organization

DEC-002

AMAP supports: - Gesture - Voice - Conventional UI

DEC-003

AMAP does not assume ISL/Indian Sign Language.

DEC-004

Worker personalization should reduce unnecessary interaction difficulty.

DEC-005

Partial movement/tolerance may be supported based on evidence and
reliability.

DEC-006

AI does not directly bypass backend validation or authorization.

DEC-007

Admin AI-generated workflows require Admin review/approval.

DEC-008

Worker monitoring is operational monitoring, not continuous raw camera
surveillance.

DEC-009

AMAP initially uses a unified platform with modular architecture rather
than unnecessary microservices.

DEC-010

PostgreSQL is the proposed primary source of truth.

DEC-011

The project will use one Master Specification as the source of truth for
all AI assistants and developers.

32. Explicitly Not Yet Frozen

The following must be decided before implementation of the relevant
module:

Exact primary worker persona

Exact capstone MVP

Exact supported gesture vocabulary

Gesture dataset/source

Gesture recognition model

Voice/STT provider

TTS provider

Exact Gemini usage

Exact personalization algorithm

Exact database schema

Exact API contracts

Exact RBAC matrix

Exact authentication provider

Exact deployment provider

Exact data retention policy

Exact compliance requirements

Exact testing dataset and evaluation protocol

These should not be guessed by individual AI assistants.

33. MVP Principle

AMAP must demonstrate a complete end-to-end workflow rather than many
disconnected features.

The MVP should prove:

Worker → Login → Receive task → Interact through gesture/voice/UI →
Intent recognized → Action validated → Action executed → Feedback
received → Task completed → Interaction data recorded →
Personalization/adaptation demonstrated

Admin → Configure task/workflow → Assign worker → Monitor worker/task →
Handle assistance/exception

Organization → Configure organizational structure → Manage
governance/access → View organization-level information

Anything outside the minimum end-to-end demonstration should be
evaluated for scope before implementation.

34. Implementation Order

The planned implementation sequence is:

Master specification

Architecture decisions

Database design

API contracts

Repository/project configuration

Authentication and authorization foundation

Organization foundation

Admin foundation

Worker foundation

Task/workflow engine

Gesture pipeline

Voice pipeline

Multimodal intent pipeline

Action validation/execution

Personalization

Admin monitoring

Organization analytics

Testing

Security hardening

Observability

CI/CD

Deployment

Capstone documentation

35. Definition of Done

A feature is not considered complete because code compiles.

A feature is complete when:

Requirements are defined.

Architecture is consistent.

API contract is defined where applicable.

Database changes are documented.

Authorization is implemented.

Error handling exists.

Tests exist.

Accessibility considerations are addressed.

Documentation is updated.

No known cross-module contract is broken.

CI checks pass.

36. Project Philosophy

AMAP should be built as a real software system.

The project should consistently ask:

Why is this needed?

Why this approach?

Why not another approach?

What happens internally?

What are the trade-offs?

What happens if it fails?

How do we test it?

How does it affect the worker?

Can the worker perform the interaction with less effort?

Does the system improve without sacrificing reliability?

The final system should demonstrate not only functionality but also
sound engineering decisions.

END OF MASTER SPECIFICATION
