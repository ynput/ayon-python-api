from __future__ import annotations

import warnings
import typing
from typing import Optional, Any, Iterable, Generator

from ayon_api.utils import SortOrder, prepare_list_filters
from ayon_api.graphql_queries import events_graphql_query

from .base import BaseServerAPI

if typing.TYPE_CHECKING:
    from typing import Union

    from ayon_api.typing import EventFilter


class EventsAPI(BaseServerAPI):
    def get_event(self, event_id: str) -> Optional[dict[str, Any]]:
        """Query full event data by id.

        Events received using event server do not contain full information. To
        get the full event information is required to receive it explicitly.

        Args:
            event_id (str): Event id.

        Returns:
            dict[str, Any]: Full event data.

        """
        response = self.get(f"events/{event_id}")
        response.raise_for_status()
        return response.data

    def get_events(
        self,
        topics: Optional[Iterable[str]] = None,
        event_ids: Optional[Iterable[str]] = None,
        project_names: Optional[Iterable[str]] = None,
        statuses: Optional[Iterable[str]] = None,
        users: Optional[Iterable[str]] = None,
        include_logs: Optional[bool] = None,
        has_children: Optional[bool] = None,
        newer_than: Optional[str] = None,
        older_than: Optional[str] = None,
        fields: Optional[Iterable[str]] = None,
        limit: Optional[int] = None,
        order: Optional[SortOrder] = None,
        states: Optional[Iterable[str]] = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Get events from server with filtering options.

        Notes:
            Not all event happen on a project.

        Args:
            topics (Optional[Iterable[str]]): Name of topics.
            event_ids (Optional[Iterable[str]]): Event ids.
            project_names (Optional[Iterable[str]]): Project on which
                event happened.
            statuses (Optional[Iterable[str]]): Filtering by statuses.
            users (Optional[Iterable[str]]): Filtering by users
                who created/triggered an event.
            include_logs (Optional[bool]): Query also log events.
            has_children (Optional[bool]): Event is with/without children
                events. If 'None' then all events are returned, default.
            newer_than (Optional[str]): Return only events newer than given
                iso datetime string.
            older_than (Optional[str]): Return only events older than given
                iso datetime string.
            fields (Optional[Iterable[str]]): Fields that should be received
                for each event.
            limit (Optional[int]): Limit number of events to be fetched.
            order (Optional[SortOrder]): Order events in ascending
                or descending order. It is recommended to set 'limit'
                when used descending.
            states (Optional[Iterable[str]]): DEPRECATED Filtering by states.
                Use 'statuses' instead.

        Returns:
            Generator[dict[str, Any]]: Available events matching filters.

        """
        if statuses is None and states is not None:
            warnings.warn(
                (
                    "Used deprecated argument 'states' in 'get_events'."
                    " Use 'statuses' instead."
                ),
                DeprecationWarning
            )
            statuses = states

        filters = {}
        if not prepare_list_filters(
            filters,
            ("eventTopics", topics),
            ("eventIds", event_ids),
            ("projectNames", project_names),
            ("eventStatuses", statuses),
            ("eventUsers", users),
        ):
            return

        if include_logs is None:
            include_logs = False

        for filter_key, filter_value in (
            ("includeLogsFilter", include_logs),
            ("hasChildrenFilter", has_children),
            ("newerThanFilter", newer_than),
            ("olderThanFilter", older_than),
        ):
            if filter_value is not None:
                filters[filter_key] = filter_value

        if not fields:
            fields = self.get_default_fields_for_type("event")

        major, minor, patch, _, _ = self.server_version_tuple
        use_states = (major, minor, patch) <= (1, 5, 6)

        query = events_graphql_query(set(fields), order, use_states)
        for attr, filter_value in filters.items():
            query.set_variable_value(attr, filter_value)

        if limit:
            events_field = query.get_field_by_path("events")
            events_field.set_limit(limit)

        for parsed_data in query.continuous_query(self):
            for event in parsed_data["events"]:
                yield event

    def update_event(
        self,
        event_id: str,
        sender: Optional[str] = None,
        project_name: Optional[str] = None,
        username: Optional[str] = None,
        status: Optional[str] = None,
        description: Optional[str] = None,
        summary: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
        progress: Optional[int] = None,
        retries: Optional[int] = None,
    ) -> None:
        """Update event data.

        Args:
            event_id (str): Event id.
            sender (Optional[str]): New sender of event.
            project_name (Optional[str]): New project name.
            username (Optional[str]): New username.
            status (Optional[str]): New event status. Enum: "pending",
                "in_progress", "finished", "failed", "aborted", "restarted"
            description (Optional[str]): New description.
            summary (Optional[dict[str, Any]]): New summary.
            payload (Optional[dict[str, Any]]): New payload.
            progress (Optional[int]): New progress. Range [0-100].
            retries (Optional[int]): New retries.

        """
        kwargs = {
            key: value
            for key, value in (
                ("sender", sender),
                ("project", project_name),
                ("user", username),
                ("status", status),
                ("description", description),
                ("summary", summary),
                ("payload", payload),
                ("progress", progress),
                ("retries", retries),
            )
            if value is not None
        }

        response = self.patch(
            f"events/{event_id}",
            **kwargs
        )
        response.raise_for_status()

    def dispatch_event(
        self,
        topic: str,
        sender: Optional[str] = None,
        event_hash: Optional[str] = None,
        project_name: Optional[str] = None,
        username: Optional[str] = None,
        depends_on: Optional[str] = None,
        description: Optional[str] = None,
        summary: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
        finished: bool = True,
        store: bool = True,
        dependencies: Optional[list[str]] = None,
    ) -> RestApiResponse:
        """Dispatch event to server.

        Args:
            topic (str): Event topic used for filtering of listeners.
            sender (Optional[str]): Sender of event.
            event_hash (Optional[str]): Event hash.
            project_name (Optional[str]): Project name.
            depends_on (Optional[str]): Add dependency to another event.
            username (Optional[str]): Username which triggered event.
            description (Optional[str]): Description of event.
            summary (Optional[dict[str, Any]]): Summary of event that can
                be used for simple filtering on listeners.
            payload (Optional[dict[str, Any]]): Full payload of event data with
                all details.
            finished (bool): Mark event as finished on dispatch.
            store (bool): Store event in event queue for possible
                future processing otherwise is event send only
                to active listeners.
            dependencies (Optional[list[str]]): Deprecated.
                List of event id dependencies.

        Returns:
            RestApiResponse: Response from server.

        """
        if summary is None:
            summary = {}
        if payload is None:
            payload = {}
        event_data = {
            "topic": topic,
            "sender": sender,
            "hash": event_hash,
            "project": project_name,
            "user": username,
            "description": description,
            "summary": summary,
            "payload": payload,
            "finished": finished,
            "store": store,
        }
        if depends_on:
            event_data["dependsOn"] = depends_on

        if dependencies:
            warnings.warn(
                (
                    "Used deprecated argument 'dependencies' in"
                    " 'dispatch_event'. Use 'depends_on' instead."
                ),
                DeprecationWarning
            )

        response = self.post("events", **event_data)
        response.raise_for_status()
        return response

    def delete_event(self, event_id: str) -> None:
        """Delete event by id.

        Supported since AYON server 1.6.0.

        Args:
            event_id (str): Event id.

        Returns:
            RestApiResponse: Response from server.

        """
        response = self.delete(f"events/{event_id}")
        response.raise_for_status()

    def enroll_event_job(
        self,
        source_topic: Union[str, list[str]],
        target_topic: str,
        sender: str,
        description: Optional[str] = None,
        sequential: Optional[bool] = None,
        events_filter: Optional[EventFilter] = None,
        max_retries: Optional[int] = None,
        ignore_older_than: Optional[str] = None,
        ignore_sender_types: Optional[str] = None,
    ):
        """Enroll job based on events.

        Enroll will find first unprocessed event with 'source_topic' and will
        create new event with 'target_topic' for it and return the new event
        data.

        Use 'sequential' to control that only single target event is created
        at same time. Creation of new target events is blocked while there is
        at least one unfinished event with target topic, when set to 'True'.
        This helps when order of events matter and more than one process using
        the same target is running at the same time.

        Make sure the new event has updated status to '"finished"' status
        when you're done with logic

        Target topic should not clash with other processes/services.

        Created target event have 'dependsOn' key where is id of source topic.

        Use-case:
            - Service 1 is creating events with topic 'my.leech'
            - Service 2 process 'my.leech' and uses target topic 'my.process'
                - this service can run on 1-n machines
                - all events must be processed in a sequence by their creation
                    time and only one event can be processed at a time
                - in this case 'sequential' should be set to 'True' so only
                    one machine is actually processing events, but if one goes
                    down there are other that can take place
            - Service 3 process 'my.leech' and uses target topic 'my.discover'
                - this service can run on 1-n machines
                - order of events is not important
                - 'sequential' should be 'False'

        Args:
            source_topic (Union[str, list[str]]): Source topic to enroll with
                wildcards '*', or explicit list of topics.
            target_topic (str): Topic of dependent event.
            sender (str): Identifier of sender (e.g. service name or username).
            description (Optional[str]): Human readable text shown
                in target event.
            sequential (Optional[bool]): The source topic must be processed
                in sequence.
            events_filter (Optional[dict[str, Any]]): Filtering conditions
                to filter the source event. For more technical specifications
                look to server backed 'ayon_server.sqlfilter.Filter'.
                TODO: Add example of filters.
            max_retries (Optional[int]): How many times can be event retried.
                Default value is based on server (3 at the time of this PR).
            ignore_older_than (Optional[int]): Ignore events older than
                given number in days.
            ignore_sender_types (Optional[list[str]]): Ignore events triggered
                by given sender types.

        Returns:
            Optional[dict[str, Any]]: None if there is no event matching
                filters. Created event with 'target_topic'.

        """
        kwargs: dict[str, Any] = {
            "sourceTopic": source_topic,
            "targetTopic": target_topic,
            "sender": sender,
        }
        major, minor, patch, _, _ = self.get_server_version_tuple()
        if max_retries is not None:
            kwargs["maxRetries"] = max_retries
        if sequential is not None:
            kwargs["sequential"] = sequential
        if description is not None:
            kwargs["description"] = description
        if events_filter is not None:
            kwargs["filter"] = events_filter
        if (
            ignore_older_than is not None
            and (major, minor, patch) > (1, 5, 1)
        ):
            kwargs["ignoreOlderThan"] = ignore_older_than
        if ignore_sender_types is not None:
            if (major, minor, patch) <= (1, 5, 4):
                raise ValueError(
                    "Ignore sender types are not supported for"
                    f" your version of server {self.get_server_version()}."
                )
            kwargs["ignoreSenderTypes"] = list(ignore_sender_types)

        response = self.post("enroll", **kwargs)
        if response.status_code == 204:
            return None

        if response.status_code == 503:
            # Server is busy
            self.log.info("Server is busy. Can't enroll event now.")
            return None

        if response.status_code >= 400:
            self.log.error(response.text)
            return None

        return response.data
