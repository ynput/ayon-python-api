from __future__ import annotations

import copy
import numbers
from abc import ABC, abstractmethod
import typing
from typing import Optional, Iterable, Any, Generator

from .exceptions import GraphQlQueryFailed
from .utils import SortOrder

if typing.TYPE_CHECKING:
    from typing import Union

    from .server_api import ServerAPI

FIELD_VALUE = object()


def fields_to_dict(fields: Optional[Iterable[str]]) -> dict:
    output = {}
    if not fields:
        return output

    for field in fields:
        hierarchy = field.split(".")
        last = hierarchy.pop(-1)
        value = output
        for part in hierarchy:
            if value is FIELD_VALUE:
                break

            if part not in value:
                value[part] = {}
            value = value[part]

        if value is not FIELD_VALUE:
            value[last] = FIELD_VALUE
    return output


class QueryVariable:
    """Object representing single varible used in GraphQlQuery.

    Variable definition is in GraphQl query header but it's value is used
    in fields.

    Args:
        variable_name (str): Name of variable in query.

    """
    def __init__(self, variable_name: str) -> None:
        self._variable_name = variable_name
        self._name = f"${variable_name}"

    @property
    def name(self) -> str:
        """Name used in field filter."""
        return self._name

    @property
    def variable_name(self) -> str:
        """Name of variable in query definition."""
        return self._variable_name

    def __hash__(self):
        return self._name.__hash__()

    def __str__(self) -> str:
        return self._name

    def __format__(self, *args, **kwargs) -> str:
        return self._name.__format__(*args, **kwargs)


