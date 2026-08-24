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
