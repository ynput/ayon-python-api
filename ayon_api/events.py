from __future__ import annotations

import atexit
from dataclasses import dataclass, field
import inspect
import json
import logging
import os
import re
import threading
import typing
from typing import Any, Callable
import weakref

import requests
from websocket import ABNF

from .exceptions import UnauthorizedError

if typing.TYPE_CHECKING:
    from websocket import WebSocket

    from .server_api import ServerAPI


@dataclass
class Event:
    topic: str
    data: dict[str, Any] = field(default_factory=dict)
    id: str | None = None
    sender: str | None = None
    event_hash: str | None = None
    project_name: str | None = None
    dependencies: list[str] | None = None
    description: str | None = None
    summary: str | None = None
    payload: dict[str, Any] | None = None
    status: str | None = None
    store: bool | None = None

    def __getitem__(self, key) -> Any:
        return self.data[key]

    def get(self, key, default=None) -> Any:
        return self.data.get(key, default)

    @classmethod
    def from_ws_message(cls, data: dict[str, Any]) -> Event | None:
        topic = data.get("topic")
        if topic is None:
            return None

        return cls(
            topic=topic,
            data=data,
            id=data.get("id"),
            sender=data.get("sender"),
            event_hash=data.get("eventHash"),
            project_name=data.get("project"),
            dependencies=data.get("dependsOn"),
            description=data.get("description"),
            summary=data.get("summary"),
            payload=data.get("payload"),
            status=data.get("status"),
            store=data.get("store"),
        )


def is_func_signature_supported(func, *args, **kwargs):
    """Check if a function signature supports passed args and kwargs.

    This check does not actually call the function, just look if function can
    be called with the arguments.

    Notes:
        This does NOT check if the function would work with passed arguments
            only if they can be passed in. If function have *args, **kwargs
            in parameters, this will always return 'True'.

    Example:
        >>> def my_function(my_number):
        ...     return my_number + 1
        ...
        >>> is_func_signature_supported(my_function, 1)
        True
        >>> is_func_signature_supported(my_function, 1, 2)
        False
        >>> is_func_signature_supported(my_function, my_number=1)
        True
        >>> is_func_signature_supported(my_function, number=1)
        False
        >>> is_func_signature_supported(my_function, "string")
        True
        >>> def my_other_function(*args, **kwargs):
        ...     my_function(*args, **kwargs)
        ...
        >>> is_func_signature_supported(
        ...     my_other_function,
        ...     "string",
        ...     1,
        ...     other=None
        ... )
        True

    Args:
        func (Callable): A function where the signature should be tested.
        *args (Any): Positional arguments for function signature.
        **kwargs (Any): Keyword arguments for function signature.

    Returns:
        bool: Function can pass in arguments.

    """
    sig = inspect.signature(func)
    try:
        sig.bind(*args, **kwargs)
        return True
    except TypeError:
        pass
    return False


def _get_func_ref(func: Callable) -> weakref.ref:
    if inspect.ismethod(func):
        return weakref.WeakMethod(func)
    return weakref.ref(func)


def _get_func_info(func: Callable) -> tuple[str, str]:
    path = "<unknown path>"
    if func is None:
        return "<unknown>", path

    if hasattr(func, "__name__"):
        name = func.__name__
    else:
        name = str(func)

    # Get path to file and fallback to '<unknown path>' if fails
    # NOTE This was added because of 'partial' functions which is handled,
    #   but who knows what else can cause this to fail?
    try:
        path = os.path.abspath(inspect.getfile(func))
    except TypeError:
        pass

    return name, path


