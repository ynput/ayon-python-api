"""Tests for detection of lost websocket connection of 'EventHub'."""

from __future__ import annotations

import json
import threading

import pytest
from websocket import ABNF, WebSocketTimeoutException

from ayon_api import events as events_module
from ayon_api.events import EventHub

HEARTBEAT = (ABNF.OPCODE_TEXT, json.dumps({"topic": "heartbeat"}))
PONG = (ABNF.OPCODE_PONG, b"")
SERVER_PING = (ABNF.OPCODE_PING, b"")
TIMEOUT = "timeout"


class FakeClock:
    def __init__(self) -> None:
        self.value = 1000.0

    def monotonic(self) -> float:
        return self.value


class FakeWebSocket:
    """Replays scripted results of 'recv_data'.

    Timeout moves the clock forward by the socket timeout as a real
        socket would. When the script is exhausted the test is stopped.

    """
    def __init__(self, clock, responses, stop_event) -> None:
        self._clock = clock
        self._responses = list(responses)
        self._stop_event = stop_event
        self.pings = 0

    def send(self, data) -> None:
        pass

    def ping(self) -> None:
        self.pings += 1

    def abort(self) -> None:
        pass

    def recv_data(self, control_frame: bool = False):
        if not self._responses:
            self._stop_event.set()
            raise ConnectionError("End of test")
        response = self._responses.pop(0)
        if response == TIMEOUT:
            self._clock.value += events_module._PING_INTERVAL
            raise WebSocketTimeoutException("timed out")
        return response


class FakeConnection:
    access_token = "token"


class EventsRecorder:
    """Callback storing received topics, callbacks are stored weakly."""

    def __init__(self) -> None:
        self.topics: list[str] = []

    def on_event(self, event) -> None:
        self.topics.append(event.topic)


@pytest.fixture
def run_hub(monkeypatch):
    """Run event hub loop with scripted websocket responses."""
    clock = FakeClock()
    monkeypatch.setattr(events_module, "time", clock)
    monkeypatch.setattr(events_module, "_RECONNECT_DELAYS", (0.0,))

    def _run_hub(responses):
        stop_event = threading.Event()
        fake_ws = FakeWebSocket(clock, responses, stop_event)
        connections = [fake_ws]

        def create_ws_connection():
            if connections:
                return connections.pop(0)
            stop_event.set()
            raise ConnectionError("End of test")

        hub = EventHub(FakeConnection())
        monkeypatch.setattr(
            hub, "_create_ws_connection", create_ws_connection
        )
        monkeypatch.setattr(hub, "_check_token", lambda: True)
        recorder = EventsRecorder()
        hub.add_callback("connection.*", recorder.on_event, connect=False)
        hub._loop(stop_event)
        return recorder.topics, fake_ws

    return _run_hub


def test_busy_server_without_heartbeat_is_connected(run_hub):
    """Server answering pings is alive even if it does not send heartbeat.

    Server does not send heartbeat while it publishes other messages,
        which might take much longer than '_RECV_TIMEOUT'.

    """
    responses = [HEARTBEAT] + [TIMEOUT, PONG] * 10
    topics, fake_ws = run_hub(responses)

    assert topics == ["connection.opened"]
    assert fake_ws.pings == 10


def test_server_ping_keeps_connection_alive(run_hub):
    responses = [HEARTBEAT] + [TIMEOUT, TIMEOUT, SERVER_PING] * 5
    topics, fake_ws = run_hub(responses)

    assert topics == ["connection.opened"]


def test_no_response_to_ping_is_connection_lost(run_hub):
    responses = [HEARTBEAT, TIMEOUT, TIMEOUT, TIMEOUT]
    topics, fake_ws = run_hub(responses)

    assert topics == ["connection.opened", "connection.closed"]
    assert fake_ws.pings == 2


def test_pong_does_not_report_connected(run_hub):
    """Pong does not tell if client is authorized."""
    responses = [PONG, PONG]
    topics, fake_ws = run_hub(responses)

    assert "connection.opened" not in topics