class GraphQlQuery:
    """GraphQl query which can have fields to query.

    Single use object which can be used only for one query. Object and children
    objects keep track about paging and progress.

    Args:
        name (str): Name of query.

    """
    offset = 2

    def __init__(self, name: str, order: Optional[int] = None) -> None:
        self._name = name
        self._variables = {}
        self._children = []
        self._has_multiple_edge_fields = None
        self._order = SortOrder.parse_value(order, SortOrder.ascending)

    @property
    def indent(self) -> int:
        """Indentation for preparation of query string.

        Returns:
            int: Ident spaces.

        """
        return 0

    @property
    def child_indent(self) -> int:
        """Indentation for preparation of query string used by children.

        Returns:
            int: Ident spaces for children.

        """
        return self.indent

    @property
    def need_query(self) -> bool:
        """Still need query from server.

        Needed for edges which use pagination.

        Returns:
            bool: If still need query from server.

        """
        for child in self._children:
            if child.need_query:
                return True
        return False

    @property
    def has_multiple_edge_fields(self) -> bool:
        if self._has_multiple_edge_fields is None:
            edge_counter = 0
            for child in self._children:
                edge_counter += child.sum_edge_fields(2)
                if edge_counter > 1:
                    break
            self._has_multiple_edge_fields = edge_counter > 1

        return self._has_multiple_edge_fields

    def add_variable(
        self, key: str, value_type: str, value: Optional[Any] = None
    ) -> QueryVariable:
        """Add variable to query.

        Args:
            key (str): Variable name.
            value_type (str): Type of expected value in variables. This is
                graphql type e.g. "[String!]", "Int", "Boolean", etc.
            value (Any): Default value for variable. Can be changed later.

        Returns:
            QueryVariable: Created variable object.

        Raises:
            KeyError: If variable was already added before.

        """
        if key in self._variables:
            raise KeyError(
                "Variable \"{}\" was already set with type {}.".format(
                    key, value_type
                )
            )

        variable = QueryVariable(key)
        self._variables[key] = {
            "type": value_type,
            "variable": variable,
            "value": value
        }
        return variable

    def get_variable(self, key: str) -> QueryVariable:
        """Variable object.

        Args:
            key (str): Variable name added to headers.

        Returns:
            QueryVariable: Variable object used in query string.

        """
        return self._variables[key]["variable"]

    def get_variable_value(
        self, key: str, default: Optional[Any] = None
    ) -> Any:
        """Get Current value of variable.

        Args:
            key (str): Variable name.
            default (Any): Default value if variable is available.

        Returns:
            Any: Variable value.

        """
        variable_item = self._variables.get(key)
        if variable_item:
            return variable_item["value"]
        return default

    def set_variable_value(self, key: str, value: Any) -> None:
        """Set value for variable.

        Args:
            key (str): Variable name under which the value is stored.
            value (Any): Variable value used in query. Variable is not used
                if value is 'None'.
        """
        self._variables[key]["value"] = value

    def get_variable_keys(self) -> set[str]:
        """Get all variable keys.

        Returns:
            set[str]: Variable keys.

        """
        return set(self._variables.keys())

    def get_variables_values(self) -> dict[str, Any]:
        """Calculate variable values used that should be used in query.

        Variables with value set to 'None' are skipped.

        Returns:
            dict[str, Any]: Variable values by their name.

        """
        output = {}
        for key, item in self._variables.items():
            value = item["value"]
            if value is not None:
                output[key] = item["value"]

        return output

    def add_obj_field(self, field: BaseGraphQlQueryField) -> None:
        """Add field object to children.

        Args:
            field (BaseGraphQlQueryField): Add field to query children.

        """
        if field in self._children:
            return

        self._children.append(field)
        field.set_parent(self)

    def add_field_with_edges(self, name: str) -> GraphQlQueryEdgeField:
        """Add field with edges to query.

        Args:
            name (str): Field name e.g. 'tasks'.

        Returns:
            GraphQlQueryEdgeField: Created field object.

        """
        item = GraphQlQueryEdgeField(name, self, self._order)
        self.add_obj_field(item)
        return item

    def add_field(self, name: str) -> GraphQlQueryField:
        """Add field to query.

        Args:
            name (str): Field name e.g. 'id'.

        Returns:
            GraphQlQueryField: Created field object.

        """
        item = GraphQlQueryField(name, self, self._order)
        self.add_obj_field(item)
        return item

    def get_field_by_keys(
        self, keys: Iterable[str]
    ) -> Optional[BaseGraphQlQueryField]:
        keys = list(keys)
        if not keys:
            return None

        key = keys.pop(0)
        for child in self._children:
            if child.name == key:
                return child.get_field_by_keys(keys)
        return None

    def get_field_by_path(
        self, path: str
    ) -> Optional[BaseGraphQlQueryField]:
        return self.get_field_by_keys(path.split("/"))

    def calculate_query(self) -> str:
        """Calculate query string which is sent to server.

        Returns:
            str: GraphQl string with variables and headers.

        Raises:
            ValueError: Query has no fiels.

        """
        if not self._children:
            raise ValueError("Missing fields to query")

        variables = []
        for item in self._variables.values():
            if item["value"] is None:
                continue

            variables.append(f"{item['variable']}: {item['type']}")

        variables_str = ""
        if variables:
            variables_str = f"({','.join(variables)})"
        header = f"query {self._name}{variables_str}"

        output = []
        output.append(header + " {")
        for field in self._children:
            output.append(field.calculate_query())
        output.append("}")

        return "\n".join(output)

    def parse_result(
        self,
        data: dict[str, Any],
        output: dict[str, Any],
        progress_data: dict[str, Any],
    ) -> None:
        """Parse data from response for output.

        Output is stored to passed 'output' variable. That's because of paging
        during which objects must have access to both new and previous values.

        Args:
            data (dict[str, Any]): Data received using calculated query.
            output (dict[str, Any]): Where parsed data are stored.
            progress_data (dict[str, Any]): Data used for paging.

        """
        if not data:
            return

        for child in self._children:
            child.parse_result(data, output, progress_data)

    def query(self, con: ServerAPI) -> dict[str, Any]:
        """Do a query from server.

        Args:
            con (ServerAPI): Connection to server with 'query' method.

        Returns:
            dict[str, Any]: Parsed output from GraphQl query.

        """
        progress_data = {}
        output = {}
        while self.need_query:
            query_str = self.calculate_query()
            variables = self.get_variables_values()
            response = con.query_graphql(
                query_str,
                self.get_variables_values()
            )
            if response.errors:
                raise GraphQlQueryFailed(response.errors, query_str, variables)
            self.parse_result(response.data["data"], output, progress_data)

        return output

    def continuous_query(
        self, con: ServerAPI
    ) -> Generator[dict[str, Any], None, None]:
        """Do a query from server.

        Args:
            con (ServerAPI): Connection to server with 'query' method.

        Returns:
            dict[str, Any]: Parsed output from GraphQl query.

        """
        progress_data = {}
        if self.has_multiple_edge_fields:
            output = {}
            while self.need_query:
                query_str = self.calculate_query()
                variables = self.get_variables_values()
                response = con.query_graphql(query_str, variables)
                if response.errors:
                    raise GraphQlQueryFailed(
                        response.errors, query_str, variables
                    )
                self.parse_result(response.data["data"], output, progress_data)

            yield output

        else:
            while self.need_query:
                output = {}
                query_str = self.calculate_query()
                variables = self.get_variables_values()
                response = con.query_graphql(query_str, variables)
                if response.errors:
                    raise GraphQlQueryFailed(
                        response.errors, query_str, variables
                    )

                self.parse_result(response.data["data"], output, progress_data)

                yield output


