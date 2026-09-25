'use client';

/**
 * AMAP Global Accessibility & Onboarding State Engine (§ 8, § 28)
 * Manages worker sensory preferences, live screen-reader regions,
 * audio feedback beeps, and language context.
 */

import React, { createContext, useContext, useState, useEffect } from 'react';
import { SupportedLanguage, t } from '../i18n/languages';

export type InteractionModality = 'multimodal' | 'gesture' | 'voice' | 'ui';

interface AccessibilityState {
  language: SupportedLanguage;
  setLanguage: (lang: SupportedLanguage) => void;
  modality: InteractionModality;
  setModality: (mod: InteractionModality) => void;
  highContrast: boolean;
  setHighContrast: (val: boolean) => void;
  textScale: number; // 1.0 to 1.5
  setTextScale: (val: number) => void;
  reducedMotion: boolean;
  setReducedMotion: (val: boolean) => void;
  audioFeedback: boolean;
  setAudioFeedback: (val: boolean) => void;
  playAudioCue: (type: 'confirm' | 'alert' | 'stop' | 'step') => void;
  announce: (text: string) => void;
  liveAnnouncement: string;
  // Onboarding milestones
  hasCompletedLanguage: boolean;
  setHasCompletedLanguage: (val: boolean) => void;
  hasCompletedAccessibility: boolean;
  setHasCompletedAccessibility: (val: boolean) => void;
  hasCompletedGestureCalibration: boolean;
  setHasCompletedGestureCalibration: (val: boolean) => void;
  hasCompletedVoiceSetup: boolean;
  setHasCompletedVoiceSetup: (val: boolean) => void;
  hasCompletedTraining: boolean;
  setHasCompletedTraining: (val: boolean) => void;
  isReady: boolean;
}

const AccessibilityContext = createContext<AccessibilityState | undefined>(undefined);

