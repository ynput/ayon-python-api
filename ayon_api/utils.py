import os
import re
import datetime
import uuid
import string
import platform
import traceback
import collections
from urllib.parse import urlparse, urlencode
import typing
from typing import Optional, Dict, Set, Any, Iterable
from enum import IntEnum

import requests
import unidecode

from .constants import (
    SERVER_TIMEOUT_ENV_KEY,
    DEFAULT_VARIANT_ENV_KEY,
    SITE_ID_ENV_KEY,
)
from .exceptions import UrlError

if typing.TYPE_CHECKING:
    from typing import Union
    from .typing import AnyEntityDict, StreamType

REMOVED_VALUE = object()
NOT_SET = object()
SLUGIFY_WHITELIST = string.ascii_letters + string.digits
SLUGIFY_SEP_WHITELIST = " ,./\\;:!|*^#@~+-_="

RepresentationParents = collections.namedtuple(
    "RepresentationParents",
    ("version", "product", "folder", "project")
)

RepresentationHierarchy = collections.namedtuple(
    "RepresentationHierarchy",
    (
        "project",
        "folder",
        "task",
        "product",
        "version",
        "representation",
    )
)


class SortOrder(IntEnum):
    """Sort order for GraphQl requests."""
    ascending = 0
    descending = 1

    @classmethod
    def parse_value(cls, value, default=None):
        if value in (cls.ascending, "ascending", "asc"):
            return cls.ascending
        if value in (cls.descending, "descending", "desc"):
            return cls.descending
        return default


def get_default_timeout() -> float:
    """Default value for requests timeout.

    First looks for environment variable SERVER_TIMEOUT_ENV_KEY which
    can affect timeout value. If not available then use 10.0 s.

    Returns:
        float: Timeout value in seconds.

    """
    try:
        return float(os.environ.get(SERVER_TIMEOUT_ENV_KEY))
    except (ValueError, TypeError):
        pass
    return 10.0


def get_default_settings_variant() -> str:
    """Default settings variant.

    Returns:
        str: Settings variant from environment variable or 'production'.

    """
    return os.environ.get(DEFAULT_VARIANT_ENV_KEY) or "production"


def get_default_site_id() -> Optional[str]:
    """Site id used for server connection.

    Returns:
        Optional[str]: Site id from environment variable or None.

    """
    return os.environ.get(SITE_ID_ENV_KEY)


class ThumbnailContent:
    """Wrapper for thumbnail content.

    Args:
        project_name (str): Project name.
        thumbnail_id (Optional[str]): Thumbnail id.
        content (Optional[bytes]): Thumbnail content.
        content_type (Optional[str]): Content type e.g. 'image/png'.

    """
    def __init__(
        self,
        project_name: str,
        thumbnail_id: Optional[str],
        content: Optional[bytes],
        content_type: Optional[str],
    ):
        self.project_name: str = project_name
        self.thumbnail_id: Optional[str] = thumbnail_id
        self.content_type: Optional[str] = content_type
        self.content: bytes = content or b""

    @property
    def id(self) -> str:
        """Wrapper for thumbnail id."""
        return self.thumbnail_id

    @property
    def is_valid(self) -> bool:
        """Content of thumbnail is valid.

        Returns:
            bool: Content is valid and can be used.

        """
        return (
            self.thumbnail_id is not None
            and self.content_type is not None
        )


def prepare_query_string(
    key_values: Dict[str, Any], skip_none: bool = True
) -> str:
    """Prepare data to query string.

    If there are any values a query starting with '?' is returned otherwise
    an empty string.

    Args:
         key_values (dict[str, Any]): Query values.
         skip_none (bool): Filter values which are 'None'.

    Returns:
        str: Query string.

    """
    if skip_none:
        key_values = {
            key: value
            for key, value in key_values.items()
            if value is not None
        }

    if not key_values:
        return ""
    return "?{}".format(urlencode(key_values))


def create_entity_id() -> str:
    return uuid.uuid1().hex


