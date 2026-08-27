# AMAP AI Subsystem Specification & Architecture

> **Accessible Multimodal Assembly Platform (AMAP) - Multi-Signal AI Perception, Intent Recognition & Adaptation Layer**

---

## 1. Architectural Invariant

The AI subsystem adheres to the AMAP foundational principle:
$$\mathbf{Recognition \neq Intent \neq Authorization \neq Execution}$$

- **Recognition (Perception):** Captures raw optical 3D hand landmarks and acoustic speech transcripts.
- **Intent (Semantic Resolution):** Cross-modal temporal fusion, phonetic normalization, and dwell accumulation filter involuntary tremors and form validated intent candidates.
- **Authorization (Governance):** Multi-tenant JWT claims and RBAC gate permissions.
- **Execution (Physical Action):** Deterministic safety interlocks mandate dual-confirmation for safety-critical actions before machine dispatch.

---

## 2. Directory Structure

```text
ai/
├── __init__.py                  # Root package exports (AIEngine, AIService, config, version)
├── config.py                    # AI hyperparameters, thresholds, temporal window bounds
├── pipeline.py                  # Unified MultimodalAIPipeline orchestrator
├── service.py                   # High-level API service layer
├── cli.py                       # Diagnostic and benchmark CLI utility
├── models/                      # Domain data types, schemas, and classifiers
│   ├── __init__.py
│   ├── types.py                 # LandmarkPoint, BoundingBox, DwellState, AcousticFeatures, etc.
│   ├── classifier.py            # GeometricClassifier, StatisticalClassifier, MockClassifier
│   └── registry.py              # Model backend registry
├── gesture/                     # Optical hand-tracking & tremor filter
│   ├── __init__.py
│   ├── landmarks.py             # 21 3D MediaPipe landmark vector geometry & jitter calculation
│   ├── recognizer.py            # Gesture recognizer & spatial pointer tracker
│   ├── dwell.py                 # Temporal dwell accumulator & adaptive EMA tremor smoother
│   ├── spatial.py               # 2D/3D spatial target collision detector (hit testing)
│   └── dataset.py               # Synthetic landmark generator & calibrator
├── voice/                       # Acoustic command processing & phonetic matching
│   ├── __init__.py
│   ├── vocabulary.py            # Bounded workplace command dictionary with safety ratings
│   ├── preprocessor.py          # Voice Activity Detection (VAD) & token normalization
│   ├── noise_filter.py          # Acoustic noise cancellation filter & SNR estimator
│   └── recognizer.py            # Soundex/Metaphone phonetic keyword spotter & fuzzy matcher
├── intent/                      # Cross-modal temporal fusion & safety gating
│   ├── __init__.py
│   ├── fusion.py                # Temporal window correlation ($c_{fused} = 1 - (1-c_1)(1-c_2)$)
│   ├── safety.py                # Safety interlock evaluator for critical machine commands
│   └── assistant.py             # Contextual worker assistant & admin workflow synthesizer
└── personalization/             # Evidence-based adaptation engine
    ├── __init__.py
    ├── analyzer.py              # Multi-signal difficulty pattern detector (tremor, timeout, noise)
    └── recommender.py           # Structured adaptation recommendation generator (>=3 in 20 interactions)
```

---

## 3. Mathematical & Algorithmic Foundations

### 3.1 Cross-Modal Reinforcing Fusion
When gesture and speech agree on candidate intent within temporal window $\Delta t \in [500\text{ms}, 2500\text{ms}]$, confidence reinforces according to:
$$c_{\text{fused}} = 1 - (1 - c_{\text{gesture}}) \times (1 - c_{\text{voice}})$$

### 3.2 Involuntary Tremor Smoothing
Spatial pointer coordinates undergo adaptive Exponential Moving Average (EMA) low-pass filtering:
$$P_t = \alpha \cdot X_t + (1 - \alpha) \cdot P_{t-1}$$
where $\alpha = 0.20$ when high-frequency acceleration jitter $> 0.045$ is detected, dampening micro-spasms and motor tremors.

### 3.3 Rule of Multi-Signal Evidence for Personalization
The adaptation engine never adjusts worker parameters based on single outlier events. An adaptation proposal is formulated only when:
$$\sum_{i=1}^{W} \mathbb{I}(\text{difficulty}_i) \ge 3 \quad \text{for sliding window } W = 20$$

---

## 4. Benchmark & Diagnostic CLI

Run the diagnostic benchmark to verify optical, voice, and fusion performance:
```bash
python -m ai.cli --benchmark
```
*Expected Throughput: $\ge 5000$ optical frames/sec, latency $< 0.2\text{ms}$.*
