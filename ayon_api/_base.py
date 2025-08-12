from __future__ import annotations

import typing
from typing import Optional

import requests

from .utils import TransferProgress, RequestType

if typing.TYPE_CHECKING:
    from .typing import AnyEntityDict


class _BaseServerAPI:
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

    def _prepare_fields(
        self,
        entity_type: str,
        fields: set[str],
        own_attributes: bool = False,
    ):
        raise NotImplementedError()

    def _convert_entity_data(self, entity: "AnyEntityDict"):
        raise NotImplementedError()