def convert_entity_id(entity_id) -> Optional[str]:
    if not entity_id:
        return None

    if isinstance(entity_id, uuid.UUID):
        return entity_id.hex

    try:
        return uuid.UUID(entity_id).hex

    except (TypeError, ValueError, AttributeError):
        pass
    return None


def convert_or_create_entity_id(entity_id: Optional[str] = None) -> str:
    output = convert_entity_id(entity_id)
    if output is None:
        output = create_entity_id()
    return output


def entity_data_json_default(value: Any) -> Any:
    if isinstance(value, datetime.datetime):
        return int(value.timestamp())

    raise TypeError(
        "Object of type {} is not JSON serializable".format(str(type(value)))
    )


def slugify_string(
    input_string: str,
    separator: Optional[str] = "_",
    slug_whitelist: Optional[Iterable[str]] = SLUGIFY_WHITELIST,
    split_chars: Optional[Iterable[str]] = SLUGIFY_SEP_WHITELIST,
    min_length: int = 1,
    lower: bool = False,
    make_set: bool = False,
) -> "Union[str, Set[str]]":
    """Slugify a text string.

    This function removes transliterates input string to ASCII, removes
    special characters and use join resulting elements using
    specified separator.

    Args:
        input_string (str): Input string to slugify
        separator (str): A string used to separate returned elements
            (default: "_")
        slug_whitelist (str): Characters allowed in the output
            (default: ascii letters, digits and the separator)
        split_chars (str): Set of characters used for word splitting
            (there is a sane default)
        lower (bool): Convert to lower-case (default: False)
        make_set (bool): Return "set" object instead of string.
        min_length (int): Minimal length of an element (word).

    Returns:
        Union[str, Set[str]]: Based on 'make_set' value returns slugified
            string.

    """
    tmp_string = unidecode.unidecode(input_string)
    if lower:
        tmp_string = tmp_string.lower()

    parts = [
        # Remove all characters that are not in whitelist
        re.sub("[^{}]".format(re.escape(slug_whitelist)), "", part)
        # Split text into part by split characters
        for part in re.split("[{}]".format(re.escape(split_chars)), tmp_string)
    ]
    # Filter text parts by length
    filtered_parts = [
        part
        for part in parts
        if len(part) >= min_length
    ]
    if make_set:
        return set(filtered_parts)
    return separator.join(filtered_parts)


def failed_json_default(value: Any) -> str:
    return "< Failed value {} > {}".format(type(value), str(value))


def prepare_attribute_changes(
    old_entity: "AnyEntityDict",
    new_entity: "AnyEntityDict",
    replace: int = False,
):
    attrib_changes = {}
    new_attrib = new_entity.get("attrib")
    old_attrib = old_entity.get("attrib")
    if new_attrib is None:
        if not replace:
            return attrib_changes
        new_attrib = {}

    if old_attrib is None:
        return new_attrib

    for attr, new_attr_value in new_attrib.items():
        old_attr_value = old_attrib.get(attr)
        if old_attr_value != new_attr_value:
            attrib_changes[attr] = new_attr_value

    if replace:
        for attr in old_attrib:
            if attr not in new_attrib:
                attrib_changes[attr] = REMOVED_VALUE

    return attrib_changes


def prepare_entity_changes(
    old_entity: "AnyEntityDict",
    new_entity: "AnyEntityDict",
    replace: bool = False,
) -> Dict[str, Any]:
    """Prepare changes of entities."""
    changes = {}
    for key, new_value in new_entity.items():
        if key == "attrib":
            continue

        old_value = old_entity.get(key)
        if old_value != new_value:
            changes[key] = new_value

    if replace:
        for key in old_entity:
            if key not in new_entity:
                changes[key] = REMOVED_VALUE

    attr_changes = prepare_attribute_changes(old_entity, new_entity, replace)
    if attr_changes:
        changes["attrib"] = attr_changes
    return changes


def _try_parse_url(url: str) -> Optional[str]:
    try:
        return urlparse(url)
    except BaseException:
        return None


