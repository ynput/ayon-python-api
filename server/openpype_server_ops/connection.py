class OpenPypeServerConnection:
    """Connection to OpenPype server."""

    def __init__(self, server_url, staging):
        self._server_url = server_url
        self._staging = staging

    def connect(self):
        """Connect to server."""

        pass

    def close(self):
        """Close connection and cleanup.

        Method should pass if connection was already closed or was not created.
        """

        pass

    def get_current_production_version(self):
        """Get expected production version of OpenPype bundle."""

        pass

    def get_current_staging_version(self):
        """Get expected staging version of OpenPype bundle."""

        pass

    def get_dependency_bundle_version(self):
        """Get expected dependency bundle from server."""

        pass

    def need_updates(self):
        """Current application need updates.

        Based on production or staging state ask server what are expected
        versions of dependency budnle, OpenPype module and expected addons,
        and check their availablity on the machine.

        Probably split into more methods? (e.g. 'build_need_update',
        'addons_need_update', 'dependency_bundle_need_update', etc.)

        Returns:
            bool: True if any version is not the expected or addon is missing.
        """

        pass

    def update(self, staging):
        """Download required versions of OpenPype bundle and addons.

        Download and "install" updates in reasonable order.
        """

        pass

    def get_addon_names(self, staging):
        """Get name of addon python modules."""

        pass

    def get_addon_versions(self, addon_names):
        pass

    def get_addon_paths(self):
        """Paths to addon directories that should be added to 'sys.path'."""
        pass
