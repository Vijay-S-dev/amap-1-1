# AMAP Frontend Workstation Studio

Next.js 14+ / React 18+ Accessible Manufacturing Interface for AMAP.

---

## 🎨 Design System & Accessibility (WCAG 2.1 AA)

- **Pure Vanilla CSS:** Custom crafted CSS architecture in `app/globals.css` with dark mode glassmorphism and high-contrast toggle.
- **Minimum Touch Standard (WCAG 2.5.5 / 2.5.8):** Strict `min-height: 48px` and `min-width: 48px` on all interactive buttons and inputs.
- **Focus Rings (WCAG 2.4.7):** Visible `:focus-visible` styling ensuring keyboard-only operators can track focus location at all times.
- **Color Independence (WCAG 1.4.1):** Every status conveys meaning via icons, text labels, and badges simultaneously.
- **Screen Reader Support (WCAG 4.1.3):** Live update announcements (`aria-live="polite"`), modal dialog semantics (`role="dialog"`), and immediate emergency alerts (`role="alert"`).

---

## 🖥️ Portals

1. **Worker Station (`/worker`):**
   - Live multimodal HUD displaying recognized gesture and voice signals.
   - Circular dwell countdown timer for tremor-safe action selection.
   - Workflow step viewer with spatial bounding boxes and part verification.
   - Instant assistance ticket modal and emergency stop lockout banner.

2. **Supervisor Station (`/organization`):**
   - Factory floor telemetry, active session counters, and station health metrics.
   - Live assistance queue with single-click ticket assignment and resolution.

3. **Admin Studio (`/admin`):**
   - Interaction configuration preset editor (dwell times, sensitivity thresholds).
   - Evidence-based adaptation review panel for approving worker personalization adjustments.
   - Tamper-proof audit trail explorer.

---

## 🚀 Running Locally

```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` in your web browser.