class BaseGraphQlQueryField(ABC):
    """Field in GraphQl query.

    Args:
        name (str): Name of field.
        parent (Union[BaseGraphQlQueryField, GraphQlQuery]): Parent object of a
            field.

    """
    def __init__(
        self,
        name: str,
        parent: Union[BaseGraphQlQueryField, GraphQlQuery],
        order: SortOrder,
    ):
        if isinstance(parent, GraphQlQuery):
            query_item = parent
        else:
            query_item = parent.query_item

        self._name = name
        self._parent = parent

        self._filters = {}

        self._children = []
        # Value is changed on first parse of result
        self._need_query = True

        self._query_item = query_item

        self._path = None

        self._limit = None
        self._order = order
        self._fetched_counter = 0

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.path}>"

    def get_name(self) -> str:
        return self._name

    name = property(get_name)

    def get_field_by_keys(
        self, keys: Iterable[str]
    ) -> Optional[BaseGraphQlQueryField]:
        keys = list(keys)
        if not keys:
            return self

        key = keys.pop(0)
        for child in self._children:
            if child.name == key:
                return child.get_field_by_keys(keys)
        return None

    def set_limit(self, limit: Optional[int]) -> None:
        self._limit = limit

    def set_order(self, order: SortOrder) -> None:
        order = SortOrder.parse_value(order)
        if order is None:
            raise ValueError(
                f"Got invalid value {order}."
                f" Expected {SortOrder.ascending} or {SortOrder.descending}"
            )
        self._order = order

    def set_ascending_order(self, enabled: bool = True) -> None:
        self.set_order(
            SortOrder.ascending if enabled else SortOrder.descending
        )

    def set_descending_order(self, enabled: bool = True) -> None:
        self.set_ascending_order(not enabled)

    def add_variable(
        self,
        key: str,
        value_type: str,
        value: Optional[Any] = None,
    ) -> QueryVariable:
        """Add variable to query.

        Args:
            key (str): Variable name.
            value_type (str): Type of expected value in variables. This is
                graphql type e.g. "[String!]", "Int", "Boolean", etc.
            value (Any): Default value for variable. Can be changed later.

        Returns:
            QueryVariable: Created variable object.

        Raises:
            KeyError: If variable was already added before.

        """
        return self._parent.add_variable(key, value_type, value)

    def get_variable(self, key: str) -> QueryVariable:
        """Variable object.

        Args:
            key (str): Variable name added to headers.

        Returns:
            QueryVariable: Variable object used in query string.

        """
        return self._parent.get_variable(key)

    @property
    def need_query(self) -> bool:
        """Still need query from server.

        Needed for edges which use pagination. Look into children values too.

        Returns:
            bool: If still need query from server.

        """
        if self._need_query:
            return True

        for child in self._children_iter():
            if child.need_query:
                return True
        return False

    def _children_iter(self) -> Generator[BaseGraphQlQueryField, None, None]:
        """Iterate over all children fields of object.

        Returns:
            Iterator[BaseGraphQlQueryField]: Children fields.

        """
        for child in self._children:
            yield child

    def sum_edge_fields(self, max_limit: Optional[int] = None) -> int:
        """Check how many edge fields query has.

        In case there are multiple edge fields or are nested the query can't
        yield mid cursor results.

        Args:
            max_limit (int): Skip rest of counting if counter is bigger then
                entered number.

        Returns:
            int: Counter edge fields

        """
        counter = 0
        if isinstance(self, GraphQlQueryEdgeField):
            counter = 1

        for child in self._children_iter():
            counter += child.sum_edge_fields(max_limit)
            if max_limit is not None and counter >= max_limit:
                break
        return counter

    @property
    def offset(self) -> int:
        return self._query_item.offset

    @property
    def indent(self) -> int:
        return self._parent.child_indent + self.offset

    @property
    @abstractmethod
    def child_indent(self) -> int:
        pass

    @property
    def query_item(self) -> GraphQlQuery:
        return self._query_item

    @property
    @abstractmethod
    def has_edges(self) -> bool:
        pass

    @property
    def child_has_edges(self) -> bool:
        for child in self._children_iter():
            if child.has_edges or child.child_has_edges:
                return True
        return False

    @property
    def path(self) -> str:
        """Field path for debugging purposes.

        Returns:
            str: Field path in query.

        """
        if self._path is None:
            if isinstance(self._parent, GraphQlQuery):
                path = self._name
            else:
                path = "/".join((self._parent.path, self._name))
            self._path = path
        return self._path

    def reset_cursor(self) -> None:
        for child in self._children_iter():
            child.reset_cursor()

    def get_variable_value(
        self, key: str, default: Optional[Any] = None
    ) -> Any:
        return self._query_item.get_variable_value(key, default)

    def set_variable_value(self, key: str, value: Any) -> None:
        self._query_item.set_variable_value(key, value)

    def set_filter(self, key: str, value: Any) -> None:
        self._filters[key] = value

    def has_filter(self, key: str) -> bool:
        return key in self._filters

    def remove_filter(self, key: str) -> None:
        self._filters.pop(key, None)

    def set_parent(
        self, parent: Union[BaseGraphQlQueryField, GraphQlQuery]
    ) -> None:
        if self._parent is parent:
            return
        self._parent = parent
        parent.add_obj_field(self)

    def add_obj_field(self, field: BaseGraphQlQueryField) -> None:
        if field in self._children:
            return

        self._children.append(field)
        field.set_parent(self)

    def add_field_with_edges(self, name: str) -> GraphQlQueryEdgeField:
        item = GraphQlQueryEdgeField(name, self, self._order)
        self.add_obj_field(item)
        return item

    def add_field(self, name: str) -> GraphQlQueryField:
        item = GraphQlQueryField(name, self, self._order)
        self.add_obj_field(item)
        return item

    def _filter_value_to_str(self, value: Any) -> Optional[str]:
        if isinstance(value, QueryVariable):
            if self.get_variable_value(value.variable_name) is None:
                return None
            return str(value)

        if isinstance(value, numbers.Number):
            return str(value)

        if isinstance(value, str):
            return f'"{value}"'

        if isinstance(value, (list, set, tuple)):
            joined_values = ", ".join(
                self._filter_value_to_str(item)
                for item in iter(value)
            )
            return f"[{joined_values}]"

        raise TypeError(
            "Unknown type to convert '{}'".format(str(type(value)))
        )

    def get_filters(self) -> dict[str, Any]:
        """Receive filters for item.

        By default just use copy of set filters.

        Returns:
            dict[str, Any]: Fields filters.

        """
        return copy.deepcopy(self._filters)

    def _filters_to_string(self) -> str:
        filters = self.get_filters()
        if not filters:
            return ""

        filter_items = []
        for key, value in filters.items():
            string_value = self._filter_value_to_str(value)
            if string_value is None:
                continue

            filter_items.append(f"{key}: {string_value}")

        if not filter_items:
            return ""
        joined_items = ", ".join(filter_items)
        return f"({joined_items})"

    def _fake_children_parse(self) -> None:
        """Mark children as they don't need query."""
        for child in self._children_iter():
            child.parse_result({}, {}, {})

    @abstractmethod
    def calculate_query(self) -> str:
        pass

    @abstractmethod
    def parse_result(
        self,
        data: dict[str, Any],
        output: dict[str, Any],
        progress_data: dict[str, Any],
    ) -> None:
        pass


