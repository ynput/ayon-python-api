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


class FailedOperations(Exception):
    pass