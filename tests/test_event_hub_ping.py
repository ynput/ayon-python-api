"""Tests for detection of lost websocket connection of 'EventHub'."""

from __future__ import annotations

import json
import threading

import pytest
from websocket import ABNF, WebSocketTimeoutException

from ayon_api import events as events_module
from ayon_api.events import EventHub

HEARTBEAT = (ABNF.OPCODE_TEXT, json.dumps({"topic": "heartbeat"}))
RESTART = (
    ABNF.OPCODE_TEXT,
    json.dumps({"topic": "server.restart_requested"}),
)
CLOSE = (ABNF.OPCODE_CLOSE, b"")
PONG = (ABNF.OPCODE_PONG, b"")
SERVER_PING = (ABNF.OPCODE_PING, b"")
TIMEOUT = "timeout"


class FakeWebSocket:
    """Replays scripted results of 'recv_data'.

    When the script is exhausted the connection is closed, or the test is
        stopped if this is the last connection.

    """
    def __init__(self, responses, stop_event, is_last) -> None:
        self._responses = list(responses)
        self._stop_event = stop_event
        self._is_last = is_last
        self.pings = 0

    def send(self, data) -> None:
        pass

    def ping(self) -> None:
        self.pings += 1

    def abort(self) -> None:
        pass

    def recv_data(self, control_frame: bool = False):
        if not self._responses:
            if self._is_last:
                self._stop_event.set()
            raise ConnectionError("End of script")
        response = self._responses.pop(0)
        if response == TIMEOUT:
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
    """Run event hub loop with scripted websocket responses.

    Each item of 'scripts' is a list of responses of one connection,
        'None' means that the connection attempt fails.

    """
    monkeypatch.setattr(events_module, "_RECONNECT_DELAYS", (0.0,))

    def _run_hub(*scripts):
        stop_event = threading.Event()
        connections = [
            None if responses is None else FakeWebSocket(
                responses, stop_event, idx == len(scripts) - 1
            )
            for idx, responses in enumerate(scripts)
        ]
        remaining = list(connections)

        def create_ws_connection():
            if not remaining:
                stop_event.set()
                raise ConnectionError("End of test")
            ws_con = remaining.pop(0)
            if ws_con is None:
                raise ConnectionError("Connection refused")
            return ws_con

        hub = EventHub(FakeConnection())
        monkeypatch.setattr(
            hub, "_create_ws_connection", create_ws_connection
        )
        monkeypatch.setattr(hub, "_check_token", lambda: True)
        recorder = EventsRecorder()
        hub.add_callback("connection.*", recorder.on_event, connect=False)
        hub._loop(stop_event)
        return recorder.topics, connections

    return _run_hub


def test_busy_server_without_heartbeat_is_connected(run_hub):
    """Server answering pings is alive even if it does not send heartbeat.

    Server does not send heartbeat while it publishes other messages,
        which might take much longer than '_RECV_TIMEOUT'.

    """
    responses = [HEARTBEAT] + [TIMEOUT, PONG] * 10
    topics, (fake_ws,) = run_hub(responses)

    assert topics == ["connection.opened"]
    assert fake_ws.pings == 10


def test_server_ping_keeps_connection_alive(run_hub):
    responses = [HEARTBEAT] + [TIMEOUT, TIMEOUT, SERVER_PING] * 5
    topics, _ = run_hub(responses)

    assert topics == ["connection.opened"]


def test_no_response_to_ping_interrupts_connection(run_hub):
    """Working connection that stopped responding is reconnected silently."""
    responses = [HEARTBEAT, TIMEOUT, TIMEOUT, TIMEOUT]
    topics, (fake_ws,) = run_hub(responses)

    assert topics == ["connection.opened", "connection.interrupted"]
    assert fake_ws.pings == 2


class StalledClock:
    """Clock jumping forward on each read, as if the GIL was held."""

    def __init__(self, stall: float) -> None:
        self._stall = stall
        self._value = 1000.0

    def monotonic(self) -> float:
        self._value += self._stall
        return self._value


def test_timeouts_are_counted_not_measured(run_hub, monkeypatch):
    """Time spent outside of socket wait does not count as silence.

    Host might hold the GIL for minutes, messages waiting in the socket
        are received once the thread runs again.

    """
    # Wall-clock based detection would report the connection as lost
    #   on first timeout. Module does not import 'time' anymore.
    monkeypatch.setattr(
        events_module, "time", StalledClock(300.0), raising=False
    )
    responses = [HEARTBEAT] + [TIMEOUT, TIMEOUT, HEARTBEAT] * 5
    topics, (fake_ws,) = run_hub(responses)

    assert topics == ["connection.opened"]


def test_interrupted_connection_reports_opened_on_reconnect(run_hub):
    topics, _ = run_hub([HEARTBEAT, CLOSE], [HEARTBEAT])

    assert topics == [
        "connection.opened",
        "connection.interrupted",
        "connection.opened",
    ]


def test_failed_reconnect_reports_closed(run_hub):
    """Connection is reported as lost when reconnection fails."""
    topics, _ = run_hub([HEARTBEAT, CLOSE], None)

    assert topics == [
        "connection.opened",
        "connection.interrupted",
        "connection.closed",
    ]


def test_server_restart_reports_closed(run_hub):
    """Server restart is reported right away, not as interruption."""
    topics, _ = run_hub([HEARTBEAT, RESTART, CLOSE], [HEARTBEAT])

    assert topics == [
        "connection.opened",
        "connection.closed",
        "connection.opened",
    ]


def test_pong_does_not_report_connected(run_hub):
    """Pong does not tell if client is authorized."""
    responses = [PONG, PONG]
    topics, _ = run_hub(responses)

    assert "connection.opened" not in topics
