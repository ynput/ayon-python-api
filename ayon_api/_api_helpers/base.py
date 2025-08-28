from __future__ import annotations

import typing
from typing import Optional, Any, Iterable

import requests

from ayon_api.utils import TransferProgress, RequestType

if typing.TYPE_CHECKING:
    from ayon_api.typing import (
        AnyEntityDict,
        ServerVersion,
        ProjectDict,
    )

_PLACEHOLDER = object()


class BaseServerAPI:
    def get_server_version(self) -> str:
        raise NotImplementedError()

    def get_server_version_tuple(self) -> ServerVersion:
        raise NotImplementedError()

    def get_base_url(self) -> str:
        raise NotImplementedError()

    def get_rest_url(self) -> str:
        raise NotImplementedError()

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

    def get_site_id(self) -> Optional[str]:
        raise NotImplementedError()

    def get_default_fields_for_type(self, entity_type: str) -> set[str]:
        raise NotImplementedError()

    def upload_file(
        self,
        endpoint: str,
        filepath: str,
        progress: Optional[TransferProgress] = None,
        request_type: Optional[RequestType] = None,
        **kwargs
    ) -> requests.Response:
        raise NotImplementedError()

    def download_file(
        self,
        endpoint: str,
        filepath: str,
        chunk_size: Optional[int] = None,
        progress: Optional[TransferProgress] = None,
    ) -> TransferProgress:
        raise NotImplementedError()

    def get_rest_entity_by_id(
        self,
        project_name: str,
        entity_type: str,
        entity_id: str,
    ) -> Optional[AnyEntityDict]:
        raise NotImplementedError()

    def get_project(
        self,
        project_name: str,
        fields: Optional[Iterable[str]] = None,
        own_attributes: bool = False,
    ) -> Optional[ProjectDict]:
        raise NotImplementedError()

    def _prepare_fields(
        self,
        entity_type: str,
        fields: set[str],
        own_attributes: bool = False,
    ):
        raise NotImplementedError()

    def _convert_entity_data(self, entity: AnyEntityDict):
        raise NotImplementedError()

    def _send_batch_operations(
        self,
        uri: str,
        operations: list[dict[str, Any]],
        can_fail: bool,
        raise_on_fail: bool
    ) -> list[dict[str, Any]]:
        raise NotImplementedError()