class weakref_partial:
    """Partial function with weak reference to the wrapped function.

    Can be used as 'functools.partial' but it will store weak reference to
        function. That means that the function must be reference counted
        to avoid garbage collecting the function itself.

        When the referenced functions is garbage collected then calling the
        weakref partial (no matter the args/kwargs passed) will do nothing.
        It will fail silently, returning `None`. The `is_valid()` method can
        be used to detect whether the reference is still valid.

    Is useful for object methods. In that case the callback is
        deregistered when object is destroyed.

    Warnings:
        Values passed as *args and **kwargs are stored strongly in memory.
            That may "keep alive" objects that should be already destroyed.
            It is recommended to pass only immutable objects like 'str',
            'bool', 'int' etc.

    Args:
        func (Callable): Function to wrap.
        *args: Arguments passed to the wrapped function.
        **kwargs: Keyword arguments passed to the wrapped function.
    """

    def __init__(self, func: Callable, *args, **kwargs) -> None:
        self._func_ref: weakref.ref = _get_func_ref(func)
        self._args: tuple = args
        self._kwargs: dict = kwargs

    def __call__(self, *args, **kwargs) -> Any:
        func = self._func_ref()
        if func is None:
            return None

        new_args = tuple(list(self._args) + list(args))
        new_kwargs = dict(self._kwargs)
        new_kwargs.update(kwargs)
        return func(*new_args, **new_kwargs)

    def get_func(self) -> Callable | None:
        """Get wrapped function.

        Returns:
            Callable | None: Wrapped function or None if it was destroyed.

        """
        return self._func_ref()

    def is_valid(self) -> bool:
        """Check if wrapped function is still valid.

        Returns:
            bool: Is wrapped function still valid.

        """
        return self._func_ref() is not None

    def validate_signature(self, *args, **kwargs) -> bool:
        """Validate if passed arguments are supported by wrapped function.

        Returns:
            bool: Are passed arguments supported by wrapped function.

        """
        func = self._func_ref()
        if func is None:
            return False

        new_args = tuple(list(self._args) + list(args))
        new_kwargs = dict(self._kwargs)
        new_kwargs.update(kwargs)
        return is_func_signature_supported(
            func, *new_args, **new_kwargs
        )


