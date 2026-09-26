# AMAP Requirements & Verification Traceability Matrix

## 1. Adaptive-Worker System Requirements (1–19)

| ID | Requirement Name | Description | PostgreSQL Entity / Implementation | Test Coverage | Status |
| :---: | :--- | :--- | :--- | :--- | :---: |
| **1** | **Worker Capability Profile** | Captures motor tremor, speech diversity, preferred modality, and sensory adaptations. | `worker_capability_profiles` table | `test_worker_capability_profiles_repository.py`, `test_personalization_pipeline.py` | **PASS** |
| **2** | **Personalized Gesture Mapping** | Custom physical gesture action overrides per worker. | `custom_gestures` table | `test_custom_gestures.py`, `test_gesture_pipeline.py` | **PASS** |
| **3** | **Gesture Calibration** | MediaPipe landmark extraction requiring $\ge 5$ consistent physical samples with variance $< 0.45$. | `GestureService.train_custom_gesture` | `test_custom_gestures.py`, `test_phase12_gesture_e2e.py` | **PASS** |
| **4** | **Gesture Performance / Confidence Profile** | Dwell-time accumulation ($100-3000\text{ms}$) with cosine similarity scoring. | `GestureService.process_frame` | `test_gesture_pipeline.py`, `test_phase4_gesture_hardening.py` | **PASS** |
| **5** | **Worker Accessibility Profile** | Theme customization: high contrast, scaled fonts, reduced motion, speech narration. | `user_accessibility_preferences` table | `test_accessibility_compliance.py`, `test_phase10_accessibility_language.py`, `test_phase8_admin_org.py` | **PASS** |
| **6** | **Workflow / Task Requirements** | Modality and physical requirements defined per workflow step. | `workflow_step_responsibilities` table | `test_workflow_steps_repository.py`, `test_master_fr01_to_fr10.py` | **PASS** |
| **7** | **Worker–Task Compatibility** | Deterministic capability-matching score $[0.0, 1.0]$. Incompatible combinations rejected. | `PersonalizationService.calculate_compatibility` | `test_personalization_pipeline.py`, `test_master_fr01_to_fr10.py` | **PASS** |
| **8** | **Suitable Task Recommendations** | Transparent rank-ordered task recommendations with evidence explanation. | `PersonalizationService.recommend_tasks` | `test_personalization_pipeline.py` | **PASS** |
| **9** | **Worker Setup / Assessment** | Onboarding readiness tracking (`not_started` $\to$ `in_progress` $\to$ `ready`). | `worker_readiness` table | `test_readiness_and_lifecycle.py`, `test_readiness_persistence.py`, `test_phase8_admin_org.py` | **PASS** |
| **10** | **Personalized Worker HUD** | Adaptive UI layout adjusting touch target sizes, contrast, and dwell rings. | `WorkerHUD` Next.js component | `frontend/worker/hud/`, `test_phase12_gesture_e2e.py` | **PASS** |
| **11** | **Personalized Voice Commands** | Worker-specific synonym and dialect vocabulary normalization in English and Hindi. | `PersonalizationService.get_worker_voice_vocabulary` | `test_voice_pipeline.py`, `test_phase11_voice_e2e.py` | **PASS** |
| **12** | **Personalized Step Instructions** | Adaptive instruction phrasing based on worker proficiency and accessibility profile. | `PersonalizationService.get_adapted_step_instructions` | `test_personalization_pipeline.py` | **PASS** |
| **13** | **One-Step-at-a-Time Mode** | Sequential step progression with server-side step order verification. | `TaskService.record_step_execution` | `test_phase7_assignments.py`, `test_api_routes.py` | **PASS** |
| **14** | **Accessible Task Assignment** | Supervisor task assignment with tenant isolation and worker capability validation. | `SupervisorService.assign_task` | `test_supervisor_module.py`, `test_phase7_assignments.py` | **PASS** |
| **15** | **Real-Time Assistance** | Worker help ticket creation, supervisor queue triage, response transmission, and resolution. | `assistance_requests` table | `test_assistance_requests_repository.py`, `test_supervisor_module.py` | **PASS** |
| **16** | **Worker Progress Tracking** | Step executions and duration calculations committed to `task_results`. | `task_results` table | `test_task_results_repository.py`, `test_phase7_assignments.py` | **PASS** |
| **17** | **Personalized Emergency Controls** | Software safety interlock halting session and creating urgent supervisor ticket. | `/api/v1/actions/emergency-stop` | `test_emergency_stop.py`, `test_actions_repository.py` | **PASS** |
| **18** | **PostgreSQL Persistence** | Migrations 001..051 applied on PostgreSQL 16 with foreign keys, constraints, and indexes. | `database/migrations/` | `test_database.py`, `scripts/ci_e2e.py` | **PASS** |
| **19** | **Evidence-Based Adaptation Engine** | Transparent mathematical scoring derived from stored data; zero fabricated AI outputs. | `PersonalizationService` | `test_personalization_pipeline.py` | **PASS** |

---

## 2. Functional Requirements (FR01–FR10)

| FR Code | Name | Description | Verification Method | Status |
| :--- | :--- | :--- | :--- | :---: |
| **FR-01** | **Multimodal Capture** | 16kHz audio capture + MediaPipe Hand Landmarker 21 3D landmarks | Automated tests + WASM verification | **PASS** |
| **FR-02** | **Speech-to-Text Processing** | Local Faster-Whisper ASR supporting English and Hindi | `test_speech_to_text_service.py`, `scripts/prefetch_whisper_model.py` | **PASS** |
| **FR-03** | **Hand Gesture Recognition** | Standard heuristic classifiers + custom Euclidean template matching | `test_gesture_pipeline.py`, `test_custom_gestures.py` | **PASS** |
| **FR-04** | **Multimodal Late Fusion** | Temporal late fusion window ($\le 1500\text{ms}$), reinforcing & complementary | `test_multimodal_fusion_hardening.py`, `test_multimodal_processing.py` | **PASS** |
| **FR-05** | **Action Execution Gateway** | Strict separation: Recognition $\neq$ Intent $\neq$ Auth $\neq$ Execution | `test_actions_repository.py`, `test_voice_execution_integration.py` | **PASS** |
| **FR-06** | **Personalization & Adaptation** | Adaptive HUD, custom gestures, bilingual voice aliases | `test_personalization_pipeline.py` | **PASS** |
| **FR-07** | **Supervisor Fleet Monitoring** | Live summary KPIs, worker table, assistance triage queue | `test_supervisor_module.py` | **PASS** |
| **FR-08** | **RBAC & Multi-Tenancy** | Organization-scoped RBAC with 4 roles and tenant isolation | `test_authorization.py`, `test_phase2_auth_rbac.py`, `test_supabase_rls.py` | **PASS** |
| **FR-09** | **Workflow Execution Tracking** | Sequential step progression and `task_results` persistence | `test_workflow_step_executions_repository.py`, `test_phase7_assignments.py` | **PASS** |
| **FR-10** | **Immutable Audit Trail** | `audit_events` and `execution_events` logging all triggers | `test_audit_events_repository.py`, `test_execution_events_repository.py` | **PASS** |
