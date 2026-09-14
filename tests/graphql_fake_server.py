"""Minimal in-memory GraphQL server that speaks the subset of the schema
that 'ayon_api.graphql' generates. Used to exercise the pagination engine.
"""
import re
import json


class Node:
    def __init__(self, name, args, children):
        self.name = name
        self.args = args
        self.children = children

    def child(self, name):
        for child in self.children:
            if child.name == name:
                return child
        return None

    def __repr__(self):
        return f"<Node {self.name} args={self.args}>"


def _parse_args(args_str, variables):
    """Parse 'first: 300, after: "x", ids: $ids' into a dict."""
    if not args_str:
        return {}
    out = {}
    # split on top level commas
    parts = []
    depth = 0
    in_str = False
    current = ""
    for char in args_str:
        if in_str:
            current += char
            if char == '"':
                in_str = False
            continue
        if char == '"':
            in_str = True
            current += char
            continue
        if char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
        if char == "," and depth == 0:
            parts.append(current)
            current = ""
            continue
        current += char
    if current.strip():
        parts.append(current)

    for part in parts:
        key, _, value = part.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("$"):
            value = variables.get(value[1:])
        elif value.startswith('"'):
            value = json.loads(value)
        elif value.startswith("["):
            value = json.loads(value)
        elif value in ("true", "false"):
            value = value == "true"
        else:
            value = int(value)
        out[key] = value
    return out


LINE_RE = re.compile(
    r"^(?P<name>\w+)(?:\((?P<args>.*)\))?(?P<open>\s*\{)?$"
)


def parse_query(query_str, variables):
    lines = [
        line.strip()
        for line in query_str.splitlines()
        if line.strip()
    ]
    # Drop query header
    assert lines[0].startswith("query"), lines[0]
    root = Node("__root__", {}, [])
    stack = [root]
    for line in lines[1:]:
        if line == "}":
            stack.pop()
            continue
        match = LINE_RE.match(line)
        if match is None:
            raise ValueError(f"Unparsable line: {line!r}")
        args = _parse_args(match.group("args"), variables)
        node = Node(match.group("name"), args, [])
        stack[-1].children.append(node)
        if match.group("open"):
            stack.append(node)
    if stack:
        raise ValueError("Unbalanced query")
    return root


class FakeServer:
    """Resolve a parsed query against plain python data.

    Data is a dict of entity collections, e.g.::

        {
            "project": {
                "name": "proj",
                "folders": [
                    {"id": "f1", "name": "a", "links": [{"id": "l1"}]},
                ],
            }
        }

    Any list value is served as a connection (edges/pageInfo), any dict
    value as a plain object.

    """
    def __init__(
        self,
        data,
        cursor_func=None,
        max_page_size=None,
        reverse_last_pages=False,
    ):
        # AYON server returns edges of page queried with 'last' from
        #   the newest item
        self._reverse_last_pages = reverse_last_pages
        self._data = data
        self._cursor_func = cursor_func or self._default_cursor
        self._max_page_size = max_page_size
        self.calls = []
        self.queries = []

    @staticmethod
    def _default_cursor(path, index, entity):
        return f"{path}:{index}"

    def query_graphql(self, query_str, variables):
        self.queries.append(query_str)
        self.calls.append((query_str, dict(variables)))
        root = parse_query(query_str, variables)
        data = {}
        for child in root.children:
            data[child.name] = self._resolve(child, self._data, child.name)
        return FakeResponse({"data": data})

    def _resolve(self, node, parent_value, path):
        value = parent_value.get(node.name) if parent_value else None
        if isinstance(value, list):
            return self._resolve_connection(node, value, path)
        if isinstance(value, dict):
            return self._resolve_object(node, value, path)
        # leaf
        if node.children:
            raise ValueError(
                f"Requested sub fields of leaf {path}"
            )
        return value

    def _resolve_object(self, node, value, path):
        out = {}
        for child in node.children:
            out[child.name] = self._resolve(
                child, value, f"{path}/{child.name}"
            )
        return out

    def _resolve_connection(self, node, items, path):
        edges_field = node.child("edges")
        if edges_field is None:
            raise ValueError(f"Connection {path} misses 'edges'")
        cursors = [
            self._cursor_func(path, idx, item)
            for idx, item in enumerate(items)
        ]
        args = node.args
        start = 0
        end = len(items)
        reverse_paging = "last" in args
        if "after" in args:
            cursor = args["after"]
            if cursor not in cursors:
                raise ValueError(
                    f"Unknown 'after' cursor {cursor!r} for {path}"
                )
            start = cursors.index(cursor) + 1
        if "before" in args:
            cursor = args["before"]
            if cursor not in cursors:
                raise ValueError(
                    f"Unknown 'before' cursor {cursor!r} for {path}"
                )
            end = cursors.index(cursor)

        limit = args.get("first", args.get("last"))
        if limit is None:
            raise ValueError(f"Missing 'first'/'last' for {path}")
        if limit < 0:
            raise ValueError(f"Negative page size {limit} for {path}")
        if self._max_page_size is not None:
            limit = min(limit, self._max_page_size)

        window = list(range(start, end))
        if reverse_paging:
            page_idxs = window[-limit:] if limit else []
        else:
            page_idxs = window[:limit]

        if reverse_paging and self._reverse_last_pages:
            page_idxs.reverse()

        node_field = edges_field.child("node")
        edges = []
        for idx in page_idxs:
            item = items[idx]
            edge = {}
            edges.append(edge)
            for child in edges_field.children:
                if child.name == "node":
                    continue
                if child.name == "cursor":
                    edge["cursor"] = cursors[idx]
                    continue
                edge[child.name] = self._resolve(
                    child, item, f"{path}[{idx}]/{child.name}"
                )
            if node_field is not None:
                edge["node"] = self._resolve_object(
                    node_field, item, f"{path}[{idx}]"
                )

        has_next = bool(page_idxs) and max(page_idxs) < end - 1
        has_prev = bool(page_idxs) and min(page_idxs) > start
        page_info = {
            "endCursor": cursors[page_idxs[-1]] if page_idxs else None,
            "startCursor": cursors[page_idxs[0]] if page_idxs else None,
            "hasNextPage": has_next,
            "hasPreviousPage": has_prev,
        }
        out = {"edges": edges, "pageInfo": {}}
        requested_page_info = node.child("pageInfo")
        if requested_page_info is not None:
            for child in requested_page_info.children:
                out["pageInfo"][child.name] = page_info[child.name]
        return out


class FakeResponse:
    def __init__(self, data):
        self.data = data
        self.errors = data.get("errors")
