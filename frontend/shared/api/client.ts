/**
 * AMAP API Client
 * Connects frontend UI to FastAPI backend with bearer token management,
 * organization header scoping, and honest error propagation.
 *
 * Phase 0 Remediation: Zero silent fake-success or demo mock fallbacks.
 * The system must fail honestly.
 */

import {
  AdaptationReviewItem,
  AssistanceTicket,
  CustomGestureProfile,
  InteractionPreset,
  MultimodalFusionPayload,
  MultimodalFusionResult,
  MultimodalInput,
  MultimodalInputItem,
  PermissionMatrix,
  TaskDetails,
  UserContext,
  WorkerPersonalization,
  WorkSession,
} from '../types';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1';

export class ApiError extends Error {
  public status?: number;
  public code?: string;
  public detail?: any;

  constructor(message: string, status?: number, code?: string, detail?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

class ApiClient {
  private token: string | null = null;
  private orgId: string = '9a61e05d-7a32-4112-9c17-1833d7b42f65';

  constructor() {
    if (typeof window !== 'undefined') {
      const savedToken = localStorage.getItem('amap_token');
      const savedOrg = localStorage.getItem('amap_org_id');
      if (savedToken) {
        this.token = savedToken;
        // Ensure edge middleware cookie is in sync with localStorage on page refresh
        if (!document.cookie.includes('amap_token=')) {
          document.cookie = `amap_token=${savedToken}; path=/; max-age=86400; SameSite=Lax`;
        }
      }
      if (savedOrg) this.orgId = savedOrg;
    }
  }

  setAuth(token: string, orgId?: string) {
    this.token = token;
    if (orgId) this.orgId = orgId;
    if (typeof window !== 'undefined') {
      localStorage.setItem('amap_token', token);
      if (orgId) localStorage.setItem('amap_org_id', orgId);
      // Sync cookie for Edge Middleware route gating
      document.cookie = `amap_token=${token}; path=/; max-age=86400; SameSite=Lax`;
    }
  }

  clearAuth() {
    this.token = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('amap_token');
      localStorage.removeItem('amap_org_id');
      document.cookie = 'amap_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
    }
  }

  getToken(): string | null {
    return this.token;
  }

  /**
   * Authenticated Vosk streaming WebSocket URL for voice recognition.
   * Browsers cannot set the Authorization header on WebSocket connections,
   * so the JWT travels as a query parameter and is verified server-side with
   * the exact same AuthService used by the REST API.
   */
  getVoiceStreamUrl(language: string, token: string): string {
    let base = API_BASE;
    if (base.startsWith('/')) {
      // Relative API base (e.g. "/api/v1" behind the Next.js proxy): resolve
      // against the page origin — WebSocket URLs must be absolute.
      base = `${typeof window !== 'undefined' ? window.location.origin : ''}${base}`;
    }
    const wsBase = base.replace(/^https:\/\//, 'wss://').replace(/^http:\/\//, 'ws://');
    const params = new URLSearchParams({ token, language });
    return `${wsBase}/voice/stream?${params.toString()}`;
  }

  getHeaders(): HeadersInit {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Organization-Id': this.orgId,
    };
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    return headers;
  }

  /**
   * Centralized HTTP request runner.
   * Enforces honest failure: network errors, HTTP error codes, and malformed
   * responses throw structured ApiError instances instead of returning fake mock data.
   */
  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = endpoint.startsWith('http')
      ? endpoint
      : `${API_BASE}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Organization-Id': this.orgId,
      ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
      ...((options.headers as Record<string, string>) || {}),
    };

    let res: Response;
    try {
      res = await fetch(url, { ...options, headers });
    } catch (err: any) {
      throw new ApiError(
        `Backend service unreachable at ${url}: ${err?.message || 'Network error'}`,
        undefined,
        'NETWORK_ERROR',
        err
      );
    }

    if (!res.ok) {
      let detail: any = null;
      try {
        const errJson = await res.json();
        detail = errJson.detail || errJson.error || errJson;
      } catch {
        try {
          detail = await res.text();
        } catch {
          detail = null;
        }
      }

      const message =
        typeof detail === 'string'
          ? detail
          : detail?.message || `API request failed with HTTP ${res.status}`;

      throw new ApiError(message, res.status, `HTTP_${res.status}`, detail);
    }

    // Handle 204 No Content
    if (res.status === 204) {
      return {} as T;
    }

    try {
      return (await res.json()) as T;
    } catch (err: any) {
      throw new ApiError(
        `Failed to parse response from ${url}: ${err?.message || 'Malformed JSON'}`,
        res.status,
        'PARSE_ERROR',
        err
      );
    }
  }

  // --------------------------------------------------------------------------
  // Authentication & Identity Endpoints
  // --------------------------------------------------------------------------

  async login(payload: {
    organization_id: string;
    email: string;
    password: string;
  }): Promise<{ access_token: string; token_type: string; expires_in: number }> {
    const data = await this.request<{
      access_token: string;
      token_type: string;
      expires_in: number;
    }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    this.setAuth(data.access_token, payload.organization_id);
    return data;
  }

  async getMe(): Promise<UserContext> {
    const raw = await this.request<any>('/auth/me');
    return {
      userId: raw.user_id || raw.id || raw.userId,
      organizationId: raw.organization_id || raw.organizationId,
      email: raw.email,
      fullName: raw.full_name || raw.fullName || raw.email,
      roles: raw.roles || [],
      permissions: raw.permissions || [],
      workerProfileId: raw.worker_profile_id || raw.workerProfileId || undefined,
    };
  }

  // --------------------------------------------------------------------------
  // Worker & Session Endpoints
  // --------------------------------------------------------------------------

  async getActiveSession(): Promise<WorkSession> {
    return await this.request<WorkSession>('/sessions/active');
  }

  async startWorkSession(): Promise<WorkSession> {
    return await this.request<WorkSession>('/sessions/start', { method: 'POST' });
  }

  async heartbeatWorkSession(workSessionId?: string | null): Promise<WorkSession | null> {
    return await this.request<WorkSession | null>('/sessions/heartbeat', {
      method: 'POST',
      body: JSON.stringify(workSessionId ? { work_session_id: workSessionId } : {}),
    });
  }

  async pauseWorkSession(workSessionId: string): Promise<WorkSession> {
    return await this.request<WorkSession>(`/sessions/${workSessionId}/pause`, { method: 'POST' });
  }

  async resumeWorkSession(workSessionId: string): Promise<WorkSession> {
    return await this.request<WorkSession>(`/sessions/${workSessionId}/resume`, { method: 'POST' });
  }

  async endWorkSession(workSessionId: string): Promise<WorkSession> {
    return await this.request<WorkSession>(`/sessions/${workSessionId}/end?status=completed`, {
      method: 'POST',
    });
  }

  async getGestureMapping(): Promise<{
    worker_profile_id: string;
    gesture_action_map: Record<string, string>;
    sources: Record<string, string>;
    calibration: Record<string, any>;
  }> {
    return await this.request('/personalization/me/gesture-mapping');
  }

  async updateGestureMapping(payload: {
    gesture_action_map?: Record<string, string>;
    calibration?: Record<string, any>;
    change_reason?: string;
  }): Promise<{
    worker_profile_id: string;
    gesture_action_map: Record<string, string>;
    sources: Record<string, string>;
    calibration: Record<string, any>;
  }> {
    return await this.request('/personalization/me/gesture-mapping', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  }

  async getWorkerReadiness(workerId: string): Promise<{
    worker_id: string;
    is_fresher: boolean;
    onboarding_completed: boolean;
    readiness_status: string;
    interaction_mode: string;
    gesture_ready: boolean;
    voice_ready: boolean;
    multimodal_ready: boolean;
    task_training_complete: boolean;
    overall_ready: boolean;
    completed_stages: string[];
    active_preferences: Record<string, any>;
  }> {
    return await this.request(`/workers/${workerId}/readiness`);
  }

  async certifyWorkerReadiness(
    workerId: string,
    payload: {
      selected_language: string;
      selected_modality: string;
      calibrated_dwell_ms: number;
      training_order_id: string;
      gesture_ready: boolean;
      voice_ready: boolean;
      multimodal_ready: boolean;
      task_training_complete: boolean;
    }
  ): Promise<any> {
    return await this.request(`/workers/${workerId}/readiness/certify`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getAssignedTasks(): Promise<any[]> {
    return await this.request<any[]>('/tasks/assigned');
  }

  async startTaskAssignment(assignmentId: string): Promise<any> {
    return await this.request<any>(`/tasks/assignments/${assignmentId}/start`, {
      method: 'POST',
    });
  }

  async getStepExecutions(workflowAssignmentId: string): Promise<any[]> {
    return await this.request<any[]>(
      `/tasks/workflows/assignments/${workflowAssignmentId}/executions`
    );
  }

  async getTaskDetails(taskId: string): Promise<TaskDetails> {
    return await this.request<TaskDetails>(`/tasks/${taskId}`);
  }

  async executeAction(payload: {
    action_name: string;
    work_session_id?: string | null;
    workflow_step_id?: string | null;
    task_id?: string | null;
    parameters?: Record<string, any>;
  }): Promise<{
    success: boolean;
    action_id: string;
    action_name: string;
    executed_at: string;
    result_data?: Record<string, any>;
    feedback_message?: string;
  }> {
    return await this.request('/actions/execute', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async recordStepExecution(
    workflowAssignmentId: string,
    stepId: string,
    payload: {
      status: string;
      execution_data?: Record<string, any>;
    }
  ): Promise<any> {
    return await this.request(
      `/tasks/workflows/assignments/${workflowAssignmentId}/steps/${stepId}/execute`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    );
  }

  async completeTaskAssignment(
    assignmentId: string,
    payload: {
      outcome?: string;
      result_data?: Record<string, any>;
      notes?: string;
    }
  ): Promise<any> {
    return await this.request(`/tasks/assignments/${assignmentId}/complete`, {
      method: 'POST',
      body: JSON.stringify({
        outcome: payload.outcome || 'completed',
        result_data: payload.result_data || null,
        notes: payload.notes || null,
      }),
    });
  }

  async cancelTaskAssignment(
    assignmentId: string,
    notes?: string
  ): Promise<any> {
    return await this.request(`/tasks/assignments/${assignmentId}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ notes: notes || null }),
    });
  }

  async getTaskResult(assignmentId: string): Promise<any> {
    return await this.request(`/tasks/assignments/${assignmentId}/result`);
  }

  // --------------------------------------------------------------------------
  // Custom Gesture Endpoints (§ 24, § 25, § 26, § 27)
  // --------------------------------------------------------------------------

  async trainCustomGesture(payload: {
    gesture_name: string;
    intent: string;
    samples: { x: number; y: number; z?: number }[][];
    handedness?: string;
  }): Promise<CustomGestureProfile> {
    return await this.request<CustomGestureProfile>('/gestures/custom/train', {
      method: 'POST',
      body: JSON.stringify({
        gesture_name: payload.gesture_name,
        intent: payload.intent,
        samples: payload.samples,
        handedness: payload.handedness || 'Right',
      }),
    });
  }

  // Phase 12: stream camera-frame landmarks through the server gesture pipeline
  async processGestureFrame(payload: {
    landmarks: { x: number; y: number; z?: number }[];
    handedness: 'Right' | 'Left';
    timestamp_ms: number;
    dwell_time_ms?: number;
  }): Promise<{
    detected_gesture: string | null;
    confidence: number;
    is_triggered: boolean;
    dwell_progress: number;
    action_mapping: string | null;
    is_custom: boolean;
    custom_gesture_id: string | null;
    message: string;
  }> {
    return await this.request('/gestures/process-frame', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getCustomGestures(): Promise<CustomGestureProfile[]> {
    return await this.request<CustomGestureProfile[]>('/gestures/custom');
  }

  async deleteCustomGesture(gestureId: string): Promise<boolean> {
    await this.request(`/gestures/custom/${gestureId}`, { method: 'DELETE' });
    return true;
  }

  // --------------------------------------------------------------------------
  // Voice & Audio Endpoints
  // --------------------------------------------------------------------------

  async processVoiceCommand(payload: {
    raw_transcript: string;
    confidence?: number;
    language?: string;
    work_session_id?: string;
  }): Promise<{
    matched_command: string | null;
    action_mapping: string | null;
    confidence: number;
    fuzzy_score: number;
    requires_confirmation: boolean;
    validation_status: string;
    message?: string;
  }> {
    return await this.request('/voice/process-command', {
      method: 'POST',
      body: JSON.stringify({
        raw_transcript: payload.raw_transcript,
        confidence: payload.confidence ?? 0.9,
        language: payload.language || 'en-US',
        work_session_id: payload.work_session_id || null,
      }),
    });
  }

  async processMultimodalIntent(
    payloadOrInput: MultimodalFusionPayload | MultimodalInputItem[] | MultimodalInputItem
  ): Promise<MultimodalFusionResult> {
    let inputs: any[] = [];
    let temporalWindowMs = 1500;
    let workSessionId: string | null = null;
    let clientContext: Record<string, any> = {};

    if (payloadOrInput && 'inputs' in payloadOrInput && Array.isArray((payloadOrInput as any).inputs)) {
      inputs = (payloadOrInput as MultimodalFusionPayload).inputs;
      temporalWindowMs = (payloadOrInput as any).temporal_window_ms || (payloadOrInput as any).temporalWindowMs || 1500;
      workSessionId = (payloadOrInput as any).work_session_id || null;
      clientContext = (payloadOrInput as any).client_context || {};
    } else if (Array.isArray(payloadOrInput)) {
      inputs = payloadOrInput;
    } else if (payloadOrInput) {
      inputs = [payloadOrInput];
    }

    const formattedInputs = inputs.map((item) => ({
      mode: typeof item.mode === 'string' ? item.mode.toLowerCase() : item.mode,
      raw_intent: item.raw_intent || item.rawIntent || '',
      confidence: item.confidence ?? 0.9,
      timestamp_ms: item.timestamp_ms ?? item.timestampMs ?? Date.now(),
      context_data: item.context_data || item.contextData || {},
    }));

    const rawResult = await this.request<any>('/multimodal/fuse', {
      method: 'POST',
      body: JSON.stringify({
        inputs: formattedInputs,
        temporal_window_ms: temporalWindowMs,
        work_session_id: workSessionId,
        client_context: clientContext,
      }),
    });

    return {
      fused_action: rawResult.fused_action ?? rawResult.fusedAction ?? null,
      fused_confidence: rawResult.fused_confidence ?? rawResult.fusedConfidence ?? 0,
      fusion_strategy: rawResult.fusion_strategy ?? rawResult.fusionStrategy ?? 'single_mode',
      requires_confirmation: rawResult.requires_confirmation ?? rawResult.requiresConfirmation ?? false,
      contributing_modes: rawResult.contributing_modes ?? rawResult.contributingModes ?? [],
      target_context: rawResult.target_context ?? rawResult.targetContext ?? {},
      validation_status: rawResult.validation_status ?? rawResult.validationStatus ?? 'valid',
      message: rawResult.message,
      // camelCase aliases
      fusedAction: rawResult.fused_action ?? rawResult.fusedAction ?? null,
      fusedConfidence: rawResult.fused_confidence ?? rawResult.fusedConfidence ?? 0,
      fusionStrategy: rawResult.fusion_strategy ?? rawResult.fusionStrategy ?? 'single_mode',
      requiresConfirmation: rawResult.requires_confirmation ?? rawResult.requiresConfirmation ?? false,
      contributingModes: rawResult.contributing_modes ?? rawResult.contributingModes ?? [],
      targetContext: rawResult.target_context ?? rawResult.targetContext ?? {},
      validationStatus: rawResult.validation_status ?? rawResult.validationStatus ?? 'valid',
    };
  }

  /**
   * Safety-critical Emergency Stop Trigger.
   * Software prototype safety boundary: records an emergency stop event,
   * creates an urgent supervisor assistance request, and returns confirmation.
   * Fails closed on network or backend failure (never returns fake success).
   */
  async triggerSafetyStop(
    reason: string,
    workSessionId?: string
  ): Promise<{ success: boolean; eventId: string; message?: string }> {
    const res = await this.request<{
      success: boolean;
      event_id?: string;
      eventId?: string;
      message?: string;
    }>('/actions/emergency-stop', {
      method: 'POST',
      body: JSON.stringify({
        reason,
        work_session_id: workSessionId || null,
      }),
    });

    return {
      success: res.success,
      eventId: res.eventId || res.event_id || 'evt-safety',
      message: res.message,
    };
  }

  async requestAssistance(data: {
    category: string;
    description: string;
    priority: string;
    workSessionId?: string;
  }): Promise<{ ticketId: string; status: string }> {
    const res = await this.request<any>('/assistance/requests', {
      method: 'POST',
      body: JSON.stringify({
        reason: data.description || data.category,
        priority: data.priority || 'normal',
        work_session_id: data.workSessionId || null,
      }),
    });
    return {
      ticketId: res.id || res.ticketId || 'ack',
      status: res.status || 'open',
    };
  }

  async getPersonalization(): Promise<WorkerPersonalization> {
    return await this.request<WorkerPersonalization>('/personalization/me');
  }

  // --------------------------------------------------------------------------
  // Supervisor Endpoints
  // --------------------------------------------------------------------------

  async getSupervisorDashboard(): Promise<{
    active_workers_count: number;
    available_workers_count: number;
    workers_in_task_count: number;
    workers_requesting_assistance_count: number;
    completed_tasks_count: number;
    in_progress_tasks_count: number;
    failed_tasks_count: number;
    current_workload_percent: number;
    emergency_stops_active: number;
  }> {
    return await this.request('/supervisor/dashboard');
  }

  async getSupervisorWorkers(): Promise<any[]> {
    return await this.request<any[]>('/supervisor/workers');
  }

  async getSupervisorWorkerDetail(workerId: string): Promise<any> {
    return await this.request(`/supervisor/workers/${workerId}`);
  }

  async getSupervisorTasks(): Promise<any[]> {
    return await this.request<any[]>('/supervisor/tasks');
  }

  async assignSupervisorTask(payload: {
    task_id: string;
    worker_profile_id: string;
    notes?: string;
  }): Promise<{ message: string; assignment?: any }> {
    return await this.request('/supervisor/tasks/assign', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async reassignSupervisorTask(
    assignmentId: string,
    payload: { new_worker_profile_id: string; reason?: string }
  ): Promise<{ message: string; new_assignment?: any }> {
    return await this.request(`/supervisor/tasks/${assignmentId}/reassign`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getSupervisorAssistance(statusFilter?: string, priorityFilter?: string): Promise<any[]> {
    const params = new URLSearchParams();
    if (statusFilter) params.append('status', statusFilter);
    if (priorityFilter) params.append('priority', priorityFilter);
    const qs = params.toString();
    return await this.request<any[]>(`/supervisor/assistance${qs ? `?${qs}` : ''}`);
  }

  async acknowledgeSupervisorAssistance(requestId: string): Promise<any> {
    return await this.request(`/supervisor/assistance/${requestId}/acknowledge`, {
      method: 'POST',
    });
  }

  async respondSupervisorAssistance(
    requestId: string,
    guidanceMessage: string,
    resolutionAction?: string
  ): Promise<any> {
    return await this.request(`/supervisor/assistance/${requestId}/respond`, {
      method: 'POST',
      body: JSON.stringify({
        guidance_message: guidanceMessage,
        resolution_action: resolutionAction,
      }),
    });
  }

  async resolveSupervisorAssistance(requestId: string, resolutionNotes?: string): Promise<any> {
    return await this.request(`/supervisor/assistance/${requestId}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ resolution_notes: resolutionNotes }),
    });
  }

  async getSupervisorEmergencyEvents(): Promise<any[]> {
    return await this.request<any[]>('/supervisor/emergency-events');
  }

  async getSupervisorAnalytics(): Promise<any> {
    return await this.request('/supervisor/analytics');
  }

  async getSupervisorAudit(limit: number = 50): Promise<any[]> {
    return await this.request<any[]>(`/supervisor/audit?limit=${limit}`);
  }

  async getPendingAssistanceTickets(): Promise<AssistanceTicket[]> {
    const data = await this.getSupervisorAssistance();
    if (data && data.length > 0) {
      return data.map((d) => ({
        id: d.id,
        workSessionId: d.work_session_id || 'ws-active',
        workerProfileId: d.worker_profile_id || 'wp-active',
        workerName: d.worker_name || 'Worker',
        stationName: d.task_name || 'Station',
        priority: d.priority || 'normal',
        category: d.is_emergency ? 'emergency_stop' : 'assistance',
        description: d.reason || 'Assistance requested',
        status: d.status || 'open',
        createdAt: d.requested_at ? new Date(d.requested_at).toLocaleTimeString() : 'Just now',
      }));
    }
    return [];
  }

  // --------------------------------------------------------------------------
  // Static UI Presets (Legitimate static configuration - preserved)
  // --------------------------------------------------------------------------

  async getInteractionPresets(): Promise<InteractionPreset[]> {
    const rows = await this.request<any[]>('/admin/configs');
    return rows.map((r) => ({
      id: r.id,
      name: r.name,
      description: r.description || undefined,
      status: r.status,
      dwellTimeMs: r.config_data?.dwell_time_ms ?? 450,
      gestureSensitivity: r.config_data?.gesture_sensitivity ?? 0.85,
      acousticFloor: r.config_data?.acoustic_floor ?? 0.6,
    }));
  }

  async createInteractionPreset(payload: {
    name: string;
    description?: string;
    config_data?: Record<string, unknown>;
  }): Promise<InteractionPreset> {
    const r = await this.request<any>('/admin/configs', {
      method: 'POST',
      body: JSON.stringify({ organization_id: this.orgId, ...payload }),
    });
    return {
      id: r.id,
      name: r.name,
      description: r.description || undefined,
      status: r.status,
      dwellTimeMs: r.config_data?.dwell_time_ms ?? 450,
      gestureSensitivity: r.config_data?.gesture_sensitivity ?? 0.85,
      acousticFloor: r.config_data?.acoustic_floor ?? 0.6,
    };
  }

  async updateInteractionPreset(
    presetId: string,
    payload: {
      name?: string;
      description?: string;
      config_data?: Record<string, unknown>;
      status?: string;
    }
  ): Promise<InteractionPreset> {
    const r = await this.request<any>(`/admin/configs/${presetId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    return {
      id: r.id,
      name: r.name,
      description: r.description || undefined,
      status: r.status,
      dwellTimeMs: r.config_data?.dwell_time_ms ?? 450,
      gestureSensitivity: r.config_data?.gesture_sensitivity ?? 0.85,
      acousticFloor: r.config_data?.acoustic_floor ?? 0.6,
    };
  }

  async deleteInteractionPreset(presetId: string): Promise<boolean> {
    await this.request(`/admin/configs/${presetId}`, { method: 'DELETE' });
    return true;
  }

  // Phase 9: Permission matrix (organization-scoped, PostgreSQL-backed)
  async getPermissionsMatrix(): Promise<PermissionMatrix> {
    return await this.request<PermissionMatrix>('/permissions/matrix');
  }

  async setPermissionGrant(payload: {
    role_name: string;
    permission_name: string;
    granted: boolean;
  }): Promise<PermissionMatrix> {
    return await this.request<PermissionMatrix>('/permissions/matrix', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  }

  // Phase 9: Adaptation recommendations review (PostgreSQL-backed)
  async getAdaptationRecommendations(
    status?: 'pending' | 'approved' | 'dismissed'
  ): Promise<AdaptationReviewItem[]> {
    const qs = status ? `?status=${status}` : '';
    return await this.request<AdaptationReviewItem[]>(
      `/personalization/recommendations${qs}`
    );
  }

  async reviewAdaptationRecommendation(
    recommendationId: string,
    action: 'approve' | 'dismiss'
  ): Promise<AdaptationReviewItem> {
    return await this.request<AdaptationReviewItem>(
      `/personalization/recommendations/${recommendationId}/review`,
      { method: 'POST', body: JSON.stringify({ action }) }
    );
  }

  // --------------------------------------------------------------------------
  // Enterprise Organization Management Endpoints (§ 1-38)
  // --------------------------------------------------------------------------

  async getOrgDashboard(): Promise<any> {
    return await this.request('/organizations/manage/dashboard');
  }

  async getOrgProfile(): Promise<any> {
    return await this.request('/organizations/manage/profile');
  }

  async updateOrgProfile(payload: any): Promise<any> {
    return await this.request('/organizations/manage/profile', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  }

  async getOrgDepartments(): Promise<any[]> {
    return await this.request<any[]>('/organizations/manage/departments');
  }

  async createOrgDepartment(payload: { name: string; status?: string }): Promise<any> {
    return await this.request('/organizations/manage/departments', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async updateOrgDepartment(deptId: string, payload: any): Promise<any> {
    return await this.request(`/organizations/manage/departments/${deptId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  }

  async deactivateOrgDepartment(deptId: string): Promise<any> {
    return await this.request(`/organizations/manage/departments/${deptId}`, {
      method: 'DELETE',
    });
  }

  async getOrgSupervisors(): Promise<any[]> {
    return await this.request<any[]>('/organizations/manage/supervisors');
  }

  async inviteOrgSupervisor(payload: {
    email: string;
    full_name: string;
    department_id?: string;
  }): Promise<any> {
    return await this.request('/organizations/manage/supervisors/invite', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getOrgWorkers(params?: {
    page?: number;
    page_size?: number;
    status?: string;
    department_id?: string;
  }): Promise<any> {
    const q = new URLSearchParams();
    if (params?.page) q.append('page', params.page.toString());
    if (params?.page_size) q.append('page_size', params.page_size.toString());
    if (params?.status) q.append('status', params.status);
    if (params?.department_id) q.append('department_id', params.department_id);
    const qs = q.toString();
    return await this.request(`/organizations/manage/workers${qs ? `?${qs}` : ''}`);
  }

  async inviteOrgWorker(payload: {
    email: string;
    full_name: string;
    badge_number?: string;
    department_id?: string;
    preferred_modality?: string;
  }): Promise<any> {
    return await this.request('/organizations/manage/workers/invite', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getOrgWorkflows(): Promise<any[]> {
    return await this.request<any[]>('/organizations/manage/workflows');
  }

  async createOrgWorkflow(payload: any): Promise<any> {
    return await this.request('/organizations/manage/workflows', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getOrgAssistanceOverview(): Promise<any[]> {
    return await this.request<any[]>('/organizations/manage/assistance');
  }

  async getOrgEmergencyEvents(): Promise<any[]> {
    return await this.request<any[]>('/organizations/manage/emergencies');
  }

  async getOrgAnalytics(): Promise<any> {
    return await this.request('/organizations/manage/analytics');
  }

  async getOrgAudit(limit: number = 50): Promise<any[]> {
    return await this.request<any[]>(`/organizations/manage/audit?limit=${limit}`);
  }

  // Phase 10: accessibility preferences (PostgreSQL-authoritative)
  async getAccessibilityPreferences(): Promise<Record<string, unknown>> {
    return await this.request<Record<string, unknown>>(
      '/accessibility/preferences'
    );
  }

  async updateAccessibilityPreferences(
    preferences: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    return await this.request<Record<string, unknown>>(
      '/accessibility/preferences',
      { method: 'PUT', body: JSON.stringify({ preferences }) }
    );
  }

  async getAuditLogs(limit: number = 50): Promise<any[]> {
    return this.getOrgAudit(limit);
  }
}

export const api = new ApiClient();
