import copy

from .server_api import get_server_api_connection


class ServerEvent(object):
    def __init__(
        self,
        topic,
        sender=None,
        hash=None,
        project_name=None,
        username=None,
        dependencies=None,
        description=None,
        summary=None,
        payload=None,
        finished=True,
        store=True,
    ):
        if dependencies is None:
            dependencies = []
        if payload is None:
            payload = {}
        if summary is None:
            summary = {}

        self.topic = topic
        self.sender = sender
        self.hash = hash
        self.project_name = project_name
        self.username = username
        self.dependencies = dependencies
        self.summary = summary
        self.payload = payload
        self.finished = finished
        self.store = store

    def to_data(self):
        return {
            "topic": self.topic,
            "sender": self.sender,
            "hash": self.hash,
            "project": self.project_name,
            "user": self.username,
            "dependencies": copy.deepcopy(self.dependencies),
            "description": self.description,
            "summary": copy.deepcopy(self.summary),
            "payload": self.payload,
            "finished": self.finished,
            "store": self.store
        }


def dispatch_event(
    topic,
    sender=None,
    hash=None,
    project_name=None,
    username=None,
    dependencies=None,
    description=None,
    summary=None,
    payload=None,
    finished=True,
    store=True,
):
    """Dispatch event to server.

    Arg:
        topic (str): Event topic used for filtering of listeners.
        sender (Optional[str]): Sender of event.
        hash (Optional[str]): Event hash.
        project_name (Optional[str]): Project name.
        username (Optional[str]): Username which triggered event.
        dependencies (Optional[list[str]]): List of event id deprendencies.
        description (Optional[str]): Description of event.
        summary (Optional[dict[str, Any]]): Summary of event that can be used
            for simple filtering on listeners.
        payload (Optional[dict[str, Any]]): Full payload of event data with
            all details.
        finished (bool): Mark event as finished on dispatch.
        store (bool): Store event in event queue for possible future processing
            otherwise is event send only to active listeners.
    """

    event = ServerEvent(
        topic,
        sender,
        hash,
        project_name,
        username,
        dependencies,
        description,
        summary,
        payload,
        finished,
        store
    )
    con = get_server_api_connection()
    response = con.post("events", json=event.to_data())
    if response:
        print(response, response.data)
        return event
    return None
