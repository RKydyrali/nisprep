"""End-to-end API tests: auth, sessions, error log, analytics, health.

Runs against an in-memory sqlite DB (aiosqlite) and a fakeredis stub —
no network calls, no real Redis/Postgres needed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import ChildAccount, ErrorLogItem, QuestionTemplate, User
from app.services import auth_service
from app.services.clone_generator_service import safe_eval

pytestmark = pytest.mark.asyncio


async def register_parent(client, email: str = "parent@test.dev", password: str = "secret123") -> dict:
    resp = await client.post(
        "/api/v1/auth/parent/register",
        json={"full_name": "Тест Родитель", "email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return {"token": data["access_token"], "email": email, "password": password}


async def create_child(client, parent_token: str, username: str = "child_test") -> dict:
    resp = await client.post(
        "/api/v1/auth/children",
        headers={"Authorization": f"Bearer {parent_token}"},
        json={
            "full_name": "Тест Ученик",
            "telegram_username": username,
            "password": "child12345",
            "language": "ru",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["activation_code"], "activation_code must be returned to the parent"
    assert len(data["activation_code"]) == 8
    return {"child": data, "password": "child12345"}


async def child_login(client, username: str, password: str, otp: str | None, redis) -> dict:
    return await client.post(
        "/api/v1/auth/child/login-otp",
        json={"telegram_username": username, "password": password, "otp": otp},
    )


async def verify_child_and_login(client, child_id: int, username: str, password: str, redis) -> str:
    await redis.delete(f"otp:{child_id}")
    otp = await auth_service.issue_otp(redis, child_id)
    resp = await child_login(client, username, password, otp, redis)
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def test_parent_register_and_duplicate(client, db):
    resp = await client.post(
        "/api/v1/auth/parent/register",
        json={"full_name": "Родитель", "email": "a@b.dev", "password": "secret123"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()

    dup = await client.post(
        "/api/v1/auth/parent/register",
        json={"full_name": "Родитель", "email": "a@b.dev", "password": "secret123"},
    )
    assert dup.status_code == 409


async def test_parent_login_ok_and_bad_password(client, db):
    await register_parent(client, email="login@test.dev")
    ok = await client.post(
        "/api/v1/auth/parent/login",
        json={"email": "login@test.dev", "password": "secret123"},
    )
    assert ok.status_code == 200
    assert "access_token" in ok.json()

    bad = await client.post(
        "/api/v1/auth/parent/login",
        json={"email": "login@test.dev", "password": "wrong-pass"},
    )
    assert bad.status_code == 401


async def test_create_child_returns_activation_code_and_duplicate_409(client, db):
    parent = await register_parent(client, email="parent2@test.dev")
    created = await create_child(client, parent["token"], username="unique_child")
    assert created["child"]["activation_code"]

    dup = await client.post(
        "/api/v1/auth/children",
        headers={"Authorization": f"Bearer {parent['token']}"},
        json={
            "full_name": "Другой",
            "telegram_username": "unique_child",
            "password": "child12345",
            "language": "ru",
        },
    )
    assert dup.status_code == 409


async def test_child_login_otp_wrong_then_right(client, db, redis, seeded):
    parent = await register_parent(client, email="parent3@test.dev")
    child = await create_child(client, parent["token"], username="otp_child")
    child_id = child["child"]["id"]
    child_row = await db.get(ChildAccount, child_id)
    child_row.is_verified = True
    await db.commit()

    wrong = await child_login(client, "otp_child", "child12345", "000000", redis)
    assert wrong.status_code == 401

    otp = await auth_service.issue_otp(redis, child_id)
    ok = await child_login(client, "otp_child", "child12345", otp, redis)
    assert ok.status_code == 200, ok.text
    assert "access_token" in ok.json()

    missing_otp = await child_login(client, "otp_child", "child12345", None, redis)
    assert missing_otp.status_code == 422


async def test_session_start_sprint_question(client, db, redis, seeded):
    parent = await register_parent(client, email="parent4@test.dev")
    child = await create_child(client, parent["token"], username="sprint_child")
    child_id = child["child"]["id"]
    child["child"]["is_verified"] = True
    child_row = await db.get(ChildAccount, child_id)
    child_row.is_verified = True
    await db.commit()

    token = await verify_child_and_login(client, child_id, "sprint_child", "child12345", redis)

    resp = await client.post(
        "/api/v1/session/start",
        headers={"Authorization": f"Bearer {token}"},
        json={"mode": "sprint"},
    )
    assert resp.status_code == 200, resp.text
    q = resp.json()
    assert q["session_id"]
    assert q["question_id"] == 1
    assert q["question_text"]
    assert q["answer_type"] == "float"
    assert q["time_limit_sec"] == 30
    assert q["mode"] == "sprint"
    assert q["progress"] == pytest.approx(1 / 10, abs=0.01)
    assert q["micro_skill"]["id"] > 0


async def test_session_submit_correct_and_next(client, db, redis, seeded):
    parent = await register_parent(client, email="parent5@test.dev")
    child = await create_child(client, parent["token"], username="submit_child")
    child_id = child["child"]["id"]
    child_row = await db.get(ChildAccount, child_id)
    child_row.is_verified = True
    await db.commit()
    token = await verify_child_and_login(client, child_id, "submit_child", "child12345", redis)

    start = await client.post(
        "/api/v1/session/start",
        headers={"Authorization": f"Bearer {token}"},
        json={"mode": "sprint"},
    )
    q = start.json()

    from app.models import QuestionTemplate

    template = await db.get(QuestionTemplate, q["template_id"])
    correct = safe_eval(template.answer_expr, q["params"])

    submit = await client.post(
        "/api/v1/session/submit",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "session_id": q["session_id"],
            "template_id": q["template_id"],
            "params": q["params"],
            "answer": correct,
            "time_taken_sec": 12.0,
        },
    )
    assert submit.status_code == 200, submit.text
    body = submit.json()
    assert body["is_correct"] is True
    assert body["next_question"] is not None
    assert body["session_finished"] is False
    assert body["theta_after"] is not None
    assert body["elo_after"] is not None


async def test_session_submit_wrong_creates_due_error_log(client, db, redis, seeded):
    parent = await register_parent(client, email="parent6@test.dev")
    child = await create_child(client, parent["token"], username="err_child")
    child_id = child["child"]["id"]
    child_row = await db.get(ChildAccount, child_id)
    child_row.is_verified = True
    await db.commit()
    token = await verify_child_and_login(client, child_id, "err_child", "child12345", redis)

    start = await client.post(
        "/api/v1/session/start",
        headers={"Authorization": f"Bearer {token}"},
        json={"mode": "sprint"},
    )
    q = start.json()
    submit = await client.post(
        "/api/v1/session/submit",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "session_id": q["session_id"],
            "template_id": q["template_id"],
            "params": q["params"],
            "answer": -999,
            "time_taken_sec": 10.0,
        },
    )
    assert submit.status_code == 200, submit.text
    assert submit.json()["is_correct"] is False

    due = await client.get(
        "/api/v1/smart-error-log/due",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert due.status_code == 200, due.text
    items = due.json()["items"]
    assert len(items) >= 1
    item = items[0]
    assert item["question"]["template_id"] == q["template_id"]
    assert item["question"]["question_text"]
    assert item["review_number"] >= 1


async def test_analytics_readiness(client, db, redis, seeded):
    parent = await register_parent(client, email="parent7@test.dev")
    child = await create_child(client, parent["token"], username="analytics_child")
    child_id = child["child"]["id"]
    child_row = await db.get(ChildAccount, child_id)
    child_row.is_verified = True
    await db.commit()
    token = await verify_child_and_login(client, child_id, "analytics_child", "child12345", redis)

    start = await client.post(
        "/api/v1/session/start",
        headers={"Authorization": f"Bearer {token}"},
        json={"mode": "sprint"},
    )
    q = start.json()
    from app.models import QuestionTemplate

    template = await db.get(QuestionTemplate, q["template_id"])
    correct = safe_eval(template.answer_expr, q["params"])
    await client.post(
        "/api/v1/session/submit",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "session_id": q["session_id"],
            "template_id": q["template_id"],
            "params": q["params"],
            "answer": correct,
            "time_taken_sec": 5.0,
        },
    )

    resp = await client.get(
        "/api/v1/analytics/readiness",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "psi" in body
    assert "p_grant" in body
    assert "weak_skills" in body
    assert "history" in body
    assert body["history"]["dates"]
    assert body["history"]["series"]["quant"]


async def test_health(client, db, redis):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] is True
    assert body["redis"] is True


async def test_children_list_and_patch_and_delete(client, db, redis, seeded):
    parent = await register_parent(client, email="parent8@test.dev")
    child = await create_child(client, parent["token"], username="mgmt_child")
    headers = {"Authorization": f"Bearer {parent['token']}"}

    lst = await client.get("/api/v1/auth/children", headers=headers)
    assert lst.status_code == 200
    assert len(lst.json()["children"]) == 1
    assert lst.json()["children"][0]["is_verified"] is False

    child_id = child["child"]["id"]
    patched = await client.patch(
        f"/api/v1/auth/children/{child_id}",
        headers=headers,
        json={"full_name": "Новое имя", "language": "kk"},
    )
    assert patched.status_code == 200
    assert patched.json()["full_name"] == "Новое имя"
    assert patched.json()["language"] == "kk"

    deleted = await client.delete(f"/api/v1/auth/children/{child_id}", headers=headers)
    assert deleted.status_code == 200

    lst2 = await client.get("/api/v1/auth/children", headers=headers)
    assert len(lst2.json()["children"]) == 0

    child_user = await db.scalar(select(User).where(User.role == "CHILD"))
    assert child_user is None


async def test_child_login_username_case_insensitive(client, db, redis, seeded):
    """Telegram usernames are case-insensitive: 'CaseKid' == 'casekid'."""
    parent = await register_parent(client, email="parent10@test.dev")
    child = await create_child(client, parent["token"], username="CaseKid")
    child_id = child["child"]["id"]
    child_row = await db.get(ChildAccount, child_id)
    child_row.is_verified = True
    await db.commit()

    otp = await auth_service.issue_otp(redis, child_id)
    ok = await child_login(client, "casekid", "child12345", otp, redis)
    assert ok.status_code == 200, ok.text
    assert "access_token" in ok.json()


async def test_rate_limit_login_otp_429(client, db, redis, seeded):
    """10 попыток входа с неверным OTP → 11-я получает 429."""
    parent = await register_parent(client, email="parent11@test.dev")
    child = await create_child(client, parent["token"], username="rl_child")
    child_id = child["child"]["id"]
    child_row = await db.get(ChildAccount, child_id)
    child_row.is_verified = True
    await db.commit()

    for i in range(10):
        resp = await child_login(client, "rl_child", "child12345", "000000", redis)
        assert resp.status_code == 401, f"attempt {i}: {resp.status_code}"

    resp = await child_login(client, "rl_child", "child12345", "000000", redis)
    assert resp.status_code == 429, resp.text


async def test_revision_submit_works(client, db, redis, seeded):
    """Повтор из журнала ошибок (session_id='revision') не должен падать с 404."""
    parent = await register_parent(client, email="parent12@test.dev")
    child = await create_child(client, parent["token"], username="rev_child")
    child_id = child["child"]["id"]
    child_row = await db.get(ChildAccount, child_id)
    child_row.is_verified = True
    await db.commit()
    token = await verify_child_and_login(client, child_id, "rev_child", "child12345", redis)

    start = await client.post(
        "/api/v1/session/start",
        headers={"Authorization": f"Bearer {token}"},
        json={"mode": "sprint"},
    )
    q = start.json()

    # 1) неверный ответ в сессии
    bad = await client.post(
        "/api/v1/session/submit",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "session_id": q["session_id"],
            "template_id": q["template_id"],
            "params": q["params"],
            "answer": -999,
            "time_taken_sec": 10.0,
        },
    )
    assert bad.status_code == 200 and bad.json()["is_correct"] is False

    # 2) повтор через error-log: session_id='revision'
    template = await db.get(QuestionTemplate, q["template_id"])
    correct = safe_eval(template.answer_expr, q["params"])
    rev = await client.post(
        "/api/v1/session/submit",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "session_id": "revision",
            "template_id": q["template_id"],
            "params": q["params"],
            "answer": correct,
            "time_taken_sec": 5.0,
        },
    )
    assert rev.status_code == 200, rev.text
    assert rev.json()["is_correct"] is True
    assert rev.json()["session_finished"] is True


async def test_error_log_upsert_no_duplicates(client, db, redis, seeded):
    """Несколько неверных ответов на один шаблон → одна запись в журнале."""
    parent = await register_parent(client, email="parent13@test.dev")
    child = await create_child(client, parent["token"], username="ups_child")
    child_id = child["child"]["id"]
    child_row = await db.get(ChildAccount, child_id)
    child_row.is_verified = True
    await db.commit()
    token = await verify_child_and_login(client, child_id, "ups_child", "child12345", redis)

    template_id = None
    for _ in range(3):
        start = await client.post(
            "/api/v1/session/start",
            headers={"Authorization": f"Bearer {token}"},
            json={"mode": "sprint"},
        )
        q = start.json()
        template_id = q["template_id"]
        resp = await client.post(
            "/api/v1/session/submit",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "session_id": q["session_id"],
                "template_id": q["template_id"],
                "params": q["params"],
                "answer": -999,
                "time_taken_sec": 10.0,
            },
        )
        assert resp.json()["is_correct"] is False

    items = (
        await db.scalars(select(ErrorLogItem).where(ErrorLogItem.child_id == child_id))
    ).all()
    assert len(items) == 1, f"expected 1 item, got {len(items)}"
    assert items[0].wrong_count == 3


async def test_content_templates_list_and_get(client, db, redis, seeded):
    """GET /content/templates и /content/templates/{id} не должны падать (lazy-load)."""
    parent = await register_parent(client, email="parent14@test.dev")
    resp = await client.get(
        "/api/v1/content/templates",
        headers={"Authorization": f"Bearer {parent['token']}"},
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert len(items) >= 5

    one = await client.get(
        f"/api/v1/content/templates/{items[0]['id']}",
        headers={"Authorization": f"Bearer {parent['token']}"},
    )
    assert one.status_code == 200, one.text
    assert one.json()["subject_code"]


async def test_session_state_restore(client, db, redis, seeded):
    parent = await register_parent(client, email="parent9@test.dev")
    child = await create_child(client, parent["token"], username="state_child")
    child_id = child["child"]["id"]
    child_row = await db.get(ChildAccount, child_id)
    child_row.is_verified = True
    await db.commit()
    token = await verify_child_and_login(client, child_id, "state_child", "child12345", redis)

    start = await client.post(
        "/api/v1/session/start",
        headers={"Authorization": f"Bearer {token}"},
        json={"mode": "cat"},
    )
    q = start.json()

    state = await client.get(
        f"/api/v1/session/state/{q['session_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert state.status_code == 200
    body = state.json()
    assert body["asked"] == [q["template_id"]]
    assert body["mode"] == "cat"
    assert body["max_questions"] == 12
