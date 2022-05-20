"""Keep singleton objects in memory with global access.

This ideally should not be used to avoid singleton dependency which cause
that some functionality can't be handled. Is needed as whole OpenPype 3
is based on this singleton access and would be impossible to remove it at once.
"""


class HostAlreadyRegistered(Exception):
    pass


class _GlobalContext:
    registered_host = None


def is_installed():
    """Return state of installation.

    Returns:
        bool: True if installed, False otherwise.
    """

    return registered_host() is not None


def register_host(host, force=False):
    """Register a host for the current process.

    Can be registered only one at a time.

    Arguments:
        host (HostImplementation): An object of host implementation.
        force (bool): Ignore if there is already registered one.
    """

    if is_installed():
        if not force:
            raise HostAlreadyRegistered("Host is already registered")
        deregister_host()

    _GlobalContext.registered_host = host


def registered_host():
    """Currently registered host."""

    return _GlobalContext.registered_host


def deregister_host():
    _GlobalContext.registered_host = None
