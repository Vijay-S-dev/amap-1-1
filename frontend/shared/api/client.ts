/**
 * AMAP API Client
 * Connects frontend UI to FastAPI backend with bearer token management,
 * organization header scoping, and simulated offline mock states.
 */

import {
  AssistanceTicket,
  AuditLogEntry,
  InteractionPreset,
  MultimodalFusionResult,
  MultimodalInput,
  TaskDetails,
  UserContext,
  WorkerPersonalization,
  WorkSession,
} from '../types';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1';

class ApiClient {
  private token: string | null = null;
  private orgId: string = '00000000-0000-0000-0000-000000000001';

  setAuth(token: string, orgId?: string) {
    this.token = token;
    if (orgId) this.orgId = orgId;
    if (typeof window !== 'undefined') {
      localStorage.setItem('amap_token', token);
      if (orgId) localStorage.setItem('amap_org_id', orgId);
    }
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

  // --------------------------------------------------------------------------
  // Worker & Session Endpoints
  // --------------------------------------------------------------------------

  async getActiveSession(): Promise<WorkSession> {
    try {
      const res = await fetch(`${API_BASE}/sessions/active`, { headers: this.getHeaders() });
      if (res.ok) return await res.json();
    } catch {
      // fallback for offline/demo
    }
    return {
      id: 'ws-78192-demo',
      workerProfileId: 'wp-001',
      organizationId: this.orgId,
      stationId: 'Assembly Station 4B (Robotic Feeder)',
      status: 'active',
      startedAt: new Date().toISOString(),
      activeTaskId: 'task-gearbox-assembly-01',
    };
  }

  async getTaskDetails(taskId: string): Promise<TaskDetails> {
    try {
      const res = await fetch(`${API_BASE}/tasks/${taskId}`, { headers: this.getHeaders() });
      if (res.ok) return await res.json();
    } catch {
      // fallback
    }
    return {
      id: taskId,
      organizationId: this.orgId,
      name: 'High-Precision Gearbox Assembly (Subsystem A)',
      description: 'Mount primary planetary drive shaft and torque-check fasteners.',
      status: 'in_progress',
      totalSteps: 4,
      currentStepIndex: 1,
      steps: [
        {
          id: 'step-1',
          stepNumber: 1,
          title: 'Mount Drive Shaft',
          instructionText: 'Align drive shaft notch with housing notch at 0° mark. Slide until seated.',
          expectedDurationSeconds: 45,
          spatialTargetId: 'HOUSING-NOTCH-A',
          requiredModality: 'gesture',
          completed: true,
        },
        {
          id: 'step-2',
          stepNumber: 2,
          title: 'Insert Planetary Gear Bearings',
          instructionText: 'Place 3 planetary gear bearings over planetary pins. Confirm seating with thumbs-up.',
          expectedDurationSeconds: 60,
          spatialTargetId: 'PIN-CLUSTER-3',
          requiredModality: 'gesture',
          completed: false,
        },
        {
          id: 'step-3',
          stepNumber: 3,
          title: 'Torque Fasteners to 18 N·m',
          instructionText: 'Use calibrated digital wrench to torque 4 perimeter bolts in cross pattern.',
          expectedDurationSeconds: 90,
          requiredModality: 'voice',
          completed: false,
        },
        {
          id: 'step-4',
          stepNumber: 4,
          title: 'Quality Verification & Photo Capture',
          instructionText: 'Inspect clearance with gauge and signal next-step to complete assembly.',
          expectedDurationSeconds: 30,
          completed: false,
        },
      ],
    };
  }

  async fuseMultimodal(inputs: MultimodalInput[]): Promise<MultimodalFusionResult> {
    try {
      const res = await fetch(`${API_BASE}/multimodal/fuse`, {
        method: 'POST',
        headers: this.getHeaders(),
        body: JSON.stringify({ inputs, temporal_window_ms: 1500 }),
      });
      if (res.ok) return await res.json();
    } catch {
      // fallback heuristic
    }

    // Heuristic fallback for demo
    const voice = inputs.find((i) => i.mode === 'voice');
    const gesture = inputs.find((i) => i.mode === 'gesture');

    if (gesture && voice && gesture.rawIntent === 'thumbs_up' && voice.rawIntent.includes('confirm')) {
      return {
        fusedAction: 'confirm_action',
        fusedConfidence: 0.985,
        fusionStrategy: 'reinforcing',
        requiresConfirmation: false,
        contributingModes: ['gesture', 'voice'],
        validationStatus: 'valid',
        message: 'Reinforced confirmation fused across Gesture + Voice.',
      };
    }

    if (gesture && gesture.rawIntent === 'pointing') {
      return {
        fusedAction: 'select_target',
        fusedConfidence: gesture.confidence,
        fusionStrategy: 'complementary',
        requiresConfirmation: false,
        contributingModes: ['gesture'],
        targetContext: gesture.contextData,
        validationStatus: 'valid',
        message: 'Spatial focus bound to target coordinate.',
      };
    }

    const primary = inputs[0] || { rawIntent: 'next_step', confidence: 0.85, mode: 'ui' };
    return {
      fusedAction: primary.rawIntent,
      fusedConfidence: primary.confidence,
      fusionStrategy: 'single_mode',
      requiresConfirmation: primary.rawIntent === 'emergency_stop',
      contributingModes: [primary.mode],
      validationStatus: 'valid',
      message: `Processed intent via ${primary.mode}.`,
    };
  }

  async requestAssistance(data: {
    workSessionId: string;
    priority: string;
    category: string;
    description: string;
  }): Promise<{ ticketId: string; status: string }> {
    try {
      const res = await fetch(`${API_BASE}/assistance/request`, {
        method: 'POST',
        headers: this.getHeaders(),
        body: JSON.stringify(data),
      });
      if (res.ok) return await res.json();
    } catch {
      // fallback
    }
    return { ticketId: 'tick-' + Math.floor(Math.random() * 90000 + 10000), status: 'pending' };
  }

  async getPersonalization(): Promise<WorkerPersonalization> {
    try {
      const res = await fetch(`${API_BASE}/personalization/me`, { headers: this.getHeaders() });
      if (res.ok) return await res.json();
    } catch {
      // fallback
    }
    return {
      id: 'pers-001',
      workerProfileId: 'wp-001',
      dwellTimeMs: 450,
      primaryModality: 'gesture',
      highContrast: false,
      fontSizeMultiplier: 1.0,
      voiceConfirmationRequired: false,
    };
  }

  // --------------------------------------------------------------------------
  // Supervisor / Organization Endpoints
  // --------------------------------------------------------------------------

  async getPendingAssistanceTickets(): Promise<AssistanceTicket[]> {
    return [
      {
        id: 'tick-9021',
        workSessionId: 'ws-78192',
        workerProfileId: 'wp-001',
        workerName: 'Alex Morgan',
        stationName: 'Station 4B',
        priority: 'high',
        category: 'part_misalignment',
        description: 'Planetary bearing pin #2 has unexpected tolerance friction.',
        status: 'pending',
        createdAt: '2 mins ago',
      },
      {
        id: 'tick-9018',
        workSessionId: 'ws-78188',
        workerProfileId: 'wp-004',
        workerName: 'Jordan Lee',
        stationName: 'Station 2A',
        priority: 'medium',
        category: 'tool_calibration',
        description: 'Digital torque wrench battery indicator blinking.',
        status: 'in_progress',
        createdAt: '12 mins ago',
      },
    ];
  }

  // --------------------------------------------------------------------------
  // Admin Endpoints
  // --------------------------------------------------------------------------

  async getInteractionPresets(): Promise<InteractionPreset[]> {
    return [
      {
        id: 'preset-1',
        name: 'Default Factory Floor Preset',
        description: 'Standard optical tracking with moderate noise tolerance.',
        status: 'active',
        dwellTimeMs: 450,
        gestureSensitivity: 0.85,
        acousticFloor: 0.60,
      },
      {
        id: 'preset-2',
        name: 'High Noise Stamping Area',
        description: 'Elevated acoustic threshold with mandatory gesture confirmation.',
        status: 'active',
        dwellTimeMs: 600,
        gestureSensitivity: 0.90,
        acousticFloor: 0.75,
      },
    ];
  }

  async getAuditLogs(): Promise<AuditLogEntry[]> {
    return [
      {
        id: 'audit-001',
        eventType: 'user.role_assigned',
        actorUserId: 'admin-01',
        resourceType: 'user',
        eventData: { role: 'supervisor', targetUser: 'Jordan Lee' },
        occurredAt: 'Just now',
      },
      {
        id: 'audit-002',
        eventType: 'interaction_config.updated',
        actorUserId: 'admin-01',
        resourceType: 'interaction_configuration',
        eventData: { preset: 'High Noise Stamping Area', newDwellTimeMs: 600 },
        occurredAt: '15 mins ago',
      },
      {
        id: 'audit-003',
        eventType: 'personalization.adapted',
        resourceType: 'worker_personalization',
        eventData: { worker: 'Alex Morgan', adjustedDwellTimeMs: 600, reason: 'Repeated tremor adaptation' },
        occurredAt: '1 hour ago',
      },
    ];
  }
}

export const api = new ApiClient();
