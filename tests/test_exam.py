# -*- coding: utf-8 -*-
"""考核模式接口测试。

运行方式：
    pip install -r requirements-dev.txt
    pytest tests/ -v
"""
import pytest

from app import app


@pytest.fixture
def client():
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c
        # 每个用例结束后退出考核，避免全局状态影响后续测试
        c.post("/api/exam/exit")


def _correct_key(io):
    if io["X0"] == 0:
        return "sensor"
    if io["X1"] == 0:
        return "emergency"
    if io["M100"] == 0:
        return "overload"
    return "communication"


def test_enter_exam_resets_score(client):
    client.post("/api/exam/enter")
    data = client.get("/api/status").get_json()
    assert data["exam"]["active"] is True
    assert data["exam"]["score"] == 0
    assert data["exam"]["total"] == 0


def test_start_hides_answer(client):
    """出题后报警码与诊断结论不能出现在接口返回里。"""
    client.post("/api/exam/enter")
    data = client.post("/api/exam/start").get_json()
    assert data["exam"]["pending"] is True
    assert data["diagnosis"] is None
    assert data["fault"] == "考核中"
    assert "***" in data["alarm"]


def test_start_hides_sensor_status(client, monkeypatch):
    """传感器断线时设备总览不能直接显示「断线」，否则等于泄题。"""
    monkeypatch.setattr("app.random.choice", lambda seq: "sensor")
    client.post("/api/exam/enter")
    data = client.post("/api/exam/start").get_json()
    assert data["io"]["X0"] == 0
    assert data["sensor"] == "异常"


def test_answer_correct_scores(client):
    client.post("/api/exam/enter")
    data = client.post("/api/exam/start").get_json()
    key = _correct_key(data["io"])

    result = client.post("/api/exam/answer", json={"key": key}).get_json()
    assert result["exam"]["result"]["correct"] is True
    assert result["exam"]["result"]["answer_key"] == key
    assert result["exam"]["score"] == 1
    assert result["exam"]["total"] == 1


def test_answer_wrong_records_zero(client):
    client.post("/api/exam/enter")
    data = client.post("/api/exam/start").get_json()
    wrong = "overload" if data["io"]["X0"] == 0 else "sensor"

    result = client.post("/api/exam/answer", json={"key": wrong}).get_json()
    assert result["exam"]["result"]["correct"] is False
    assert result["exam"]["result"]["answer_key"] != wrong
    assert result["exam"]["score"] == 0
    assert result["exam"]["total"] == 1


def test_duplicate_answer_rejected(client):
    client.post("/api/exam/enter")
    client.post("/api/exam/start")
    client.post("/api/exam/answer", json={"key": "sensor"})
    assert client.post("/api/exam/answer", json={"key": "sensor"}).status_code == 400


def test_manual_injection_blocked_during_exam(client):
    client.post("/api/exam/enter")
    client.post("/api/exam/start")
    assert client.post("/api/fault/sensor").status_code == 400


def test_invalid_key_rejected(client):
    client.post("/api/exam/enter")
    client.post("/api/exam/start")
    assert client.post("/api/exam/answer", json={"key": "not_exist"}).status_code == 400


def test_exit_exam_restores_running(client):
    client.post("/api/exam/enter")
    client.post("/api/exam/start")
    data = client.post("/api/exam/exit").get_json()
    assert data["exam"]["active"] is False
    assert data["line_status"] == "运行中"
    assert data["alarm"] == "无"