def _try_connect_to_server(
    url: str,
    timeout: Optional[float],
    verify: Optional["Union[str, bool]"],
    cert: Optional[str],
) -> Optional[str]:
    if timeout is None:
        timeout = get_default_timeout()

    if verify is None:
        verify = os.environ.get("AYON_CA_FILE") or True

    if cert is None:
        cert = os.environ.get("AYON_CERT_FILE") or None

    try:
        # TODO add validation if the url lead to AYON server
        #   - this won't validate if the url lead to 'google.com'
        response = requests.get(
            url,
            timeout=timeout,
            verify=verify,
            cert=cert,
        )
        if response.history:
            return response.history[-1].headers["location"].rstrip("/")
        return url

    except Exception:
        print(f"Failed to connect to '{url}'")
        traceback.print_exc()

    return None


def login_to_server(
    url: str,
    username: str,
    password: str,
    timeout: Optional[float] = None,
) -> Optional[str]:
    """Use login to the server to receive token.

    Args:
        url (str): Server url.
        username (str): User's username.
        password (str): User's password.
        timeout (Optional[float]): Timeout for request. Value from
            'get_default_timeout' is used if not specified.

    Returns:
        Optional[str]: User's token if login was successfull.
            Otherwise 'None'.

    """
    if timeout is None:
        timeout = get_default_timeout()
    headers = {"Content-Type": "application/json"}
    response = requests.post(
        "{}/api/auth/login".format(url),
        headers=headers,
        json={
            "name": username,
            "password": password
        },
        timeout=timeout,
    )
    token = None
    # 200 - success
    # 401 - invalid credentials
    # *   - other issues
    if response.status_code == 200:
        token = response.json()["token"]
    return token


def logout_from_server(url: str, token: str, timeout: Optional[float] = None):
    """Logout from server and throw token away.

    Args:
        url (str): Url from which should be logged out.
        token (str): Token which should be used to log out.
        timeout (Optional[float]): Timeout for request. Value from
            'get_default_timeout' is used if not specified.

    """
    if timeout is None:
        timeout = get_default_timeout()
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer {}".format(token)
    }
    requests.post(
        url + "/api/auth/logout",
        headers=headers,
        timeout=timeout,
    )


