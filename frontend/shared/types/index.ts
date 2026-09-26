/**
 * AMAP Frontend Type Definitions
 * Typed interfaces for API contracts across Worker, Supervisor, and Admin interfaces.
 */

export type InteractionMode = 'gesture' | 'voice' | 'touch' | 'ui';

export type SessionStatus = 'active' | 'paused' | 'completed' | 'terminated';

export type AssistancePriority = 'low' | 'medium' | 'high' | 'critical';

export interface UserContext {
  userId: string;
  organizationId: string;
  email: string;
  fullName: string;
  roles: string[];
  permissions: string[];
  workerProfileId?: string;
}

export interface WorkSession {
  id: string;
  workerProfileId: string;
  organizationId: string;
  stationId?: string;
  status: SessionStatus;
  startedAt: string;
  endedAt?: string;
  activeTaskId?: string;
}

export interface WorkflowStep {
  id: string;
  stepNumber: number;
  title: string;
  instructionText: string;
  expectedDurationSeconds?: number;
  spatialTargetId?: string;
  requiredModality?: InteractionMode;
  imageUrl?: string;
  completed?: boolean;
}

export interface TaskDetails {
  id: string;
  organizationId: string;
  name: string;
  description?: string;
  status: string;
  totalSteps: number;
  currentStepIndex: number;
  steps: WorkflowStep[];
}

export interface MultimodalInputItem {
  mode: InteractionMode | string;
  raw_intent: string;
  confidence: number;
  timestamp_ms: number;
  context_data?: Record<string, any>;
  // camelCase aliases
  rawIntent?: string;
  timestampMs?: number;
  contextData?: Record<string, any>;
}

export type MultimodalInput = MultimodalInputItem;

export interface MultimodalFusionPayload {
  inputs: MultimodalInputItem[];
  temporal_window_ms?: number;
  temporalWindowMs?: number;
  work_session_id?: string | null;
  client_context?: Record<string, any>;
}

export interface MultimodalFusionResult {
  fused_action: string | null;
  fused_confidence: number;
  fusion_strategy: string;
  requires_confirmation: boolean;
  contributing_modes: string[];
  target_context?: Record<string, any>;
  validation_status: 'valid' | 'rejected' | 'ambiguous' | string;
  message?: string;
  // camelCase aliases
  fusedAction?: string | null;
  fusedConfidence?: number;
  fusionStrategy?: string;
  requiresConfirmation?: boolean;
  contributingModes?: string[];
  targetContext?: Record<string, any>;
  validationStatus?: 'valid' | 'rejected' | 'ambiguous' | string;
}

export interface WorkerPersonalization {
  id: string;
  workerProfileId: string;
  dwellTimeMs: number;
  primaryModality: InteractionMode;
  highContrast: boolean;
  fontSizeMultiplier: number;
  voiceConfirmationRequired: boolean;
}

export interface AdaptationRecommendation {
  recommendationType: string;
  currentValue: any;
  suggestedValue: any;
  confidence: number;
  reason: string;
  autoApplicable: boolean;
}

export interface PermissionMatrixEntry {
  permission: { id: string; name: string; description?: string | null };
  roles: Record<string, boolean>;
}

export interface PermissionMatrix {
  organization_id: string;
  roles: string[];
  permissions: PermissionMatrixEntry[];
}

export interface AdaptationReviewItem {
  id: string;
  organization_id: string;
  worker_profile_id: string;
  worker_name?: string | null;
  recommendation_type: string;
  current_value: unknown;
  suggested_value: unknown;
  confidence: number;
  reason: string;
  auto_applicable: boolean;
  evidence_count: number;
  status: 'pending' | 'approved' | 'dismissed';
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AssistanceTicket {
  id: string;
  workSessionId: string;
  workerProfileId: string;
  workerName: string;
  stationName: string;
  priority: AssistancePriority;
  category: string;
  description: string;
  status: 'pending' | 'in_progress' | 'resolved';
  createdAt: string;
}

export interface InteractionPreset {
  id: string;
  name: string;
  description?: string;
  status: string;
  dwellTimeMs: number;
  gestureSensitivity: number;
  acousticFloor: number;
}

export interface AuditLogEntry {
  id: string;
  eventType: string;
  actorUserId?: string;
  resourceType?: string;
  resourceId?: string;
  eventData: Record<string, any>;
  occurredAt: string;
}

export interface CustomGestureProfile {
  id: string;
  worker_id: string;
  organization_id: string;
  gesture_name: string;
  intent: string;
  action_mapping: string;
  handedness: string;
  sample_count: number;
  stability_score: number;
  feature_template: number[];
  version: number;
  status: string;
  created_at: string;
  updated_at: string;
}