class EventCallback:
    """Callback registered to a topic.

    The callback function is registered to a topic. Topic is a string which
    may contain '*' that will be handled as "any characters".

    # Examples:
    - "entity.folder.attr_changed" - Callback will be triggered if the event
        topic is exactly "entity.folder.attr_changed".
    - "entity.*" - Callback will be triggered an event topic starts with
        "entity." so "entity.folder.created" and "entity.version.created"
        will trigger the callback.
    - "*" Callback will listen to all events.

    Callback can be function or method. In both cases it should expect one
    or none arguments. When 1 argument is expected then the processed 'Event'
    object is passed in.

    The callbacks are validated against their reference counter, that is
        achieved using 'weakref' module. That means that the callback must
        be stored in memory somewhere. e.g. lambda functions are not
        supported as valid callback.

    You can use 'weakref_partial' functions. In that case is partial object
        stored in the callback object and reference counter is checked for
        the wrapped function.

    Args:
        topic (str): Topic which will be listened.
        func (Callable): Callback to a topic.
        order (int | None): Order of callback. Lower number means higher
            priority.

    Raises:
        TypeError: When passed function is not a callable object.
    """
    default_order: int = 100

    def __init__(
        self, topic: str, func: Callable, order: int | None = None
    ) -> None:
        if not callable(func):
            raise TypeError(
                f"Registered callback is not callable. \"{func}\""
            )

        if order is None:
            order = self.default_order
        self._validate_order(order)

        self._log = None
        self._topic: str = topic
        self._order: int = order
        self._enabled: bool = True
        # Replace '*' with any character regex and escape rest of text
        #   - when callback is registered for '*' topic it will receive all
        #       events
        #   - it is possible to register to a partial topis 'my.event.*'
        #       - it will receive all matching event topics
        #           e.g. 'my.event.start' and 'my.event.end'
        topic_regex_str = "^{}$".format(
            ".+".join(
                re.escape(part)
                for part in topic.split("*")
            )
        )
        topic_regex = re.compile(topic_regex_str)
        self._topic_regex: re.Pattern = topic_regex

        # Callback function prep
        if isinstance(func, weakref_partial):
            partial_func = func
            (name, path) = _get_func_info(func.get_func())
            func_ref = None
            expect_args = partial_func.validate_signature("fake")
            expect_kwargs = partial_func.validate_signature(event="fake")

        else:
            partial_func = None
            (name, path) = _get_func_info(func)
            # Convert callback into references
            #   - deleted functions won't cause crashes
            func_ref = _get_func_ref(func)

            # Get expected arguments from function spec
            # - positional arguments are always preferred
            expect_args = is_func_signature_supported(func, "fake")
            expect_kwargs = is_func_signature_supported(func, event="fake")

        self._func_ref: weakref.ref | None = func_ref
        self._partial_func: weakref_partial | None = partial_func
        self._ref_is_valid: bool = True
        self._expect_args: bool = expect_args
        self._expect_kwargs: bool = expect_kwargs

        self._name: str = name
        self._path: str = path

    def __repr__(self) -> str:
        return f"< {self.__class__.__name__} - {self._name} > {self._path}"

    @property
    def log(self) -> logging.Logger:
        if self._log is None:
            self._log = logging.getLogger(self.__class__.__name__)
        return self._log

    @property
    def topic(self) -> str:
        return self._topic

    @property
    def is_ref_valid(self) -> bool:
        """

        Returns:
            bool: Is reference to callback valid.

        """
        self._validate_ref()
        return self._ref_is_valid

    def validate_ref(self) -> None:
        """Validate if reference to callback is valid.

        Deprecated:
            Reference is always live checkd with 'is_ref_valid'.

        """
        # Trigger validate by getting 'is_valid'
        _ = self.is_ref_valid

    @property
    def enabled(self) -> bool:
        """Is callback enabled.

        Returns:
            bool: Is callback enabled.

        """
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        """Change if callback is enabled.

        Args:
            enabled (bool): Change enabled state of the callback.

        """
        self._enabled = enabled

    def deregister(self) -> None:
        """Calling this function will cause that callback will be removed."""
        self._ref_is_valid = False
        self._partial_func = None
        self._func_ref = None

    def get_order(self) -> int:
        """Get callback order.

        Returns:
            int: Callback order.

        """
        return self._order

    def set_order(self, order: int) -> None:
        """Change callback order.

        Args:
            order (int): Order of callback. Lower number means
                higher priority.

        """
        self._validate_order(order)
        self._order = order

    order = property(get_order, set_order)

    def topic_matches(self, topic: str) -> bool:
        """Check if event topic matches callback's topic.

        Args:
            topic (str): Topic name.

        Returns:
            bool: Topic matches callback's topic.

        """
        return self._topic_regex.match(topic)

    def process_event(self, event: Event) -> None:
        """Process event.

        Args:
            event(Event): Event that was triggered.

        """
        # Skip if callback is not enabled
        if not self._enabled:
            return

        # Get reference and skip if is not available
        callback = self._get_callback()
        if callback is None:
            return

        if not self.topic_matches(event.topic):
            return

        # Try to execute callback
        try:
            if self._expect_args:
                callback(event)

            elif self._expect_kwargs:
                callback(event=event)

            else:
                callback()

        except Exception:
            self.log.warning(
                f"Failed to execute event callback {repr(self)}",
                exc_info=True
            )

    def _validate_order(self, order: int) -> None:
        if isinstance(order, int):
            return

        raise TypeError(f"Expected type 'int' got '{type(order)}'.")

    def _get_callback(self) -> Callable | None:
        if self._partial_func is not None:
            return self._partial_func

        if self._func_ref is not None:
            return self._func_ref()
        return None

    def _validate_ref(self) -> None:
        if self._ref_is_valid is False:
            return

        if self._func_ref is not None:
            self._ref_is_valid = self._func_ref() is not None

        elif self._partial_func is not None:
            self._ref_is_valid = self._partial_func.is_valid()

        else:
            self._ref_is_valid = False

        if not self._ref_is_valid:
            self._func_ref = None
            self._partial_func = None


