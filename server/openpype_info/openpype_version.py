"""Logic related to OpenPype version resolving.

Semantic versioning logic (comparing of version strings). Getting information
about currently used build version and current zip version (if used).
"""
import sys
import semver


class OpenPypeVersion(semver.VersionInfo):
    """Class for storing information about OpenPype version.

    Attributes:
        version (str): Version string to parse.
    """

    def __init__(self, version, staging, *args, **kwargs):
        super(OpenPypeVersion, self).__init__(*args, **kwargs)
        self.version = version
        self.staging = staging

    @classmethod
    def from_string(cls, version):
        """Extends parse to handle ta handle staging variant."""

        parsed = semver.VersionInfo.parse(version)
        staging = parsed.build and "staging" in parsed.build
        return cls(
            version,
            staging,
            major=parsed.major,
            minor=parsed.minor,
            patch=parsed.patch,
            prerelease=parsed.prerelease,
            build=parsed.build
        )

    def __eq__(self, other):
        result = super(OpenPypeVersion, self).__eq__(other)
        return bool(result and self.staging == other.staging)

    def __repr__(self):
        return "<{}: {}>".format(self.__class__.__name__, str(self))
