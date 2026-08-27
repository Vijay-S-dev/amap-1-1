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

export interface MultimodalInput {
  mode: InteractionMode;
  rawIntent: string;
  confidence: number;
  timestampMs: number;
  contextData?: Record<string, any>;
}

export interface MultimodalFusionResult {
  fusedAction: string | null;
  fusedConfidence: number;
  fusionStrategy: 'single_mode' | 'reinforcing' | 'complementary' | 'conflict_resolved' | 'conflict_ambiguous';
  requiresConfirmation: boolean;
  contributingModes: string[];
  targetContext?: Record<string, any>;
  validationStatus: 'valid' | 'rejected' | 'ambiguous';
  message?: string;
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