# Server sends 'heartbeat' message to authorized clients when there was no
#   other message for ~5 seconds. If nothing arrives for this amount of time
#   the connection is considered dead.
_RECV_TIMEOUT: float = 15.0
# Timeout for opening websocket connection and for the auth check request.
_CONNECT_TIMEOUT: float = 5.0
# Delays between reconnection attempts (last value is used repeatedly).
_RECONNECT_DELAYS: tuple[float, ...] = (0.5, 1.0, 2.0, 5.0)
# Delay between reconnection attempts when the token is known to be invalid.
_AUTH_FAILED_DELAY: float = 30.0
# How long to wait for the loop thread on stop. The thread is daemon so
#   it can't block process exit even if it does not finish in time.
_STOP_TIMEOUT: float = 1.0


def _abort_ws(ws_con: WebSocket) -> None:
    """Close websocket without waiting for server response.

    'WebSocket.close' sends close frame and waits for the response
        (up to 3 seconds) which would block the caller.

    """
    for method_name in ("abort", "shutdown"):
        method = getattr(ws_con, method_name, None)
        if method is None:
            continue
        try:
            method()
            return
        except Exception:
            pass


@dataclass
class _LoopState:
    stop_event: threading.Event = field(default_factory=threading.Event)
    # Subscribe message has to be sent
    auth_required: bool = False
    # Some message was received with current websocket connection
    received_message: bool = False
    # Connection state reported via events
    #   - 'None' means unknown (nothing was reported yet)
    connected: bool | None = None
    auth_failed: bool = False
    failed_attempts: int = 0
    registered_topics: set[str] = field(default_factory=set)
    server_is_restarting: bool = False
    # Interrupts waiting between reconnection attempts
    wake_event: threading.Event = field(default_factory=threading.Event)


# Hubs stopped on process exit, stored weakly so a hub that is not running
#   can be garbage collected
_EVENT_HUBS: weakref.WeakSet[EventHub] = weakref.WeakSet()


def _stop_event_hubs() -> None:
    for event_hub in list(_EVENT_HUBS):
        event_hub.stop()


atexit.register(_stop_event_hubs)


