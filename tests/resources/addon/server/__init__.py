from ayon_server.addons import BaseServerAddon
from ayon_server.api.dependencies import CurrentUser


class TestsAddon(BaseServerAddon):
    def initialize(self):
        self.add_endpoint(
            "test-get",
            self.get_test,
            method="GET",
        )

    async def get_test(
        self, user: CurrentUser,
    ):
        """Return a random folder from the database"""
        return {
            "success": True,
        }