class GraphQlQueryField(BaseGraphQlQueryField):
    has_edges = False

    @property
    def child_indent(self) -> int:
        return self.indent

    def parse_result(
        self,
        data: dict[str, Any],
        output: dict[str, Any],
        progress_data: dict[str, Any],
    ) -> None:
        if not isinstance(data, dict):
            raise TypeError(
                f"{self._name} Expected 'dict' type got '{type(data)}'"
            )

        self._need_query = False
        value = data.get(self._name)
        if value is None:
            self._fake_children_parse()
            if self._name in data:
                output[self._name] = None
            return

        if not self._children:
            output[self._name] = value
            return

        output_value = output.get(self._name)
        if isinstance(value, dict):
            if output_value is None:
                output_value = {}
                output[self._name] = output_value

            for child in self._children:
                child.parse_result(value, output_value, progress_data)
            return

        if output_value is None:
            output_value = []
            output[self._name] = output_value

        if not value:
            self._fake_children_parse()
            return

        diff = len(value) - len(output_value)
        if diff > 0:
            for _ in range(diff):
                output_value.append({})

        for idx, item in enumerate(value):
            item_value = output_value[idx]
            for child in self._children:
                child.parse_result(item, item_value, progress_data)

    def calculate_query(self) -> str:
        offset = self.indent * " "
        header = f"{offset}{self._name}{self._filters_to_string()}"
        if not self._children:
            return header

        output = []
        output.append(header + " {")

        output.extend([
            field.calculate_query()
            for field in self._children
        ])
        output.append(offset + "}")

        return "\n".join(output)