class EventHub:
    """Receive AYON server events via websocket and trigger callbacks.

    Websocket connection is handled in a daemon thread, so it never blocks
        the caller (e.g. DCC main thread) nor the process exit.

    Warnings:
        Callbacks are triggered in the websocket thread! Use own queue
            to process them in main thread, especially if a callback
            touches Qt widgets.

    Internal topics:
        - 'connection.opened' first message received after (re)connection.
        - 'connection.closed' connection was lost or could not be created.
        - 'auth.failed' server rejected the token.

    Args:
        connection (ServerAPI): Server connection.

    """
    # Topics emitted by the hub itself
    TOPIC_CONNECTION_OPENED: str = "connection.opened"
    TOPIC_CONNECTION_CLOSED: str = "connection.closed"
    TOPIC_AUTH_FAILED: str = "auth.failed"
    # Topic sent by server
    TOPIC_SERVER_RESTART_REQUESTED: str = "server.restart_requested"

    def __init__(self, connection: ServerAPI) -> None:
        self._log = logging.getLogger(self.__class__.__name__)
        self._connection: ServerAPI = connection
        self._ws_connection: WebSocket | None = None
        self._loop_state: _LoopState = _LoopState()
        self._loop_thread: threading.Thread | None = None
        self._thread_lock = threading.Lock()
        self._callbacks_lock = threading.RLock()
        self._state_lock = threading.Lock()
        self._registered_callbacks: list[EventCallback] = []
        self._internal_callbacks: list[EventCallback] = [
            EventCallback(
                self.TOPIC_SERVER_RESTART_REQUESTED,
                self._on_server_restart,
            ),
        ]
        self.add_callbacks(self._internal_callbacks, connect=False)
        _EVENT_HUBS.add(self)

    def is_running(self) -> bool:
        """Check if event loop is running.

        Returns:
            bool: Is event loop running.

        """
        thread = self._loop_thread
        return thread is not None and thread.is_alive()

    def is_connected(self) -> bool:
        """Check if event loop is connected to server.

        Returns:
            bool: Is event loop connected to server.

        """
        return self._loop_state.connected is True

    def get_connection_state(self) -> bool | None:
        """Connection state as was reported by events.

        Returns:
            bool | None: 'True' if connected, 'False' if disconnected and
                'None' if state is not known yet.

        """
        return self._loop_state.connected

    def is_auth_failed(self) -> bool:
        return self._loop_state.auth_failed

    def is_server_restarting(self) -> bool:
        return self._loop_state.server_is_restarting

    def check_server_available(self) -> bool | None:
        """Quick synchronous check if server is available.

        Websocket connection is created in a background thread, so it takes
            a while until the connection state is known. This check can be
            used e.g. when a tool is opened to find out that the server is
            not available before the tool tries to fetch data from it.

        Request is sent only if the connection state is not known yet. When
            the server is not available, the state is changed to
            disconnected and 'connection.closed' event is emitted.

        Returns:
            bool | None: 'False' if server is not available, 'True' if
                websocket is connected, 'None' if server did respond but
                websocket connection is not established yet.

        """
        state = self._loop_state.connected
        if state is not None:
            return state

        # Use 'get_info' so timeout and retries configured on the
        #   connection are respected
        try:
            self._connection.get_info()
            available = True
        except UnauthorizedError:
            # Server is running but rejected the token
            available = True
        except Exception:
            available = False

        if available:
            return self._loop_state.connected

        self._set_connected(False)
        return False

    def add_callback(
        self,
        topic: str,
        callback: Callable | weakref_partial,
        order: int | None = None,
        *,
        connect: bool = True,
    ) -> EventCallback:
        """Register callback in event system.

        Args:
            topic (str): Topic for EventCallback.
            callback (Callable | weakref_partial): Function or method
                that will be called when topic is triggered.
            order (int | None): Order of callback. Lower number means
                higher priority.
            connect (bool): Create websocket connection if
                not already created.

        Returns:
            EventCallback: Created callback object which can be used to
                stop listening.

        """
        callback = EventCallback(topic, callback, order)
        self.add_callbacks(
            [callback], connect=connect
        )
        return callback

    def add_callbacks(
        self,
        callbacks: list[EventCallback],
        *,
        connect: bool = True,
    ) -> None:
        """Register callback in event system.

        Args:
            callbacks (list[EventCallback]): List of EventCallback
                objects to register.
            connect (bool): Create websocket connection if
                not already created.

        """
        with self._callbacks_lock:
            self._registered_callbacks.extend(callbacks)
            self._update_topics()
        if connect:
            self.start()

    def emit_event(self, event: Event) -> None:
        """Emit event object.

        Args:
            event (Event): Prepared event with topic and data.

        """
        self._process_event(event)

    def start(self) -> None:
        """Start event loop.

        Websocket connection is created in a daemon thread, this method
            does not block.

        """
        with self._thread_lock:
            if self.is_running():
                return

            stop_event = threading.Event()
            self._loop_state.stop_event = stop_event
            loop_thread = threading.Thread(
                target=self._thread_loop,
                args=(stop_event,),
                name="AYONEventHub",
                # Daemon thread must be used! Non-daemon threads are joined
                #   by the interpreter BEFORE 'atexit' callbacks are called,
                #   so the process would hang on exit.
                daemon=True,
            )
            self._loop_thread = loop_thread
            loop_thread.start()

    def stop(self) -> None:
        self._stop()

    def reconnect(self) -> None:
        """Drop current websocket connection and connect again.

        Should be called when websocket connection should be recreated,
            e.g. server url of the connection did change.

        """
        state = self._loop_state
        state.auth_failed = False
        state.failed_attempts = 0
        self._close_ws_connection()
        state.wake_event.set()

    def reauthenticate(self) -> None:
        """Authenticate websocket connection with current token.

        Should be called when token of the server connection did change.
            Websocket connection is kept if is open, otherwise next
            connection attempt happens immediately.

        """
        if not self._connection.access_token:
            # Token was removed, server would close the connection anyway
            self.reconnect()
            return

        state = self._loop_state
        state.auth_failed = False
        state.failed_attempts = 0
        state.auth_required = True
        state.wake_event.set()

    def _stop(self) -> None:
        with self._thread_lock:
            loop_thread, self._loop_thread = self._loop_thread, None
            self._loop_state.stop_event.set()
            self._loop_state.wake_event.set()
            ws_con = self._ws_connection

        # Unblock 'recv' in the loop thread
        if ws_con is not None:
            _abort_ws(ws_con)

        if (
            loop_thread is not None
            and loop_thread is not threading.current_thread()
        ):
            loop_thread.join(_STOP_TIMEOUT)

    def _update_topics(self) -> None:
        """Subscribe to topics in server based on registered callbacks.

        Server does not allow wildcards in the topic but does validate
            start of the topic so 'entity.folder.*' is not allowed
            but 'entity.folder.' does work.

        In case the wildcard is used at the start of the topic we have to
            subscribe to all topics.

        """
        topics = set()
        with self._callbacks_lock:
            callbacks = list(self._registered_callbacks)

        for callback in callbacks:
            topic = callback.topic
            if topic == "*":
                topics.add(topic)
                continue
            parts = topic.split("*", maxsplit=1)
            if len(parts) == 1:
                topics.add(topic)
                continue

            part = parts[0]
            if part:
                topics.add(part)
            else:
                topics.add("*")

        if topics == self._loop_state.registered_topics:
            return

        self._loop_state.registered_topics = topics
        self._loop_state.auth_required = True

    def _create_ws_connection(self) -> WebSocket:
        ws_con = self._connection.create_websocket("ws")
        # Server sends heartbeat periodically, so timeout on receive means
        #   that the connection is dead.
        ws_con.settimeout(_RECV_TIMEOUT)
        return ws_con

    def _close_ws_connection(self) -> None:
        with self._thread_lock:
            ws_con, self._ws_connection = self._ws_connection, None
        if ws_con is not None:
            _abort_ws(ws_con)

    def _check_token(self) -> bool | None:
        """Check if token is valid without affecting the server connection.

        Do NOT use 'ServerAPI.validate_token' here. It marks the token
            as invalid on any non-200 response (e.g. 502 while server is
            restarting) which would break all requests of the process.

        Returns:
            bool | None: 'True' if valid, 'False' if server rejected the
                token, 'None' if it is not possible to tell (server is
                not reachable).

        """
        token = self._connection.access_token
        if not token:
            return False

        ssl_verify = self._connection.get_ssl_verify()
        if ssl_verify is None:
            ssl_verify = True
        url = f"{self._connection.get_base_url()}/api/users/me"
        status_codes = set()
        for headers in (
            {"Authorization": f"Bearer {token}"},
            {"X-Api-Key": token},
        ):
            try:
                response = requests.get(
                    url,
                    headers=headers,
                    verify=ssl_verify,
                    cert=self._connection.get_cert(),
                    timeout=_CONNECT_TIMEOUT,
                )
            except Exception:
                return None
            if response.status_code == 200:
                return True
            status_codes.add(response.status_code)

        if status_codes <= {401, 403}:
            return False
        return None

    def _set_connected(self, connected: bool) -> None:
        # Can be called from websocket thread and from main thread
        #   ('check_server_available').
        state = self._loop_state
        with self._state_lock:
            if state.connected is connected:
                return
            state.connected = connected
            if connected:
                state.failed_attempts = 0
                state.server_is_restarting = False
                state.auth_failed = False
                state.wake_event.clear()

        if connected:
            self.emit_event(Event(self.TOPIC_CONNECTION_OPENED))
        else:
            self.emit_event(Event(self.TOPIC_CONNECTION_CLOSED))

    def _on_connection_lost(self, stop_event: threading.Event) -> None:
        state = self._loop_state
        received_message = state.received_message
        state.received_message = False
        self._close_ws_connection()
        if stop_event.is_set():
            return

        self._set_connected(False)

        # Server closes unauthorized clients after few seconds without
        #   sending anything, authorized clients receive heartbeat.
        if not received_message and not state.auth_failed:
            if self._check_token() is False:
                state.auth_failed = True
                self.emit_event(Event(self.TOPIC_AUTH_FAILED))

        if state.auth_failed:
            delay = _AUTH_FAILED_DELAY
        else:
            idx = min(state.failed_attempts, len(_RECONNECT_DELAYS) - 1)
            delay = _RECONNECT_DELAYS[idx]
        state.failed_attempts += 1
        self._wait(stop_event, delay)

    def _wait(self, stop_event: threading.Event, timeout: float) -> None:
        """Wait until timeout, stop or wake request."""
        if stop_event.is_set():
            return
        wake_event = self._loop_state.wake_event
        wake_event.wait(timeout)
        wake_event.clear()

    def _thread_loop(self, stop_event: threading.Event) -> None:
        try:
            self._loop(stop_event)
        except Exception:
            self._log.warning("AYON event hub loop crashed", exc_info=True)
        finally:
            self._close_ws_connection()
            self._loop_state.received_message = False

    def _loop(self, stop_event: threading.Event) -> None:
        state = self._loop_state
        while not stop_event.is_set():
            ws_con = self._ws_connection
            if ws_con is None:
                if not self._connection.access_token:
                    self._wait(stop_event, 1.0)
                    continue

                try:
                    ws_con = self._create_ws_connection()
                except Exception:
                    # Server is not available (connection refused, timeout,
                    #   502 from proxy during restart, ssl error...)
                    self._on_connection_lost(stop_event)
                    continue

                with self._thread_lock:
                    if stop_event.is_set():
                        _abort_ws(ws_con)
                        break
                    self._ws_connection = ws_con
                state.received_message = False
                state.auth_required = True

            if state.auth_required:
                state.auth_required = False
                subscribe_payload = {
                    "topic": "auth",
                    "token": self._connection.access_token,
                    "subscribe": list(state.registered_topics),
                }
                try:
                    ws_con.send(json.dumps(subscribe_payload))
                except Exception:
                    self._on_connection_lost(stop_event)
                continue

            try:
                op_code, message = ws_con.recv_data()
            except Exception:
                # Timeout (no heartbeat), closed connection, socket error...
                self._on_connection_lost(stop_event)
                continue

            if op_code == ABNF.OPCODE_CLOSE:
                self._on_connection_lost(stop_event)
                continue

            if not state.received_message:
                state.received_message = True
                self._set_connected(True)

            if op_code != ABNF.OPCODE_TEXT or not message:
                continue

            try:
                event_data = json.loads(message)
            except ValueError:
                self._log.debug(
                    "Failed to parse websocket message", exc_info=True
                )
                continue

            if not isinstance(event_data, dict):
                continue

            event = Event.from_ws_message(event_data)
            if event is not None:
                self.emit_event(event)

    def _on_server_restart(self) -> None:
        self._loop_state.server_is_restarting = True

    def _process_event(self, event: Event) -> None:
        """Process event topic and trigger callbacks.

        Args:
            event (Event): Prepared event with topic and data.

        """
        with self._callbacks_lock:
            callbacks = tuple(sorted(
                self._registered_callbacks, key=lambda x: x.order
            ))

        removed = []
        for callback in callbacks:
            callback.process_event(event)
            if not callback.is_ref_valid:
                removed.append(callback)

        if not removed:
            return

        with self._callbacks_lock:
            for callback in removed:
                try:
                    self._registered_callbacks.remove(callback)
                except ValueError:
                    pass
            self._update_topics()
