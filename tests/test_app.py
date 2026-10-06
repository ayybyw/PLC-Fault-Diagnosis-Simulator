# -*- coding: utf-8 -*-
"""接口与模板渲染的回归测试。

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


def test_index_page_renders(client):
    """首页模板必须能正常渲染。

    回归点：仓库曾缺失 templates/index.html，导致首页直接抛 TemplateNotFound。
    """
    res = client.get("/")
    assert res.status_code == 200
    assert "PLC 故障诊断模拟平台" in res.get_data(as_text=True)


@pytest.mark.parametrize("path", ["/static/style.css", "/static/script.js"])
def test_static_assets_available(client, path):
    assert client.get(path).status_code == 200


def test_status_baseline(client):
    data = client.get("/api/status").get_json()
    assert data["io"] == {"X0": 1, "X1": 1, "Y0": 1, "M100": 1}
    assert data["fault"] is None
    assert data["diagnosis"] is None
    assert data["line_status"] == "运行中"


FAULT_CASES = [
    ("sensor", "X0", "E101"),
    ("overload", "M100", "E202"),
    ("emergency", "X1", "E001"),
    ("communication", "Y0", "E301"),
]


@pytest.mark.parametrize("key,point,alarm_code", FAULT_CASES)
def test_fault_injection_updates_io_and_diagnosis(client, key, point, alarm_code):
    """四类故障各自的关键信号位必须熄灭，并输出报警码与排查步骤。"""
    data = client.post(f"/api/fault/{key}").get_json()
    assert data["io"][point] == 0
    assert alarm_code in data["alarm"]
    assert data["line_status"] == "故障停机"
    assert data["diagnosis"]["causes"]
    assert data["diagnosis"]["steps"]


def test_unknown_fault_returns_404(client):
    assert client.post("/api/fault/not_exist").status_code == 404


def test_reset_restores_baseline(client):
    client.post("/api/fault/sensor")
    data = client.post("/api/reset").get_json()
    assert data["io"] == {"X0": 1, "X1": 1, "Y0": 1, "M100": 1}
    assert data["fault"] is None
    assert data["alarm"] == "无"


def test_fault_switch_does_not_leak_previous_state(client):
    """切换故障时应先回到基线，避免上一次的故障字段残留。"""
    client.post("/api/fault/overload")
    data = client.post("/api/fault/emergency").get_json()
    assert data["fault"] == "急停触发"
    assert data["io"] == {"X0": 1, "X1": 0, "Y0": 0, "M100": 1}
