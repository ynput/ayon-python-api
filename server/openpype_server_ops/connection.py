class OpenPypeServerConnection:
    def __init__(self, server_url):
        self._server_url = server_url

    def connect(self):
        pass

    def get_current_version_production(self):
        pass

    def get_current_version_staging(self):
        pass

    def need_updates(self):
        pass

    def update(self):
        pass

    def get_addon_names(self):
        pass

    def get_addon_versions(self, addon_names):
        pass

    def get_dependency_bundle_version(self):
        pass