class GraphQlQueryEdgeField(BaseGraphQlQueryField):
    has_edges = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cursor = None
        self._edge_children = []

    @property
    def child_indent(self) -> int:
        offset = self.offset * 2
        return self.indent + offset

    def _children_iter(self) -> Generator[BaseGraphQlQueryField, None, None]:
        for child in super()._children_iter():
            yield child

        for child in self._edge_children:
            yield child

    def add_obj_field(self, field: BaseGraphQlQueryField) -> None:
        if field in self._edge_children:
            return

        super().add_obj_field(field)

    def add_obj_edge_field(self, field: BaseGraphQlQueryField) -> None:
        if field in self._edge_children or field in self._children:
            return

        self._edge_children.append(field)
        field.set_parent(self)

    def add_edge_field(self, name: str) -> GraphQlQueryEdgeField:
        item = GraphQlQueryEdgeField(name, self, self._order)
        self.add_obj_edge_field(item)
        return item

    def reset_cursor(self) -> None:
        # Reset cursor only for edges
        self._cursor = None
        self._need_query = True

        super().reset_cursor()

    def parse_result(
        self,
        data: dict[str, Any],
        output: dict[str, Any],
        progress_data: dict[str, Any],
    ) -> None:
        if not isinstance(data, dict):
            raise TypeError("{} Expected 'dict' type got '{}'".format(
                self._name, str(type(data))
            ))

        value = data.get(self._name)
        if value is None:
            self._fake_children_parse()
            self._need_query = False
            return

        if self._name in output:
            node_values = output[self._name]
        else:
            node_values = []
            output[self._name] = node_values

        nodes_by_cursor = {}
        handle_cursors = self.child_has_edges
        if handle_cursors:
            cursor_key = self._get_cursor_key()
            if cursor_key in progress_data:
                nodes_by_cursor = progress_data[cursor_key]
            else:
                progress_data[cursor_key] = nodes_by_cursor

        page_info = value["pageInfo"]
        new_cursor = page_info["endCursor"]
        self._need_query = page_info["hasNextPage"]
        edges = value["edges"]
        # Fake result parse
        if not edges:
            self._fake_children_parse()

        self._fetched_counter += len(edges)
        if self._limit and self._fetched_counter >= self._limit:
            self._need_query = False

        for edge in edges:
            if not handle_cursors:
                edge_value = {}
                node_values.append(edge_value)
            else:
                edge_cursor = edge["cursor"]
                edge_value = nodes_by_cursor.get(edge_cursor)
                if edge_value is None:
                    edge_value = {}
                    nodes_by_cursor[edge_cursor] = edge_value
                    node_values.append(edge_value)

            for child in self._edge_children:
                child.parse_result(edge, edge_value, progress_data)

            for child in self._children:
                child.parse_result(edge["node"], edge_value, progress_data)

        if not self._need_query:
            return

        change_cursor = True
        for child in self._children_iter():
            if child.need_query:
                change_cursor = False

        if change_cursor:
            for child in self._children_iter():
                child.reset_cursor()
            self._cursor = new_cursor

    def _get_cursor_key(self) -> str:
        return f"{self.path}/__cursor__"

    def get_filters(self) -> dict[str, Any]:
        filters = super().get_filters()
        limit_key = "first"
        if self._order == SortOrder.descending:
            limit_key = "last"

        limit_amount = 300
        if self._limit:
            total = self._fetched_counter + limit_amount
            if total > self._limit:
                limit_amount = self._limit - self._fetched_counter

        filters[limit_key] = limit_amount

        if self._cursor:
            filters["after"] = self._cursor
        return filters

    def calculate_query(self) -> str:
        if not self._children and not self._edge_children:
            raise ValueError("Missing child definitions for edges {}".format(
                self.path
            ))

        offset = self.indent * " "
        header = f"{offset}{self._name}{self._filters_to_string()}"

        output = []
        output.append(header + " {")

        edges_offset = offset + self.offset * " "
        node_offset = edges_offset + self.offset * " "
        output.append(edges_offset + "edges {")
        for field in self._edge_children:
            output.append(field.calculate_query())

        if self._children:
            output.append(node_offset + "node {")

            for field in self._children:
                output.append(
                    field.calculate_query()
                )

            output.append(node_offset + "}")
            if self.child_has_edges:
                output.append(node_offset + "cursor")

        output.append(edges_offset + "}")

        # Add page information
        output.append(edges_offset + "pageInfo {")
        for page_key in (
            "endCursor",
            "hasNextPage",
        ):
            output.append(node_offset + page_key)
        output.append(edges_offset + "}")
        output.append(offset + "}")

        return "\n".join(output)


INTROSPECTION_QUERY = """
  query IntrospectionQuery {
    __schema {
      queryType { name }
      mutationType { name }
      subscriptionType { name }
      types {
        ...FullType
      }
      directives {
        name
        description
        locations
        args {
          ...InputValue
        }
      }
    }
  }
  fragment FullType on __Type {
    kind
    name
    description
    fields(includeDeprecated: true) {
      name
      description
      args {
        ...InputValue
      }
      type {
        ...TypeRef
      }
      isDeprecated
      deprecationReason
    }
    inputFields {
      ...InputValue
    }
    interfaces {
      ...TypeRef
    }
    enumValues(includeDeprecated: true) {
      name
      description
      isDeprecated
      deprecationReason
    }
    possibleTypes {
      ...TypeRef
    }
  }
  fragment InputValue on __InputValue {
    name
    description
    type { ...TypeRef }
    defaultValue
  }
  fragment TypeRef on __Type {
    kind
    name
    ofType {
      kind
      name
      ofType {
        kind
        name
        ofType {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
              ofType {
                kind
                name
                ofType {
                  kind
                  name
                }
              }
            }
          }
        }
      }
    }
  }
"""
