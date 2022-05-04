"""Attributes that are on entities to be able catch changes of data."""

from .exceptions import ImmutableAttributeError

EMPTY_VALUE = object()


class EntityAttribute:
    """Example of attribute possible implementation.

    Object of attributes should replace all attributes on entities to track
    changes and avoid changes of immutable keys.

    This approach requires to known schema of entities which may be complicated
    with dynamic attributes not in default database attributes.
    """

    def __init__(self, entity, name, mutable, *args, **kwargs):
        self._entity = entity
        self._name = name
        self._mutable = mutable

    @property
    def entity(self):
        return self._entity

    @property
    def session(self):
        return self._entity.session

    @property
    def name(self):
        return self._name

    def get_value(self):
        cached_data = self.session.cached_data[self.entity.id]
        if self._name in cached_data:
            return cached_data[self._name]
        return self.session.get_attribute_value(self.entity, self.name)

    def set_value(self, value):
        if not self._mutable:
            raise ImmutableAttributeError("")
        self.session.set_attribute_value(self.entity, self.name)


class DictContent:
    pass


class ListContent:
    pass
