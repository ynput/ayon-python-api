import typing
from typing import Set

if typing.TYPE_CHECKING:
    from .typing import AnyEntityDict


class _BaseServerAPI:
    def get(self, entrypoint: str, **kwargs):
        raise NotImplementedError()

    def post(self, entrypoint: str, **kwargs):
        raise NotImplementedError()

    def put(self, entrypoint: str, **kwargs):
        raise NotImplementedError()

    def patch(self, entrypoint: str, **kwargs):
        raise NotImplementedError()

    def delete(self, entrypoint: str, **kwargs):
        raise NotImplementedError()

    def raw_get(self, entrypoint: str, **kwargs):
        raise NotImplementedError()

    def raw_post(self, entrypoint: str, **kwargs):
        raise NotImplementedError()

    def raw_put(self, entrypoint: str, **kwargs):
        raise NotImplementedError()

    def raw_patch(self, entrypoint: str, **kwargs):
        raise NotImplementedError()

    def raw_delete(self, entrypoint: str, **kwargs):
        raise NotImplementedError()

    def get_default_settings_variant(self) -> str:
        raise NotImplementedError()

    def get_default_fields_for_type(self, entity_type: str) -> Set[str]:
        raise NotImplementedError()

    def _convert_entity_data(self, entity: "AnyEntityDict"):
        raise NotImplementedError()
