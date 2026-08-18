from __future__ import annotations

from dataclasses import dataclass
import inspect
import logging
import os
import re
from typing import Any, Callable
import weakref


@dataclass
class Event:
    topic: str


@dataclass
class ServerEvent(Event):
    sender: str | None
    event_hash: str | None
    project_name: str | None
    username: str | None
    dependencies: list[str] | None
    description: str | None
    summary: str | None
    payload: dict[str, Any] | None
    finished: bool = True
    store: bool = True


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
    - "workfile.save"   Callback will be triggered if the event topic is
                        exactly "workfile.save" .
    - "workfile.*"      Callback will be triggered an event topic starts with
                        "workfile." so "workfile.save" and "workfile.open"
                        will trigger the callback.
    - "*"               Callback will listen to all events.

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
        order (Union[int, None]): Order of callback. Lower number means higher
            priority.

    Raises:
        TypeError: When passed function is not a callable object.
    """

    def __init__(self, topic: str, func: Callable, order: int) -> None:
        if not callable(func):
            raise TypeError(
                f"Registered callback is not callable. \"{func}\""
            )

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


class EventSystem:
    """Encapsulate event handling into an object.

    System wraps registered callbacks and triggered events into single object,
    so it is possible to create multiple independent systems that have their
    topics and callbacks.

    Callbacks are stored by order of their registration, but it is possible to
    manually define order of callbacks using 'order' argument within
    'add_callback'.
    """

    default_order: int = 100

    def __init__(self) -> None:
        self._registered_callbacks: list[EventCallback] = []

    def add_callback(
        self,
        topic: str,
        callback: Callable | weakref_partial,
        order: int | None = None,
    ) -> EventCallback:
        """Register callback in event system.

        Args:
            topic (str): Topic for EventCallback.
            callback (Callable | weakref_partial): Function or method
                that will be called when topic is triggered.
            order (int | None): Order of callback. Lower number means
                higher priority.

        Returns:
            EventCallback: Created callback object which can be used to
                stop listening.

        """
        if order is None:
            order = self.default_order

        callback = EventCallback(topic, callback, order)
        self._registered_callbacks.append(callback)
        return callback

    def emit_event(self, event: Event) -> None:
        """Emit event object.

        Args:
            event (Event): Prepared event with topic and data.

        """
        self._process_event(event)

    def clear_callbacks(self) -> None:
        """Clear all registered callbacks."""
        self._registered_callbacks = []

    def _process_event(self, event: Event) -> None:
        """Process event topic and trigger callbacks.

        Args:
            event (Event): Prepared event with topic and data.

        """
        callbacks = tuple(sorted(
            self._registered_callbacks, key=lambda x: x.order
        ))
        for callback in callbacks:
            callback.process_event(event)
            if not callback.is_ref_valid:
                self._registered_callbacks.remove(callback)
