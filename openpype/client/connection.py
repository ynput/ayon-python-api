"""First idea of possible was how connection would work.

Question is if process will keep alive one connection to server and create
sessions from using the connection (sesssion is new connection anyway).

I think it would be  practical to have access to multiple servers using same
codebase so avoiding the singleton as only approach is very welcomed.
Possible usecases are publisihing same data to more then one server
(coop studios), maintanance tools etc.
"""


class _ServerConnection:
    """Connection to OpenPype server."""

    def __init__(self, server_url):
        pass

    def create_session(self):
        """Create session."""
        pass

    def get_server_information():
        pass

    def check_updates():
        pass


class ServerConnection:
    """Connection to OpenPype server."""

    _connections = {}

    @classmethod
    def get_connection(cls, server_url):
        """Create connection to a server."""
        if server_url not in cls._connections:
            cls._connections[server_url] = _ServerConnection(server_url)
        return cls._connections[server_url]


class ServerSession:
    """Single session connected to a server.

    Transaction based connection keeping track of changes with ability of
    commit and rollback.
    """
    pass
