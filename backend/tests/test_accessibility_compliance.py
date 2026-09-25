"""
WCAG 2.1 AA Accessibility & Inclusive Interaction Verification Suite (Phase 17).
Validates accessibility design tokens, ARIA markup contracts, minimum touch targets (>=48px),
high contrast theme properties, keyboard navigation semantics, and screen reader feedback regions.
"""

from pathlib import Path
import pytest


def test_wcag_css_design_system_tokens_and_accessibility():
    css_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "app" / "globals.css"
    assert css_path.exists(), "globals.css must exist"

    css_content = css_path.read_text(encoding="utf-8")

    # 1. Accessible Touch Target Height (>= 48px per WCAG 2.5.5 / 2.5.8)
    assert "min-height: 48px;" in css_content, "Buttons and touch targets must meet the 48px minimum touch standard"

    # 2. Visible Focus Ring Outline (WCAG 2.4.7 Focus Visible)
    assert ":focus-visible" in css_content, "Visible focus indicator must be explicitly defined"
    assert "outline:" in css_content, "Focus outline must be rendered"

    # 3. High Contrast Mode Definition
    assert "body.high-contrast" in css_content, "High contrast mode styling must be provided"
    assert "#000000" in css_content, "High contrast background must provide pure black floor"
    assert "#ffffff" in css_content, "High contrast text must provide pure white ceiling"


def test_wcag_aria_landmarks_in_shared_components():
    navbar_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "shared" / "components" / "NavBar.tsx"
    assert navbar_path.exists(), "NavBar.tsx must exist"

    navbar_code = navbar_path.read_text(encoding="utf-8")

    # Semantic navigation landmark
    assert 'aria-label="Main Navigation"' in navbar_code
    assert "aria-pressed=" in navbar_code, "High contrast toggle must have aria-pressed state"
    assert 'aria-label="Toggle High Contrast Mode"' in navbar_code


def test_wcag_screen_reader_live_regions_in_worker_station():
    worker_page_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "app" / "worker" / "page.tsx"
    assert worker_page_path.exists(), "Worker page.tsx must exist"

    worker_code = worker_page_path.read_text(encoding="utf-8")

    # Screen reader announcement region (WCAG 4.1.3 Status Messages)
    assert 'aria-live="polite"' in worker_code, "Worker status updates must be announced via aria-live polite"
    assert 'role="alert"' in worker_code, "Emergency stop banner must declare alert role for immediate interruption"


def test_wcag_accessible_modal_dialog_semantics():
    modal_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "worker" / "components" / "AssistanceModal.tsx"
    assert modal_path.exists(), "AssistanceModal.tsx must exist"

    modal_code = modal_path.read_text(encoding="utf-8")

    # Accessible Dialog Attributes (WCAG 2.1 Dialog Pattern)
    assert 'role="dialog"' in modal_code
    assert 'aria-modal="true"' in modal_code
    assert 'aria-labelledby="assistance-modal-title"' in modal_code
    assert 'aria-label="Close modal"' in modal_code


def test_wcag_non_reliance_on_color_alone():
    hud_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "worker" / "components" / "MultimodalHUD.tsx"
    assert hud_path.exists(), "MultimodalHUD.tsx must exist"

    hud_code = hud_path.read_text(encoding="utf-8")

    # Verify visual text + icon pairings for multimodal recognition states
    assert "🖐️" in hud_code
    assert "🎙️" in hud_code
    assert "⚡" in hud_code
    assert "CONF" in hud_code


def test_wcag_semantic_html_structure_in_layout():
    layout_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "app" / "layout.tsx"
    assert layout_path.exists(), "layout.tsx must exist"

    layout_code = layout_path.read_text(encoding="utf-8")
    assert '<html lang="en">' in layout_code, "Document must declare html lang attribute (WCAG 3.1.1)"
    assert '<main id="main-content"' in layout_code, "Primary container must be semantic <main> landmark"


def test_sr_only_utility_css_definition():
    """Phase 6 Check 1 & 8: Verify .sr-only visually-hidden utility is explicitly defined with clipping."""
    css_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "app" / "globals.css"
    css_content = css_path.read_text(encoding="utf-8")

    assert ".sr-only" in css_content, ".sr-only class must be defined in globals.css"
    assert "position: absolute;" in css_content
    assert "clip: rect(0, 0, 0, 0);" in css_content
    assert "width: 1px;" in css_content
    assert "height: 1px;" in css_content
    assert "display: none" not in css_content.split(".sr-only")[1].split("}")[0], ".sr-only must not use display:none"


