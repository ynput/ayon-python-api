"""Lifecycle of event hub. Does not require running AYON server.

Websocket connection is replaced with a fake socket which sends
heartbeat messages, the same way as AYON server does.
"""
import gc
import json
import threading
import time
import weakref

import pytest
from websocket import ABNF, WebSocketConnectionClosedException

from ayon_api.events import EventHub
from ayon_api.server_api import ServerAPI

WAIT_TIMEOUT = 5.0


def wait_for(predicate, timeout=WAIT_TIMEOUT):
    start = time.time()
    while time.time() - start < timeout:
        if predicate():
            return True
        time.sleep(0.01)
    return False


class FakeWebSocket:
    """Fake websocket connection.

    Sends heartbeat until aborted. If 'rejected_tokens' contains token
        sent in auth message, the connection is closed by "server" without
        sending any message.
    """

    def __init__(self, base_url, rejected_tokens):
        self.base_url = base_url
        self.sent = []
        self._rejected_tokens = rejected_tokens
        self._aborted = threading.Event()

    @property
    def tokens(self):
        return [message["token"] for message in self.sent]

    def settimeout(self, timeout):
        pass

    def send(self, data):
        message = json.loads(data)
        self.sent.append(message)
        if message["token"] in self._rejected_tokens:
            self._aborted.set()

    def recv_data(self):
        if self._aborted.wait(0.02):
            raise WebSocketConnectionClosedException("closed")
        if not self.sent:
            # Server does not send anything before auth message
            return self.recv_data()
        return ABNF.OPCODE_TEXT, json.dumps({"topic": "heartbeat"})

    def abort(self):
        self._aborted.set()


class Recorder:
    """Callback storing received topics, must be kept in memory."""

    def __init__(self):
        self.topics = []

    def __call__(self, event):
        self.topics.append(event.topic)

    def count(self, topic):
        return self.topics.count(topic)


class _Sockets(list):
    rejected_tokens = None


@pytest.fixture
def sockets(monkeypatch):
    created = _Sockets()
    rejected_tokens = set()

    def create_websocket(self, endpoint, **kwargs):
        ws_con = FakeWebSocket(self.get_base_url(), rejected_tokens)
        created.append(ws_con)
        return ws_con

    def check_token(self):
        return self._connection.access_token not in rejected_tokens

    monkeypatch.setattr(ServerAPI, "create_websocket", create_websocket)
    monkeypatch.setattr(ServerAPI, "validate_token", lambda self: True)
    monkeypatch.setattr(EventHub, "_check_token", check_token)
    created.rejected_tokens = rejected_tokens
    return created


@pytest.fixture
def con():
    return ServerAPI("http://server-a:0", "token-a", create_session=False)


@pytest.fixture
def hubs():
    created = []
    yield created
    for hub in created:
        hub.stop()


def _start_hub(hub, hubs):
    hubs.append(hub)
    recorder = Recorder()
    hub.add_callback("*", recorder)
    return recorder


def test_event_hub_is_created_on_demand(con):
    assert con._event_hub is None
    hub = con.get_event_hub()
    assert hub is con.get_event_hub()
    assert not hub.is_running()


def test_set_token_reauthenticates_open_connection(con, sockets, hubs):
    recorder = _start_hub(con.get_event_hub(), hubs)
    assert wait_for(lambda: recorder.count(EventHub.TOPIC_CONNECTION_OPENED))
    assert sockets[0].tokens == ["token-a"]

    con.set_token("token-b")

    assert wait_for(lambda: sockets[0].tokens[-1] == "token-b")
    # Same websocket connection is used
    assert len(sockets) == 1
    assert recorder.count(EventHub.TOPIC_CONNECTION_CLOSED) == 0


def test_token_change_wakes_hub_after_auth_failure(con, sockets, hubs):
    sockets.rejected_tokens.add("token-a")
    hub = con.get_event_hub()
    recorder = _start_hub(hub, hubs)
    assert wait_for(lambda: recorder.count(EventHub.TOPIC_AUTH_FAILED))
    assert hub.is_auth_failed()

    # Without wake up the hub would wait 30 seconds before next attempt
    con.set_token("token-b")

    assert wait_for(
        lambda: recorder.count(EventHub.TOPIC_CONNECTION_OPENED), timeout=2.0
    )
    assert not hub.is_auth_failed()
    assert sockets[-1].tokens == ["token-b"]


def test_stopped_hub_is_garbage_collected(sockets):
    con = ServerAPI("http://server-a:0", "token-a", create_session=False)
    hub = con.get_event_hub()
    recorder = Recorder()
    hub.add_callback("*", recorder)
    assert wait_for(lambda: recorder.count(EventHub.TOPIC_CONNECTION_OPENED))
    hub.stop()

    con_ref = weakref.ref(con)
    hub_ref = weakref.ref(hub)
    del con, hub
    gc.collect()
    assert hub_ref() is None
    assert con_ref() is None
