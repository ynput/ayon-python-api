try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

import requests
import uuid


def create_entity_id():
    return uuid.uuid1().hex


class UrlError(Exception):
    """Url cannot be parsed as url.

    Exception may contain hints of possible fixes of url that can be used in
    UI if needed.
    """

    def __init__(self, message, title, hints=None):
        if hints is None:
            hints = []

        self.title = title
        self.hints = hints
        super(UrlError, self).__init__(message)


def _try_parse_url(url):
    try:
        return urlparse(url)
    except BaseException:
        return None


def _try_connect_to_server(url):
    try:
        # TODO add validation if the url lead to OpenPype server
        #   - thiw won't validate if the url lead to 'google.com'
        requests.get(url)

    except BaseException:
        return False
    return True


def login_to_server(url, username, password):
    """Use login to the server to receive token.

    Args:
        url (str): Server url.
        username (str): User's username.
        password (str): User's password.

    Returns:
        Union[str, None]: User's token if login was successfull.
            Otherwise 'None'.
    """

    headers = {"Content-Type": "application/json"}
    response = requests.post(
        "{}/api/auth/login".format(url),
        headers=headers,
        json={
            "name": username,
            "password": password
        }
    )
    token = None
    # 200 - success
    # 401 - invalid credentials
    # *   - other issues
    if response.status_code == 200:
        token = response.json()["token"]
    return token


def logout_from_server(url, token):
    """Logout from server and throw token away.

    Args:
        url (str): Url from which should be logged out.
        token (str): Token which should be used to log out.
    """

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer {}".format(token)
    }
    requests.post(
        url + "/api/auth/logout",
        headers=headers
    )


def is_token_valid(url, token):
    """Check if token is valid.

    Args:
        url (str): Server url.
        token (str): User's token.

    Returns:
        bool: True if token is valid.
    """

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer {}".format(token)
    }
    response = requests.get(
        "{}/api/users/me".format(url),
        headers=headers
    )
    return response.status_code == 200


def validate_url(url):
    """Validate url if is valid and server is available.

    Validation checks if can be parsed as url and contains scheme.

    Function will try to autofix url thus will return modified url when
    connection to server works.

    ```python
    my_url = "my.server.url"
    try:
        # Store new url
        validated_url = validate_url(my_url)

    except UrlError:
        # Handle invalid url
        ...
    ```

    Args:
        url (str): Server url.

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
        new_url = "https://" + modified_url
        if _try_connect_to_server(new_url):
            return new_url

    if _try_connect_to_server(modified_url):
        return modified_url

    hints = []
    if "/" in parsed_url.path or not parsed_url.scheme:
        new_path = parsed_url.path.split("/")[0]
        if not parsed_url.scheme:
            new_path = "https://" + new_path

        hints.append(
            "did you mean \"{}\"?".format(parsed_url.scheme + new_path)
        )

    raise UrlError(
        "Couldn't connect to server on \"{}\"".format(),
        title="Couldn't connect to server",
        hints=hints + universal_hints
    )