def test_high_contrast_theme_class_sync():
    """Phase 6 Check 1 & 9: Verify .theme-high-contrast is styled and synchronized with the context."""
    css_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "app" / "globals.css"
    css_content = css_path.read_text(encoding="utf-8")

    assert ".theme-high-contrast" in css_content, ".theme-high-contrast must be styled in globals.css"
    assert "body.high-contrast" in css_content, "body.high-contrast must also be preserved"
    assert "#000000" in css_content, "High contrast must provide pure black background floor"
    assert "#ffffff" in css_content, "High contrast must provide pure white text ceiling"


def test_reduced_motion_media_query_and_class():
    """Phase 6 Check 15: Verify OS preference and application-level reduced motion overrides."""
    css_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "app" / "globals.css"
    css_content = css_path.read_text(encoding="utf-8")

    assert "@media (prefers-reduced-motion: reduce)" in css_content, "prefers-reduced-motion media query must be defined"
    assert ".reduce-motion" in css_content, ".reduce-motion class override must be defined"
    assert "animation-duration: 0.01ms !important;" in css_content


def test_skip_to_main_content_link_in_layout():
    """Phase 6 Check 6: Verify keyboard-accessible skip link targets #main-content."""
    layout_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "app" / "layout.tsx"
    layout_code = layout_path.read_text(encoding="utf-8")

    assert '<a href="#main-content" className="skip-link"' in layout_code, "Skip link must point to #main-content"

    css_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "app" / "globals.css"
    css_content = css_path.read_text(encoding="utf-8")
    assert ".skip-link" in css_content, ".skip-link class must be defined in globals.css"
    assert ".skip-link:focus" in css_content, ".skip-link:focus must be visibly rendered on focus"


def test_login_inputs_focus_ring_not_suppressed():
    """Phase 6 Check 6 & 7: Verify login inputs do not suppress visible focus indicator."""
    login_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "app" / "login" / "page.tsx"
    login_code = login_path.read_text(encoding="utf-8")

    assert "outline: 'none'" not in login_code, "outline: 'none' must not be applied to login inputs"


def test_assistance_modal_escape_handling():
    """Phase 6 Check 7: Verify AssistanceModal handles Escape key dismissal."""
    modal_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "worker" / "components" / "AssistanceModal.tsx"
    modal_code = modal_path.read_text(encoding="utf-8")

    assert "e.key === 'Escape'" in modal_code, "Escape key handler must be implemented in AssistanceModal"
    assert "onClose()" in modal_code


def test_assistance_modal_focus_containment():
    """Phase 6 Check 7: Verify AssistanceModal implements keyboard focus trapping and restoration."""
    modal_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "worker" / "components" / "AssistanceModal.tsx"
    modal_code = modal_path.read_text(encoding="utf-8")

    assert "e.key === 'Tab'" in modal_code, "Tab key focus trap must be implemented"
    assert "previousActiveElementRef" in modal_code, "Previous active element must be preserved for restoration"
    assert "closeBtnRef.current?.focus()" in modal_code, "Focus must be moved into modal upon opening"


def test_interactive_target_minimums_enforced():
    """Phase 6 Check 10: Verify 48px minimum touch targets across critical navigation and action controls."""
    navbar_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "shared" / "components" / "NavBar.tsx"
    navbar_code = navbar_path.read_text(encoding="utf-8")
    assert "minHeight: '48px'" in navbar_code, "NavBar controls must have 48px minHeight"

    modal_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "worker" / "components" / "AssistanceModal.tsx"
    modal_code = modal_path.read_text(encoding="utf-8")
    assert "minHeight: '48px'" in modal_code, "AssistanceModal controls must have 48px minHeight"

    worker_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "app" / "worker" / "page.tsx"
    worker_code = worker_path.read_text(encoding="utf-8")
    assert "minHeight: '48px'" in worker_code, "Worker workstation action controls must have 48px minHeight"


def test_progressbar_aria_attributes_in_hand_tracker():
    """Phase 6 Check 5: Verify dwell timer progressbar ARIA attributes in MediaPipeHandTracker."""
    tracker_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "worker" / "components" / "MediaPipeHandTracker.tsx"
    tracker_code = tracker_path.read_text(encoding="utf-8")

    assert 'role="progressbar"' in tracker_code, "Dwell bar must declare role='progressbar'"
    assert "aria-valuenow=" in tracker_code
    assert "aria-valuemin=" in tracker_code
    assert "aria-valuemax=" in tracker_code


def test_client_document_language_synchronization():
    """Phase 6 Check 19: Verify client-side synchronization of document.documentElement.lang without SSR mismatch."""
    context_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "shared" / "theme" / "AccessibilityContext.tsx"
    context_code = context_path.read_text(encoding="utf-8")

    assert "document.documentElement.lang = activeLang" in context_code, "Client must sync document.documentElement.lang"
    assert "'en', 'es', 'ta', 'hi', 'de'" in context_code, "Must validate supported AMAP language codes"

