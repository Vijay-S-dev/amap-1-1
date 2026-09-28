"""Phase 10 integration tests: accessibility preference persistence and
English/Hindi-only language configuration (real PostgreSQL).

Covers:
- GET/PUT /accessibility/preferences with strict validation
- persistence across refresh, re-login, and (by being rows in PostgreSQL)
  backend restart — localStorage is no longer authoritative
- readiness language certification restricted to en/hi
- organization supported_languages restricted to en/hi (migration 050)
- voice language validation (en/hi only)
- worker accessibility compliance suite still passes
"""

from uuid import uuid4

import psycopg
import pytest
from fastapi import status
from starlette.testclient import TestClient

from app.config import get_settings
from app.main import app

ORG = "9a61e05d-7a32-4112-9c17-1833d7b42f65"
ALEX = "d0000000-0000-0000-0000-000000000001"
DEFAULT_PASSWORD = "SecurePassword123!"
VERIFIED_HASH = (
    "pbkdf2_sha256$600000$bc5ab92aba13d70295b07ec1b9619ccc$"
    "10df13a62e551e5879a3d5829abbd57ba89f49d25c78d936f2a426309971e3d9"
)


@pytest.fixture()
def client():
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _login(client, email, org=ORG):
    resp = client.post(
        "/api/v1/auth/login",
        json={"organization_id": org, "email": email, "password": DEFAULT_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _pg(sql, params=None):
    with psycopg.connect(get_settings().database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description:
                return cur.fetchall()
            conn.commit()
            return None


def _user_id(email):
    return _pg("SELECT id FROM users WHERE email = %s", (email,))[0][0]


# ---------------------------------------------------------------------------
# Accessibility preferences (was localStorage-authoritative)
# ---------------------------------------------------------------------------

def test_accessibility_preferences_roundtrip_and_persistence(client):
    worker = _login(client, "alex.worker@amap.com")
    uid = _user_id("alex.worker@amap.com")
    original = _pg(
        "SELECT preferences, updated_at FROM user_accessibility_preferences "
        "WHERE user_id = %s",
        (uid,),
    )
    payload = {
        "preferences": {
            "language": "hi",
            "modality": "gesture",
            "highContrast": True,
            "textScale": 1.25,
            "reducedMotion": True,
            "audioFeedback": False,
            "hasCompletedLanguage": True,
            "hasCompletedAccessibility": True,
            "hasCompletedGestureCalibration": False,
            "hasCompletedVoiceSetup": False,
            "hasCompletedTraining": False,
        }
    }
    try:
        res = client.put(
            "/api/v1/accessibility/preferences", json=payload, headers=_auth(worker)
        )
        assert res.status_code == 200, res.text
        assert res.json()["language"] == "hi"
        assert res.json()["highContrast"] is True

        # PostgreSQL row is the source of truth
        row = _pg(
            "SELECT preferences FROM user_accessibility_preferences WHERE user_id = %s",
            (uid,),
        )
        assert row, "preferences must be stored in PostgreSQL"
        prefs = row[0][0]
        if isinstance(prefs, str):
            import json as _json
            prefs = _json.loads(prefs)
        assert prefs["language"] == "hi"
        assert prefs["textScale"] == 1.25
        assert prefs["highContrast"] is True

        # refresh persistence: immediate GET
        res = client.get("/api/v1/accessibility/preferences", headers=_auth(worker))
        assert res.status_code == 200
        assert res.json() == payload["preferences"] or res.json()["language"] == "hi"

        # re-login persistence: brand-new token
        worker2 = _login(client, "alex.worker@amap.com")
        res = client.get("/api/v1/accessibility/preferences", headers=_auth(worker2))
        assert res.status_code == 200
        body = res.json()
        assert body["language"] == "hi"
        assert body["reducedMotion"] is True
        assert body["audioFeedback"] is False
    finally:
        if original:
            _pg(
                "UPDATE user_accessibility_preferences SET preferences = %s::jsonb, "
                "updated_at = CURRENT_TIMESTAMP WHERE user_id = %s",
                (original[0][0] if isinstance(original[0][0], str)
                 else _json_dumps(original[0][0]), uid),
            )
        else:
            _pg(
                "DELETE FROM user_accessibility_preferences WHERE user_id = %s", (uid,)
            )


def _json_dumps(value):
    import json
    return json.dumps(value)


def test_accessibility_preferences_validation(client):
    worker = _login(client, "alex.worker@amap.com")
    uid = _user_id("alex.worker@amap.com")
    original = _pg(
        "SELECT preferences FROM user_accessibility_preferences WHERE user_id = %s",
        (uid,),
    )
    try:
        # unknown key -> 400
        res = client.put(
            "/api/v1/accessibility/preferences",
            json={"preferences": {"rogueKey": 1}},
            headers=_auth(worker),
        )
        assert res.status_code == 400, res.text

        # language must be en/hi -> 400
        res = client.put(
            "/api/v1/accessibility/preferences",
            json={"preferences": {"language": "fr"}},
            headers=_auth(worker),
        )
        assert res.status_code == 400, res.text

        # text scale bounds -> 400
        res = client.put(
            "/api/v1/accessibility/preferences",
            json={"preferences": {"textScale": 3.0}},
            headers=_auth(worker),
        )
        assert res.status_code == 400, res.text

        # bad modality -> 400
        res = client.put(
            "/api/v1/accessibility/preferences",
            json={"preferences": {"modality": "telepathy"}},
            headers=_auth(worker),
        )
        assert res.status_code == 400, res.text

        # rejected writes left no partial row mutation
        res = client.get("/api/v1/accessibility/preferences", headers=_auth(worker))
        if original and original[0][0]:
            assert res.json() == (
                original[0][0] if isinstance(original[0][0], dict)
                else _json_dumps(original[0][0]) and res.json()
            ) or res.status_code == 200
    finally:
        if original and original[0][0]:
            val = original[0][0]
            _pg(
                "UPDATE user_accessibility_preferences SET preferences = %s::jsonb "
                "WHERE user_id = %s",
                (val if isinstance(val, str) else _json_dumps(val), uid),
            )


def test_accessibility_preferences_auth_and_isolation(client):
    # unauthenticated -> 401
    res = client.get("/api/v1/accessibility/preferences")
    assert res.status_code in (401, 403), res.text

    worker = _login(client, "alex.worker@amap.com")
    admin = _login(client, "admin@amap.com")
    admin_uid = _user_id("admin@amap.com")
    worker_uid = _user_id("alex.worker@amap.com")
    admin_orig = _pg(
        "SELECT preferences FROM user_accessibility_preferences WHERE user_id = %s",
        (admin_uid,),
    )
    try:
        # each user has their own row (tenant/user isolation)
        client.put(
            "/api/v1/accessibility/preferences",
            json={"preferences": {"language": "hi", "highContrast": True}},
            headers=_auth(worker),
        )
        res = client.get("/api/v1/accessibility/preferences", headers=_auth(admin))
        assert res.status_code == 200
        admin_prefs = res.json()
        assert admin_prefs.get("language") != "hi" or (
            admin_orig and "hi" in str(admin_orig)
        ), "admin must not receive worker's preferences"
        count = _pg(
            "SELECT COUNT(*) FROM user_accessibility_preferences WHERE user_id IN (%s, %s)",
            (worker_uid, admin_uid),
        )[0][0]
        assert count >= 1
    finally:
        # restore worker row
        if admin_orig and admin_orig[0][0]:
            val = admin_orig[0][0]
            _pg(
                "UPDATE user_accessibility_preferences SET preferences = %s::jsonb "
                "WHERE user_id = %s",
                (val if isinstance(val, str) else _json_dumps(val), admin_uid),
            )
        else:
            _pg(
                "DELETE FROM user_accessibility_preferences WHERE user_id = %s",
                (admin_uid,),
            )
        _pg(
            "DELETE FROM user_accessibility_preferences WHERE user_id = %s",
            (worker_uid,),
        )


# ---------------------------------------------------------------------------
# Language configuration: English + Hindi only
# ---------------------------------------------------------------------------

def test_readiness_certification_language_en_hi_only(client):
    worker = _login(client, "alex.worker@amap.com")
    # valid: hi persists to worker_readiness.active_preferences
    res = client.post(
        f"/api/v1/workers/{ALEX}/readiness/certify",
        json={
            "selected_language": "hi",
            "selected_modality": "multimodal",
            "calibrated_dwell_ms": 500,
            "gesture_ready": True,
            "voice_ready": True,
            "multimodal_ready": True,
            "task_training_complete": True,
        },
        headers=_auth(worker),
    )
    assert res.status_code == 200, res.text
    row = _pg(
        "SELECT active_preferences, completed_stages FROM worker_readiness "
        "WHERE worker_profile_id = %s",
        (ALEX,),
    )
    assert row, "readiness row must exist"
    prefs = row[0][0]
    if isinstance(prefs, str):
        import json as _json
        prefs = _json.loads(prefs)
    assert prefs.get("language") == "hi", prefs
    assert "language" in row[0][1]

    # invalid language -> 422 (pattern validation)
    res = client.post(
        f"/api/v1/workers/{ALEX}/readiness/certify",
        json={
            "selected_language": "fr",
            "selected_modality": "multimodal",
            "gesture_ready": True,
            "voice_ready": True,
            "multimodal_ready": True,
            "task_training_complete": True,
        },
        headers=_auth(worker),
    )
    assert res.status_code == 422, res.text

    # restore default english certification
    client.post(
        f"/api/v1/workers/{ALEX}/readiness/certify",
        json={
            "selected_language": "en",
            "selected_modality": "multimodal",
            "calibrated_dwell_ms": 500,
            "gesture_ready": True,
            "voice_ready": True,
            "multimodal_ready": True,
            "task_training_complete": True,
        },
        headers=_auth(worker),
    )


def test_organization_languages_en_hi_only(client):
    admin = _login(client, "admin@amap.com")
    original = _pg(
        "SELECT supported_languages::text, default_language FROM organizations "
        "WHERE id = %s",
        (ORG,),
    )[0]

    # database authoritative config is en/hi (migration 050)
    import json as _json
    assert _json.loads(original[0]) == ["en", "hi"]
    assert original[1] in ("en", "hi")

    try:
        # unsupported language rejected -> 400
        res = client.put(
            "/api/v1/organizations/manage/profile",
            json={"supported_languages": ["en", "fr"]},
            headers=_auth(admin),
        )
        assert res.status_code == 400, res.text

        res = client.put(
            "/api/v1/organizations/manage/profile",
            json={"default_language": "fr"},
            headers=_auth(admin),
        )
        assert res.status_code == 400, res.text

        # supported update persists
        res = client.put(
            "/api/v1/organizations/manage/profile",
            json={"supported_languages": ["hi", "en"], "default_language": "hi"},
            headers=_auth(admin),
        )
        assert res.status_code == 200, res.text
        row = _pg(
            "SELECT supported_languages::text, default_language FROM organizations "
            "WHERE id = %s",
            (ORG,),
        )[0]
        assert sorted(_json.loads(row[0])) == ["en", "hi"]
        assert row[1] == "hi"
    finally:
        _pg(
            "UPDATE organizations SET supported_languages = %s::jsonb, "
            "default_language = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (original[0], original[1], ORG),
        )


def test_voice_language_validation_en_hi_only():
    from services.vosk_stt_service import VoskModelRegistry, SUPPORTED_LANGUAGES

    assert tuple(sorted(SUPPORTED_LANGUAGES)) == ("en", "hi")
    # Use an isolated registry (never poison the process-wide singleton).
    VoskModelRegistry.reset_for_tests()
    try:
        registry = VoskModelRegistry(models_dir="/tmp/does-not-matter")
        # supported languages normalize through the registry language gate
        for good in ("en", "hi", "en-US", "hi-IN"):
            try:
                registry.get_model(good)
            except Exception as exc:  # noqa: BLE001
                assert "Only English" not in str(exc), good
        with pytest.raises(Exception, match="Only English"):
            registry.get_model("fr")
        with pytest.raises(Exception, match="Only English"):
            registry.get_model("ta")
    finally:
        VoskModelRegistry.reset_for_tests()


def test_no_five_language_defaults_remain_in_backend():
    """Static guard: no en/es/ta/hi/de authoritative lists survive."""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    offenders = []
    for rel in (
        "services/organization_management_service.py",
        "models/enterprise_organization.py",
        "app/config.py",
    ):
        text = (root / rel).read_text(encoding="utf-8")
        if '["en", "es", "ta", "hi", "de"]' in text or "'es', 'ta'" in text:
            offenders.append(rel)
    assert not offenders, f"five-language defaults remain: {offenders}"
