from datetime import datetime
import pytest

from ayon_api import (
    get_events,
    get_default_fields_for_type,
    exceptions,
    set_timeout,
    get_timeout
)
from .conftest import TestEventFilters


@pytest.mark.parametrize("topics", TestEventFilters.topics[-3:])
@pytest.mark.parametrize(
    "event_ids",
    [None] + [pytest.param(None, marks=pytest.mark.usefixtures("event_ids"))]
)
@pytest.mark.parametrize("project_names", TestEventFilters.project_names[-3:])
@pytest.mark.parametrize("states", TestEventFilters.states[-3:])
@pytest.mark.parametrize("users", TestEventFilters.users[-3:])
@pytest.mark.parametrize("include_logs", TestEventFilters.include_logs[-3:])
@pytest.mark.parametrize("has_children", TestEventFilters.has_children[-3:])
@pytest.mark.parametrize("newer_than", TestEventFilters.newer_than[-2:])
@pytest.mark.parametrize("older_than", TestEventFilters.older_than[-2:])
@pytest.mark.parametrize("fields", TestEventFilters.fields[0:1])
def test_get_events_all_filter_combinations(
    topics,
    event_ids,
    project_names,
    states,
    users,
    include_logs,
    has_children,
    newer_than,
    older_than,
    fields
):
    """Tests all combinations of possible filters for `get_events`.

    Verifies:
        - Calls `get_events` with the provided filter parameters.
        - Ensures each event in the result set matches the specified filters.
        - Checks that the number of returned events matches the expected count
            based on the filters applied.
        - Confirms that each event contains only the specified fields, with
            no extra keys.

    Note:
        - Adjusts the timeout setting if necessary to handle a large number
            of tests and avoid timeout errors.
        - Some combinations of filter parameters may lead to a server timeout
            error. When this occurs, the test will skip instead of failing.
        - Currently, a ServerError due to timeout may occur when `has_children`
            is set to False.

    """
    if get_timeout() < 5:
        set_timeout(None) # default timeout

    try:
        res = list(get_events(
            topics=topics,
            event_ids=event_ids,
            project_names=project_names,
            states=states,
            users=users,
            include_logs=include_logs,
            has_children=has_children,
            newer_than=newer_than,
            older_than=older_than,
            fields=fields
        ))
    except exceptions.ServerError as exc:
        assert has_children is False, (
            f"{exc} even if has_children is {has_children}."
        )
        print("Warning: ServerError encountered, test skipped due to timeout.")
        pytest.skip("Skipping test due to server timeout.")

    for item in res:
        assert item.get("topic") in topics
        assert item.get("project") in project_names
        assert item.get("user") in users
        assert item.get("status") in states

        assert (newer_than is None) or (
            datetime.fromisoformat(item.get("createdAt"))
                > datetime.fromisoformat(newer_than)
        )
        assert (older_than is None) or (
            datetime.fromisoformat(item.get("createdAt"))
                < datetime.fromisoformat(older_than)
        )

    assert topics is None or len(res) == sum(len(
        list(get_events(
            topics=[topic],
            project_names=project_names,
            states=states,
            users=users,
            include_logs=include_logs,
            has_children=has_children,
            newer_than=newer_than,
            older_than=older_than,
            fields=fields
        )) or []
    ) for topic in topics)

    assert project_names is None or len(res) == sum(len(
        list(get_events(
            topics=topics,
            project_names=[project_name],
            states=states,
            users=users,
            include_logs=include_logs,
            has_children=has_children,
            newer_than=newer_than,
            older_than=older_than,
            fields=fields
        )) or []
    ) for project_name in project_names)

    assert states is None or len(res) == sum(len(
        list(get_events(
            topics=topics,
            project_names=project_names,
            states=[state],
            users=users,
            include_logs=include_logs,
            has_children=has_children,
            newer_than=newer_than,
            older_than=older_than,
            fields=fields
        )) or []
    ) for state in states)

    assert users is None or len(res) == sum(len(
        list(get_events(
            topics=topics,
            project_names=project_names,
            states=states,
            users=[user],
            include_logs=include_logs,
            has_children=has_children,
            newer_than=newer_than,
            older_than=older_than,
            fields=fields
        )) or []
    ) for user in users)

    if fields == []:
        fields = get_default_fields_for_type("event")

    assert fields is None \
        or all(
            set(event.keys()) == set(fields)
            for event in res
        )
