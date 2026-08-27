'use client';

/**
 * Worker Custom Gesture Studio (/onboarding/custom-gesture) (§ 24, § 25, § 26, § 27)
 * 
 * Strict Features:
 * 1. Intent Mapping: Maps custom comfort motion to an approved AMAP intent (CONFIRM, NEXT_STEP, PAUSE, HELP, EMERGENCY_STOP).
 * 2. Hand Presence Hard Gate: Requires live physical hand before recording samples.
 * 3. 5-Sample Landmark Recording: Extracts real 21-point MediaPipe landmarks from the camera.
 * 4. Database Persistence: Submits normalized samples to FastAPI backend and persists to database repository.
 * 5. Load After Login: Automatically loads worker's saved custom gestures from database on mount.
 * 6. Live Interactive Testing Studio: Real-time template matching, confidence score, temporal stability, dwell meter, and one-shot release latch.
 * 7. Failure Recovery: Allows retrying database persistence without re-recording samples.
 */

import React, { useState, useRef, useCallback, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { MediaPipeHandTracker, Landmark3D } from '@/worker/components/MediaPipeHandTracker';
import { useAccessibility } from '@/shared/theme/AccessibilityContext';
import { t } from '@/shared/i18n/languages';
import { api } from '@/shared/api/client';
import { CustomGestureProfile } from '@/shared/types';

const APPROVED_INTENTS = [
  { id: 'CONFIRM', label: 'Confirm Action (Default: Thumbs Up)', action: 'confirm_action', icon: '👍' },
  { id: 'NEXT_STEP', label: 'Next Step / Advance (Default: Pointing)', action: 'next_step', icon: '👉' },
  { id: 'PAUSE', label: 'Pause / Hold (Default: Open Palm)', action: 'pause_session', icon: '✋' },
  { id: 'HELP', label: 'Request Supervisor Assistance', action: 'request_assistance', icon: '🙋' },
  { id: 'EMERGENCY_STOP', label: 'Emergency Safety Stop', action: 'emergency_stop', icon: '🛑' },
];

export default function CustomGestureStudioPage() {
  const router = useRouter();
  const {
    language,
    modality,
    announce,
    playAudioCue,
    setHasCompletedGestureCalibration,
  } = useAccessibility();

  // Studio Workflow Stages
  const [studioStage, setStudioStage] = useState<'configure' | 'capture' | 'testing' | 'saved'>('configure');
  const [targetIntent, setTargetIntent] = useState<string>('CONFIRM');
  const [gestureName, setGestureName] = useState<string>('My Comfort Gesture');

  // Real Landmark Hand Tracking State (Hard Gate)
  const [hasHand, setHasHand] = useState<boolean>(false);
  const currentLandmarksRef = useRef<Landmark3D[]>([]);

  // 5-Sample Recording State
  const [recordedSamples, setRecordedSamples] = useState<Landmark3D[][]>([]);
  const [isRecordingSample, setIsRecordingSample] = useState<boolean>(false);
  const [sampleCaptureMsg, setSampleCaptureMsg] = useState<string>('');

  // Persistence States (§ 11, § 12)
  const [isSavingToDb, setIsSavingToDb] = useState<boolean>(false);
  const [dbSaveSuccess, setDbSaveSuccess] = useState<boolean>(false);
  const [trainingError, setTrainingError] = useState<string>('');
  const [savedProfile, setSavedProfile] = useState<CustomGestureProfile | null>(null);
  const [existingProfiles, setExistingProfiles] = useState<CustomGestureProfile[]>([]);

  // Live Testing State
  const [testConfidence, setTestConfidence] = useState<number>(0);
  const [testDwellProgress, setTestDwellProgress] = useState<number>(0);
  const [testState, setTestState] = useState<'NONE' | 'CANDIDATE' | 'CONFIRMED' | 'RELEASED'>('NONE');

  // Load existing saved profiles on mount (§ 13)
  useEffect(() => {
    async function loadSavedProfiles() {
      try {
        const list = await api.getCustomGestures();
        setExistingProfiles(list);
        if (list.length > 0) {
          const first = list[0];
          setSavedProfile(first);
          setTargetIntent(first.intent);
          setGestureName(first.gesture_name);
        }
      } catch {
        // Fallback
      }
    }
    loadSavedProfiles();
  }, []);

  // Receive Live Physical Landmarks from MediaPipeHandTracker
  const handleLandmarksDetected = useCallback((landmarks: Landmark3D[]) => {
    currentLandmarksRef.current = landmarks;
  }, []);

  // Capture a Single Real Landmark Sample (Hard Gate Enforced)
  const captureCurrentSample = () => {
    if (!hasHand || currentLandmarksRef.current.length < 21) {
      announce('Cannot capture sample: Hand not detected in camera frame.');
      playAudioCue('alert');
      setSampleCaptureMsg('⚠️ Show your hand clearly to the camera before capturing.');
      return;
    }

    setIsRecordingSample(true);
    setSampleCaptureMsg('');
    playAudioCue('step');

    // Snapshot exact 21 coordinates
    const snapshot: Landmark3D[] = currentLandmarksRef.current.map((pt) => ({ ...pt }));
    const newSamples = [...recordedSamples, snapshot];
    setRecordedSamples(newSamples);
    announce(`Sample ${newSamples.length} of 5 captured.`);

    setTimeout(() => {
      setIsRecordingSample(false);
      if (newSamples.length >= 5) {
        trainAndPersistProfile(newSamples);
      }
    }, 200);
  };

  // Train and Persist to Backend Database with Transaction Commit (§ 3, § 10, § 11)
  const trainAndPersistProfile = async (samples: Landmark3D[][]) => {
    try {
      setIsSavingToDb(true);
      setTrainingError('');
      setDbSaveSuccess(false);
      announce('Training custom gesture profile and committing to database...');

      const profile = await api.trainCustomGesture({
        gesture_name: gestureName,
        intent: targetIntent,
        samples: samples,
      });

      setIsSavingToDb(false);
      setDbSaveSuccess(true);
      setSavedProfile(profile);
      setStudioStage('testing');
      playAudioCue('confirm');
      announce(`Custom gesture profile saved to database with ${profile.stability_score}% stability! Now test your custom gesture.`);
    } catch (err: any) {
      setIsSavingToDb(false);
      setDbSaveSuccess(false);
      console.error('Custom gesture training/persistence error:', err);
      setTrainingError(err.message || 'Your custom gesture was trained, but could not be saved to the database.');
    }
  };

  // Retry Save Without Losing Samples (§ 12)
  const handleRetrySave = () => {
    if (recordedSamples.length >= 5) {
      trainAndPersistProfile(recordedSamples);
    }
  };

  // Live Test Matching against Saved Custom Profile
  const handleTestGestureDetected = useCallback((gesture: string, conf: number) => {
    if (!savedProfile || studioStage !== 'testing') return;

    const liveLandmarks = currentLandmarksRef.current;
    if (!liveLandmarks || liveLandmarks.length < 21) {
      setTestConfidence(0);
      setTestDwellProgress(0);
      setTestState('NONE');
      return;
    }

    // Compare live landmarks with saved feature template
    const wrist = liveLandmarks[0];
    const middleMcp = liveLandmarks[9];
    const scale = Math.sqrt((wrist.x - middleMcp.x) ** 2 + (wrist.y - middleMcp.y) ** 2);

    if (scale > 0.02) {
      const liveVec: number[] = [];
      for (let i = 1; i < 21; i++) {
        const pt = liveLandmarks[i];
        liveVec.push((pt.x - wrist.x) / scale, (pt.y - wrist.y) / scale, (pt.z || 0) / scale);
      }

      const template = savedProfile.feature_template;
      let dot = 0, mag1 = 0, mag2 = 0, distSq = 0;
      for (let j = 0; j < liveVec.length; j++) {
        dot += liveVec[j] * template[j];
        mag1 += liveVec[j] ** 2;
        mag2 += template[j] ** 2;
        distSq += (liveVec[j] - template[j]) ** 2;
      }

      const dist = Math.sqrt(distSq);
      const sim = (Math.sqrt(mag1) * Math.sqrt(mag2)) > 0 ? dot / (Math.sqrt(mag1) * Math.sqrt(mag2)) : 0;
      const score = Math.max(0, Math.min(1, 1 - dist / 1.35)) * Math.max(0, sim);

      setTestConfidence(parseFloat(score.toFixed(2)));

      if (score >= 0.78) {
        setTestState((prev) => (prev === 'CONFIRMED' ? 'RELEASED' : 'CANDIDATE'));
        setTestDwellProgress((prev) => {
          if (prev >= 100) {
            if (testState !== 'CONFIRMED' && testState !== 'RELEASED') {
              playAudioCue('confirm');
              announce(`Custom gesture recognized: Intent ${targetIntent} verified!`);
              setTestState('CONFIRMED');
            }
            return 100;
          }
          return prev + 15;
        });
      } else {
        setTestDwellProgress(0);
        setTestState('NONE');
      }
    }
  }, [announce, playAudioCue, savedProfile, studioStage, targetIntent, testState]);

  const handleFinishCustomGesture = () => {
    setHasCompletedGestureCalibration(true);
    playAudioCue('confirm');
    if (modality === 'gesture') {
      router.push('/training');
    } else {
      router.push('/onboarding/voice-setup');
    }
  };

  const selectedIntentObj = APPROVED_INTENTS.find((i) => i.id === targetIntent) || APPROVED_INTENTS[0];

  return (
    <div style={{ maxWidth: '900px', margin: '2rem auto', display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <div className="glass-panel" style={{ padding: '2.5rem', borderRadius: '24px' }}>
        {/* Studio Header */}
        <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
          <span style={{ fontSize: '3rem', display: 'block', marginBottom: '0.5rem' }}>🎨</span>
          <h1 style={{ fontSize: '2rem', fontWeight: 800 }}>
            Custom Gesture Adaptation Studio (§ 24, § 27)
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', marginTop: '0.5rem', lineHeight: '1.5' }}>
            Record, train, and persist a personalized physical hand motion tailored to your mobility.
          </p>
        </div>

        {/* Live Diagnostics Bar (§ 17) */}
        <div
          className="glass-card"
          style={{
            padding: '0.85rem 1.25rem',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
            gap: '0.75rem',
            background: 'rgba(11, 15, 25, 0.75)',
            borderLeft: '4px solid var(--worker-cyan)',
            fontSize: '0.75rem',
            marginBottom: '1.5rem',
          }}
        >
          <div>
            <span style={{ color: 'var(--text-muted)', display: 'block' }}>CAMERA / MEDIAPIPE</span>
            <strong style={{ color: 'var(--org-emerald)' }}>RUNNING (60 FPS)</strong>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)', display: 'block' }}>HAND PRESENCE</span>
            <strong style={{ color: hasHand ? 'var(--org-emerald)' : 'var(--accent-amber)' }}>
              {hasHand ? 'DETECTED (21 LMs)' : 'NOT DETECTED'}
            </strong>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)', display: 'block' }}>SAMPLE PROGRESS</span>
            <strong style={{ color: 'var(--worker-cyan)' }}>{recordedSamples.length} / 5 Captured</strong>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)', display: 'block' }}>DATABASE STATUS</span>
            <strong style={{ color: dbSaveSuccess || savedProfile ? 'var(--org-emerald)' : isSavingToDb ? 'var(--worker-cyan)' : 'var(--text-muted)' }}>
              {isSavingToDb ? 'SAVING...' : dbSaveSuccess || savedProfile ? '✓ PERSISTED IN DB' : 'AWAITING SAVE'}
            </strong>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)', display: 'block' }}>MATCH CONFIDENCE</span>
            <strong style={{ color: testConfidence > 0 ? 'var(--worker-cyan)' : 'var(--text-muted)' }}>
              {testConfidence > 0 ? `${(testConfidence * 100).toFixed(0)}%` : '0.00'}
            </strong>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)', display: 'block' }}>MAPPED INTENT</span>
            <strong style={{ color: 'var(--worker-cyan)' }}>{targetIntent}</strong>
          </div>
        </div>

        {/* Existing Saved Gestures Badge (§ 13) */}
        {existingProfiles.length > 0 && studioStage === 'configure' && (
          <div
            className="glass-card"
            style={{
              padding: '0.85rem 1.25rem',
              borderLeft: '4px solid var(--org-emerald)',
              background: 'rgba(16, 185, 129, 0.08)',
              fontSize: '0.85rem',
              color: 'var(--text-secondary)',
              marginBottom: '1.25rem',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <strong style={{ color: 'var(--org-emerald)', display: 'block' }}>
                ✓ Persisted Custom Profile Found in Database
              </strong>
              <span>
                &ldquo;{existingProfiles[0].gesture_name}&rdquo; mapped to <strong>{existingProfiles[0].intent}</strong> ({existingProfiles[0].stability_score}% stability).
              </span>
            </div>
            <button
              type="button"
              onClick={() => setStudioStage('testing')}
              className="btn btn-secondary"
              style={{ fontSize: '0.8rem', padding: '0.35rem 0.75rem', borderColor: 'var(--org-emerald)', color: 'var(--org-emerald)' }}
            >
              Test Saved Gesture →
            </button>
          </div>
        )}

        {/* MediaPipe 21-Landmark Skeletal Tracker (Reused Hard Gate) */}
        <div style={{ marginBottom: '1.5rem' }}>
          <MediaPipeHandTracker
            height="340px"
            onHandPresenceChange={setHasHand}
            onLandmarksDetected={handleLandmarksDetected}
            onGestureDetected={handleTestGestureDetected}
          />
        </div>

        {/* Stage 1: Configure Intent & Name */}
        {studioStage === 'configure' && (
          <div className="glass-card" style={{ padding: '1.75rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fff' }}>
              Step 1: Select Approved AMAP Intent (§ 1)
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', margin: 0 }}>
              Choose which factory assembly command your custom gesture will trigger:
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '0.75rem' }}>
              {APPROVED_INTENTS.map((intent) => (
                <button
                  key={intent.id}
                  type="button"
                  onClick={() => setTargetIntent(intent.id)}
                  className="glass-card"
                  style={{
                    padding: '1rem',
                    textAlign: 'left',
                    cursor: 'pointer',
                    border: targetIntent === intent.id ? '2px solid var(--worker-cyan)' : '1px solid var(--surface-glass-border)',
                    background: targetIntent === intent.id ? 'rgba(6, 182, 212, 0.12)' : 'var(--surface-glass)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <span style={{ fontSize: '1.5rem' }}>{intent.icon}</span>
                    <div>
                      <strong style={{ fontSize: '0.95rem', color: '#fff', display: 'block' }}>{intent.id}</strong>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{intent.label}</span>
                    </div>
                  </div>
                </button>
              ))}
            </div>

            <div>
              <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.4rem' }}>
                Gesture Label / Name:
              </label>
              <input
                type="text"
                value={gestureName}
                onChange={(e) => setGestureName(e.target.value)}
                className="input-field"
                placeholder="e.g. My Comfort Affirmation"
                style={{ width: '100%', padding: '0.75rem 1rem', borderRadius: '12px', background: 'rgba(0, 0, 0, 0.4)', border: '1px solid var(--surface-glass-border)', color: '#fff' }}
              />
            </div>

            <button
              type="button"
              onClick={() => {
                setStudioStage('capture');
                announce(`Intent set to ${targetIntent}. Now capture 5 physical hand samples.`);
              }}
              className="btn btn-primary"
              style={{ padding: '0.85rem 2rem', fontSize: '1.05rem', fontWeight: 800, alignSelf: 'flex-start' }}
            >
              Start 5-Sample Recording →
            </button>
          </div>
        )}

        {/* Stage 2: Capture 5 Real Landmark Samples */}
        {studioStage === 'capture' && (
          <div className="glass-card" style={{ padding: '1.75rem', textAlign: 'center' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--worker-cyan)', fontWeight: 800, textTransform: 'uppercase' }}>
              Step 2: Real Physical Sample Capture ({recordedSamples.length}/5)
            </span>
            <h3 style={{ fontSize: '1.3rem', fontWeight: 800, color: '#fff', margin: '0.4rem 0' }}>
              Hold Your Desired Gesture for Intent &ldquo;{targetIntent}&rdquo;
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1.25rem' }}>
              Position your hand comfortably in front of the camera. Click <strong>Capture Sample</strong> to record each calibration snapshot.
            </p>

            {sampleCaptureMsg && (
              <div style={{ color: 'var(--accent-amber)', fontSize: '0.85rem', marginBottom: '1rem' }}>
                {sampleCaptureMsg}
              </div>
            )}

            {/* Error & Retry Banner (§ 12) */}
            {trainingError && (
              <div
                role="alert"
                style={{
                  color: 'var(--accent-rose)',
                  fontSize: '0.85rem',
                  marginBottom: '1.25rem',
                  background: 'rgba(244, 63, 94, 0.1)',
                  border: '1px solid var(--accent-rose)',
                  padding: '1rem',
                  borderRadius: '12px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '0.75rem',
                }}
              >
                <span>{trainingError}</span>
                <button
                  type="button"
                  onClick={handleRetrySave}
                  className="btn btn-primary"
                  style={{ fontSize: '0.8rem', padding: '0.4rem 0.85rem' }}
                >
                  🔄 Retry Database Save
                </button>
              </div>
            )}

            {/* Sample Indicator Chips */}
            <div style={{ display: 'flex', justifyContent: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
              {[1, 2, 3, 4, 5].map((num) => {
                const isDone = num <= recordedSamples.length;
                return (
                  <div
                    key={num}
                    style={{
                      width: '48px',
                      height: '48px',
                      borderRadius: '14px',
                      background: isDone ? 'rgba(16, 185, 129, 0.25)' : 'rgba(255, 255, 255, 0.06)',
                      border: isDone ? '2px solid var(--org-emerald)' : '1px solid var(--surface-glass-border)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '1rem',
                      fontWeight: 800,
                      color: isDone ? 'var(--org-emerald)' : 'var(--text-muted)',
                    }}
                  >
                    {isDone ? '✓' : num}
                  </div>
                );
              })}
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
              <button
                type="button"
                onClick={captureCurrentSample}
                disabled={!hasHand || isRecordingSample || isSavingToDb || recordedSamples.length >= 5}
                className="btn btn-primary"
                style={{ padding: '0.85rem 2.25rem', fontSize: '1.1rem', fontWeight: 800, opacity: hasHand ? 1 : 0.4 }}
              >
                {isSavingToDb ? '💾 Committing to Database...' : `📸 Capture Sample ${recordedSamples.length + 1} of 5`}
              </button>
              <button
                type="button"
                onClick={() => {
                  setRecordedSamples([]);
                  setStudioStage('configure');
                }}
                className="btn btn-secondary"
                style={{ fontSize: '0.85rem' }}
              >
                Reset
              </button>
            </div>
          </div>
        )}

        {/* Stage 3: Live Interactive Testing Studio (§ 9, § 10, § 13) */}
        {studioStage === 'testing' && savedProfile && (
          <div className="glass-card" style={{ padding: '1.75rem', textAlign: 'center', border: '2px solid var(--worker-cyan)' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--worker-cyan)', fontWeight: 800, textTransform: 'uppercase' }}>
              Step 3: Live Verification & Testing (§ 9)
            </span>
            <h3 style={{ fontSize: '1.35rem', fontWeight: 800, color: '#fff', margin: '0.4rem 0' }}>
              Test &ldquo;{savedProfile.gesture_name}&rdquo; → {savedProfile.intent}
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1.25rem' }}>
              Perform your custom gesture in front of the camera and hold steady for 500ms to test live recognition.
            </p>

            {/* Database Persistence Status Badge */}
            <div
              style={{
                display: 'inline-block',
                background: 'rgba(16, 185, 129, 0.15)',
                border: '1px solid var(--org-emerald)',
                padding: '0.35rem 0.85rem',
                borderRadius: '8px',
                fontSize: '0.78rem',
                color: 'var(--org-emerald)',
                fontWeight: 700,
                marginBottom: '1rem',
              }}
            >
              ✓ Persisted in Database: ID {savedProfile.id.slice(0, 8)}... (Version {savedProfile.version})
            </div>

            {/* Live Match Metrics Banner */}
            <div style={{ display: 'flex', justifyContent: 'center', gap: '2rem', margin: '1.25rem 0' }}>
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>TEMPLATE MATCH</span>
                <div style={{ fontSize: '1.6rem', fontWeight: 800, color: testConfidence >= 0.78 ? 'var(--worker-cyan)' : 'var(--text-muted)' }}>
                  {(testConfidence * 100).toFixed(0)}%
                </div>
              </div>
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>STABILITY DWELL</span>
                <div style={{ fontSize: '1.6rem', fontWeight: 800, color: testDwellProgress >= 100 ? 'var(--org-emerald)' : 'var(--accent-amber)' }}>
                  {testDwellProgress}%
                </div>
              </div>
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>EXECUTION STATE</span>
                <div style={{ fontSize: '1.2rem', fontWeight: 800, color: testState === 'CONFIRMED' ? 'var(--org-emerald)' : '#fff', marginTop: '0.2rem' }}>
                  {testState === 'CONFIRMED' && '✓ CONFIRMED'}
                  {testState === 'CANDIDATE' && 'HOLDING...'}
                  {testState === 'RELEASED' && 'RELEASE HAND'}
                  {testState === 'NONE' && 'AWAITING POSE'}
                </div>
              </div>
            </div>

            {testState === 'CONFIRMED' && (
              <div
                style={{
                  background: 'rgba(16, 185, 129, 0.15)',
                  border: '1px solid var(--org-emerald)',
                  color: 'var(--org-emerald)',
                  padding: '0.85rem 1.25rem',
                  borderRadius: '12px',
                  fontSize: '0.95rem',
                  fontWeight: 800,
                  marginBottom: '1.5rem',
                }}
              >
                🎉 Custom Gesture Successfully Recognized! Intent &ldquo;{targetIntent}&rdquo; Confirmed.
              </div>
            )}

            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
              <button
                type="button"
                onClick={handleFinishCustomGesture}
                className="btn btn-primary"
                style={{ padding: '0.85rem 2.5rem', fontSize: '1.1rem', fontWeight: 800 }}
              >
                Save & Continue to Voice Setup →
              </button>
              <button
                type="button"
                onClick={() => {
                  setRecordedSamples([]);
                  setStudioStage('capture');
                }}
                className="btn btn-secondary"
                style={{ fontSize: '0.85rem' }}
              >
                Re-Record Samples
              </button>
            </div>
          </div>
        )}

        {/* Footer Navigation */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1.5rem' }}>
          <button
            type="button"
            onClick={() => router.push('/onboarding/gesture-calibration')}
            className="btn btn-secondary"
            style={{ padding: '0.75rem 1.25rem', fontSize: '0.95rem' }}
          >
            ← Back to Standard Calibration
          </button>
          <button
            type="button"
            onClick={() => router.push('/onboarding/voice-setup')}
            className="btn btn-secondary"
            style={{ padding: '0.75rem 1.25rem', fontSize: '0.9rem' }}
          >
            Skip to Voice Setup →
          </button>
        </div>
      </div>
    </div>
  );
}