export function AccessibilityProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState<SupportedLanguage>('en');
  const [modality, setModalityState] = useState<InteractionModality>('multimodal');
  const [highContrast, setHighContrastState] = useState<boolean>(false);
  const [textScale, setTextScaleState] = useState<number>(1.0);
  const [reducedMotion, setReducedMotionState] = useState<boolean>(false);
  const [audioFeedback, setAudioFeedbackState] = useState<boolean>(true);
  const [liveAnnouncement, setLiveAnnouncement] = useState<string>('');

  const [hasCompletedLanguage, setHasCompletedLanguageState] = useState<boolean>(false);
  const [hasCompletedAccessibility, setHasCompletedAccessibilityState] = useState<boolean>(false);
  const [hasCompletedGestureCalibration, setHasCompletedGestureCalibrationState] = useState<boolean>(false);
  const [hasCompletedVoiceSetup, setHasCompletedVoiceSetupState] = useState<boolean>(false);
  const [hasCompletedTraining, setHasCompletedTrainingState] = useState<boolean>(false);

  // Load from localStorage on mount
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const savedLang = localStorage.getItem('amap_lang') as SupportedLanguage;
    if (savedLang) setLanguageState(savedLang);

    const savedMod = localStorage.getItem('amap_modality') as InteractionModality;
    if (savedMod) setModalityState(savedMod);

    const savedHC = localStorage.getItem('amap_high_contrast');
    if (savedHC) setHighContrastState(savedHC === 'true');

    const savedScale = localStorage.getItem('amap_text_scale');
    if (savedScale) setTextScaleState(parseFloat(savedScale));

    const savedRM = localStorage.getItem('amap_reduced_motion');
    if (savedRM) setReducedMotionState(savedRM === 'true');

    const savedAF = localStorage.getItem('amap_audio_feedback');
    if (savedAF) setAudioFeedbackState(savedAF !== 'false');

    setHasCompletedLanguageState(localStorage.getItem('amap_ob_lang') === 'true');
    setHasCompletedAccessibilityState(localStorage.getItem('amap_ob_acc') === 'true');
    setHasCompletedGestureCalibrationState(localStorage.getItem('amap_ob_gest') === 'true');
    setHasCompletedVoiceSetupState(localStorage.getItem('amap_ob_voice') === 'true');
    setHasCompletedTrainingState(localStorage.getItem('amap_ob_train') === 'true');
  }, []);

  // Synchronize document.documentElement.lang safely from the client (WCAG 3.1.1)
  useEffect(() => {
    if (typeof document !== 'undefined') {
      const supportedLanguages: SupportedLanguage[] = ['en', 'es', 'ta', 'hi', 'de'];
      const activeLang = supportedLanguages.includes(language) ? language : 'en';
      document.documentElement.lang = activeLang;
    }
  }, [language]);

  // Synchronize root body class with high contrast and reduced motion preferences
  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.body.classList.toggle('high-contrast', highContrast);
      document.body.classList.toggle('theme-high-contrast', highContrast);
      document.body.classList.toggle('reduce-motion', reducedMotion);
    }
  }, [highContrast, reducedMotion]);

  const setLanguage = (lang: SupportedLanguage) => {
    setLanguageState(lang);
    if (typeof window !== 'undefined') localStorage.setItem('amap_lang', lang);
  };

  const setModality = (mod: InteractionModality) => {
    setModalityState(mod);
    if (typeof window !== 'undefined') localStorage.setItem('amap_modality', mod);
  };

  const setHighContrast = (val: boolean) => {
    setHighContrastState(val);
    if (typeof window !== 'undefined') localStorage.setItem('amap_high_contrast', String(val));
  };

  const setTextScale = (val: number) => {
    setTextScaleState(val);
    if (typeof window !== 'undefined') localStorage.setItem('amap_text_scale', String(val));
  };

  const setReducedMotion = (val: boolean) => {
    setReducedMotionState(val);
    if (typeof window !== 'undefined') localStorage.setItem('amap_reduced_motion', String(val));
  };

  const setAudioFeedback = (val: boolean) => {
    setAudioFeedbackState(val);
    if (typeof window !== 'undefined') localStorage.setItem('amap_audio_feedback', String(val));
  };

  const setHasCompletedLanguage = (val: boolean) => {
    setHasCompletedLanguageState(val);
    if (typeof window !== 'undefined') localStorage.setItem('amap_ob_lang', String(val));
  };

  const setHasCompletedAccessibility = (val: boolean) => {
    setHasCompletedAccessibilityState(val);
    if (typeof window !== 'undefined') localStorage.setItem('amap_ob_acc', String(val));
  };

  const setHasCompletedGestureCalibration = (val: boolean) => {
    setHasCompletedGestureCalibrationState(val);
    if (typeof window !== 'undefined') localStorage.setItem('amap_ob_gest', String(val));
  };

  const setHasCompletedVoiceSetup = (val: boolean) => {
    setHasCompletedVoiceSetupState(val);
    if (typeof window !== 'undefined') localStorage.setItem('amap_ob_voice', String(val));
  };

  const setHasCompletedTraining = (val: boolean) => {
    setHasCompletedTrainingState(val);
    if (typeof window !== 'undefined') localStorage.setItem('amap_ob_train', String(val));
  };

  const isReady =
    hasCompletedLanguage &&
    hasCompletedAccessibility &&
    (modality === 'voice' || hasCompletedGestureCalibration) &&
    (modality === 'gesture' || hasCompletedVoiceSetup) &&
    hasCompletedTraining;

  const announce = (text: string) => {
    setLiveAnnouncement(text);
  };

  const playAudioCue = (type: 'confirm' | 'alert' | 'stop' | 'step') => {
    if (!audioFeedback || typeof window === 'undefined') return;
    try {
      const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new AudioContextClass();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.connect(gain);
      gain.connect(ctx.destination);

      if (type === 'confirm') {
        osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
        osc.frequency.setValueAtTime(880.0, ctx.currentTime + 0.08); // A5
        gain.gain.setValueAtTime(0.15, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.25);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + 0.25);
      } else if (type === 'step') {
        osc.frequency.setValueAtTime(440.0, ctx.currentTime); // A4
        gain.gain.setValueAtTime(0.1, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + 0.15);
      } else if (type === 'alert') {
        osc.frequency.setValueAtTime(329.63, ctx.currentTime); // E4
        osc.frequency.setValueAtTime(261.63, ctx.currentTime + 0.1); // C4
        gain.gain.setValueAtTime(0.2, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.35);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + 0.35);
      } else if (type === 'stop') {
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(180, ctx.currentTime);
        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + 0.4);
      }
    } catch {
      // AudioContext unavailable or blocked by autoplay policy
    }
  };

  return (
    <AccessibilityContext.Provider
      value={{
        language,
        setLanguage,
        modality,
        setModality,
        highContrast,
        setHighContrast,
        textScale,
        setTextScale,
        reducedMotion,
        setReducedMotion,
        audioFeedback,
        setAudioFeedback,
        playAudioCue,
        announce,
        liveAnnouncement,
        hasCompletedLanguage,
        setHasCompletedLanguage,
        hasCompletedAccessibility,
        setHasCompletedAccessibility,
        hasCompletedGestureCalibration,
        setHasCompletedGestureCalibration,
        hasCompletedVoiceSetup,
        setHasCompletedVoiceSetup,
        hasCompletedTraining,
        setHasCompletedTraining,
        isReady,
      }}
    >
      <div
        className={`${highContrast ? 'theme-high-contrast' : ''} ${reducedMotion ? 'reduce-motion' : ''}`}
        style={{ fontSize: `${textScale * 100}%` }}
      >
        {/* Screen Reader Live Region (§ 28) */}
        <div aria-live="polite" aria-atomic="true" className="sr-only">
          {liveAnnouncement}
        </div>
        {children}
      </div>
    </AccessibilityContext.Provider>
  );
}

export function useAccessibility() {
  const context = useContext(AccessibilityContext);
  if (!context) {
    throw new Error('useAccessibility must be used within an AccessibilityProvider');
  }
  return context;
}