def get_user_by_token(
    url: str,
    token: str,
    timeout: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Get user information by url and token.

    Args:
        url (str): Server url.
        token (str): User's token.
        timeout (Optional[float]): Timeout for request. Value from
            'get_default_timeout' is used if not specified.

    Returns:
        Optional[Dict[str, Any]]: User information if url and token are valid.

    """
    if timeout is None:
        timeout = get_default_timeout()

    base_headers = {
        "Content-Type": "application/json",
    }
    for header_value in (
        {"Authorization": "Bearer {}".format(token)},
        {"X-Api-Key": token},
    ):
        headers = base_headers.copy()
        headers.update(header_value)
        response = requests.get(
            "{}/api/users/me".format(url),
            headers=headers,
            timeout=timeout,
        )
        if response.status_code == 200:
            return response.json()
    return None


def is_token_valid(
    url: str,
    token: str,
    timeout: Optional[float] = None,
) -> bool:
    """Check if token is valid.

    Token can be a user token or service api key.

    Args:
        url (str): Server url.
        token (str): User's token.
        timeout (Optional[float]): Timeout for request. Value from
            'get_default_timeout' is used if not specified.

    Returns:
        bool: True if token is valid.

    """
    if get_user_by_token(url, token, timeout=timeout):
        return True
    return False


def validate_url(
    url: str,
    timeout: Optional[int] = None,
    verify: Optional["Union[str, bool]"] = None,
    cert: Optional[str] = None,
) -> str:
    """Validate url if is valid and server is available.

    Validation checks if can be parsed as url and contains scheme.

    Function will try to autofix url thus will return modified url when
    connection to server works.

    .. highlight:: python
    .. code-block:: python

        my_url = "my.server.url"
        try:
            # Store new url
            validated_url = validate_url(my_url)

        except UrlError:
            # Handle invalid url
            ...

    Args:
        url (str): Server url.
        timeout (Optional[int]): Timeout in seconds for connection to server.

    Returns:
        Url which was used to connect to server.

    Raises:
        UrlError: Error with short description and hints for user.

    """
    stripperd_url = url.strip()
    if not stripperd_url:
        raise UrlError(
            "Invalid url format. Url is empty.",
            title="Invalid url format",
            hints=["url seems to be empty"]
        )

    # Not sure if this is good idea?
    modified_url = stripperd_url.rstrip("/")
    parsed_url = _try_parse_url(modified_url)
    universal_hints = [
        "does the url work in browser?"
    ]
    if parsed_url is None:
        raise UrlError(
            "Invalid url format. Url cannot be parsed as url \"{}\".".format(
                modified_url
            ),
            title="Invalid url format",
            hints=universal_hints
        )

    # Try add 'https://' scheme if is missing
    # - this will trigger UrlError if both will crash
    if not parsed_url.scheme:
        new_url = _try_connect_to_server(
            "http://" + modified_url,
            timeout=timeout,
            verify=verify,
            cert=cert,
        )
        if new_url:
            return new_url

    new_url = _try_connect_to_server(
        modified_url,
        timeout=timeout,
        verify=verify,
        cert=cert,
    )
    if new_url:
        return new_url

    hints = []
    if "/" in parsed_url.path or not parsed_url.scheme:
        new_path = parsed_url.path.split("/")[0]
        if not parsed_url.scheme:
            new_path = "https://" + new_path

        hints.append(
            "did you mean \"{}\"?".format(parsed_url.scheme + new_path)
        )

    raise UrlError(
        "Couldn't connect to server on \"{}\"".format(url),
        title="Couldn't connect to server",
        hints=hints + universal_hints
    )


class TransferProgress:
    """Object to store progress of download/upload from/to server."""

    def __init__(self):
        self._started: bool = False
        self._transfer_done: bool = False
        self._transferred: int = 0
        self._content_size: Optional[int] = None

        self._failed: bool = False
        self._fail_reason: Optional[str] = None

        self._source_url: str = "N/A"
        self._destination_url: str = "N/A"

    def get_content_size(self):
        """Content size in bytes.

        Returns:
            Union[int, None]: Content size in bytes or None
                if is unknown.

        """
        return self._content_size

    def set_content_size(self, content_size: int):
        """Set content size in bytes.

        Args:
            content_size (int): Content size in bytes.

        Raises:
            ValueError: If content size was already set.

        """
        if self._content_size is not None:
            raise ValueError("Content size was set more then once")
        self._content_size = content_size

    def get_started(self) -> bool:
        """Transfer was started.

        Returns:
            bool: True if transfer started.

        """
        return self._started

    def set_started(self):
        """Mark that transfer started.

        Raises:
            ValueError: If transfer was already started.

        """
        if self._started:
            raise ValueError("Progress already started")
        self._started = True

    def get_transfer_done(self) -> bool:
        """Transfer finished.

        Returns:
            bool: Transfer finished.

        """
        return self._transfer_done

    def set_transfer_done(self):
        """Mark progress as transfer finished.

        Raises:
            ValueError: If progress was already marked as done
                or wasn't started yet.

        """
        if self._transfer_done:
            raise ValueError("Progress was already marked as done")
        if not self._started:
            raise ValueError("Progress didn't start yet")
        self._transfer_done = True

    def get_failed(self) -> bool:
        """Transfer failed.

        Returns:
            bool: True if transfer failed.

        """
        return self._failed

    def get_fail_reason(self) -> Optional[str]:
        """Get reason why transfer failed.

        Returns:
            Optional[str]: Reason why transfer
                failed or None.

        """
        return self._fail_reason

    def set_failed(self, reason: str):
        """Mark progress as failed.

        Args:
            reason (str): Reason why transfer failed.

        """
        self._fail_reason = reason
        self._failed = True

    def get_transferred_size(self) -> int:
        """Already transferred size in bytes.

        Returns:
            int: Already transferred size in bytes.

        """
        return self._transferred

    def set_transferred_size(self, transferred: int):
        """Set already transferred size in bytes.

        Args:
            transferred (int): Already transferred size in bytes.

        """
        self._transferred = transferred

    def add_transferred_chunk(self, chunk_size: int):
        """Add transferred chunk size in bytes.

        Args:
            chunk_size (int): Add transferred chunk size
                in bytes.

        """
        self._transferred += chunk_size

    def get_source_url(self) -> str:
        """Source url from where transfer happens.

        Note:
            Consider this as title. Must be set using
                'set_source_url' or 'N/A' will be returned.

        Returns:
            str: Source url from where transfer happens.

        """
        return self._source_url

    def set_source_url(self, url: str):
        """Set source url from where transfer happens.

        Args:
            url (str): Source url from where transfer happens.

        """
        self._source_url = url

    def get_destination_url(self) -> str:
        """Destination url where transfer happens.

        Note:
            Consider this as title. Must be set using
                'set_source_url' or 'N/A' will be returned.

        Returns:
            str: Destination url where transfer happens.

        """
        return self._destination_url

    def set_destination_url(self, url: str):
        """Set destination url where transfer happens.

        Args:
            url (str): Destination url where transfer happens.

        """
        self._destination_url = url

    @property
    def is_running(self) -> bool:
        """Check if transfer is running.

        Returns:
            bool: True if transfer is running.

        """
        if (
            not self.started
            or self.transfer_done
            or self.failed
        ):
            return False
        return True

    @property
    def transfer_progress(self) -> Optional[float]:
        """Get transfer progress in percents.

        Returns:
            Optional[float]: Transfer progress in percents or 'None'
                if content size is unknown.

        """
        if self._content_size is None:
            return None
        return (self._transferred * 100.0) / float(self._content_size)

    content_size = property(get_content_size, set_content_size)
    started = property(get_started)
    transfer_done = property(get_transfer_done)
    failed = property(get_failed)
    fail_reason = property(get_fail_reason)
    source_url = property(get_source_url, set_source_url)
    destination_url = property(get_destination_url, set_destination_url)
    transferred_size = property(get_transferred_size, set_transferred_size)


def create_dependency_package_basename(
    platform_name: Optional[str] = None
) -> str:
    """Create basename for dependency package file.

    Args:
        platform_name (Optional[str]): Name of platform for which the
            bundle is targeted. Default value is current platform.

    Returns:
        str: Dependency package name with timestamp and platform.

    """
    if platform_name is None:
        platform_name = platform.system().lower()

    now_date = datetime.datetime.now()
    time_stamp = now_date.strftime("%y%m%d%H%M")
    return "ayon_{}_{}".format(time_stamp, platform_name)



def _get_media_mime_type_from_ftyp(content: bytes) -> Optional[str]:
    if content[8:10] == b"qt" or content[8:12] == b"MSNV":
        return "video/quicktime"

    if content[8:12] in (b"3g2a", b"3g2b", b"3g2c", b"KDDI"):
        return "video/3gpp2"

    if content[8:12] in (
        b"isom", b"iso2", b"avc1", b"F4V", b"F4P", b"F4A", b"F4B", b"mmp4",
        # These might be "video/mp4v"
        b"mp41", b"mp42",
        # Nero
        b"NDSC", b"NDSH", b"NDSM", b"NDSP", b"NDSS", b"NDXC", b"NDXH",
        b"NDXM", b"NDXP", b"NDXS",
    ):
        return "video/mp4"

    if content[8:12] in (
        b"3ge6", b"3ge7", b"3gg6",
        b"3gp1", b"3gp2", b"3gp3", b"3gp4", b"3gp5", b"3gp6", b"3gs7",
    ):
        return "video/3gpp"

    if content[8:11] == b"JP2":
        return "image/jp2"

    if content[8:11] == b"jpm":
        return "image/jpm"

    if content[8:11] == b"jpx":
        return "image/jpx"

    if content[8:12] in (b"M4V\x20", b"M4VH", b"M4VP"):
        return "video/x-m4v"

    if content[8:12] in (b"mj2s", b"mjp2"):
        return "video/mj2"
    return None


def _get_media_mime_type_for_content_base(content: bytes) -> Optional[str]:
    """Determine Mime-Type of a file.

    Use header of the file to determine mime type (needs 12 bytes).
    """
    content_len = len(content)
    # Pre-validation (largest definition check)
    # - hopefully there cannot be media defined in less than 12 bytes
    if content_len < 12:
        return None

    # FTYP
    if content[4:8] == b"ftyp":
        return _get_media_mime_type_from_ftyp(content)

    # BMP
    if content[0:2] == b"BM":
        return "image/bmp"

    # Tiff
    if content[0:2] in (b"MM", b"II"):
        return "tiff"

    # PNG
    if content[0:4] == b"\211PNG":
        return "image/png"

    # JPEG
    # - [0:2] is constant b"\xff\xd8"
    #   (ref. https://www.file-recovery.com/jpg-signature-format.htm)
    # - [2:4] Marker identifier b"\xff{?}"
    #   (ref. https://www.disktuna.com/list-of-jpeg-markers/)
    # NOTE: File ends with b"\xff\xd9"
    if content[0:3] == b"\xff\xd8\xff":
        return "image/jpeg"

    # Webp
    if content[0:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"

    # Gif
    if content[0:6] in (b"GIF87a", b"GIF89a"):
        return "gif"

    # Adobe PhotoShop file (8B > Adobe, PS > PhotoShop)
    if content[0:4] == b"8BPS":
        return "image/vnd.adobe.photoshop"

    # Windows ICO > this might be wild guess as multiple files can start
    #   with this header
    if content[0:4] == b"\x00\x00\x01\x00":
        return "image/x-icon"
    return None


def _get_svg_mime_type(content: bytes) -> Optional[str]:
    # SVG
    if b'xmlns="http://www.w3.org/2000/svg"' in content:
        return "image/svg+xml"
    return None


def get_media_mime_type_for_content(content: bytes) -> Optional[str]:
    mime_type = _get_media_mime_type_for_content_base(content)
    if mime_type is not None:
        return mime_type
    return _get_svg_mime_type(content)


def get_media_mime_type_for_stream(stream: "StreamType") -> Optional[str]:
    # Read only 12 bytes to determine mime type
    content = stream.read(12)
    if len(content) < 12:
        return None
    mime_type = _get_media_mime_type_for_content_base(content)
    if mime_type is None:
        content += stream.read()
        mime_type = _get_svg_mime_type(content)
    return mime_type


def get_media_mime_type(filepath: str) -> Optional[str]:
    """Determine Mime-Type of a file.

    Args:
        filepath (str): Path to file.

    Returns:
        Optional[str]: Mime type or None if is unknown mime type.

    """
    if not filepath or not os.path.exists(filepath):
        return None

    with open(filepath, "rb") as stream:
        return get_media_mime_type_for_stream(stream)


def take_web_action_event(
    server_url: str,
    action_token: str
) -> Dict[str, Any]:
    """Take web action event using action token.

    Action token is generated by AYON server and passed to AYON launcher.

    Args:
        server_url (str): AYON server url.
        action_token (str): Action token.

    Returns:
        Dict[str, Any]: Web action event.

    """
    response = requests.get(
        f"{server_url}/api/actions/take/{action_token}"
    )
    response.raise_for_status()
    return response.json()


def abort_web_action_event(
    server_url: str,
    action_token: str,
    reason: str
) -> requests.Response:
    """Abort web action event using action token.

    A web action event could not be processed for some reason.

    Args:
        server_url (str): AYON server url.
        action_token (str): Action token.
        reason (str): Reason why webaction event was aborted.

    Returns:
        requests.Response: Response from server.

    """
    response = requests.post(
        f"{server_url}/api/actions/abort/{action_token}",
        json={"message": reason},
    )
    response.raise_for_status()
    return response
