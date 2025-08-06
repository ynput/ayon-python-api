class _BaseServerAPI:
    def get_default_settings_variant(self) -> str:
        raise NotImplementedError()

    def get(self, entrypoint: str, **kwargs):
        pass

    def post(self, entrypoint: str, **kwargs):
        pass
