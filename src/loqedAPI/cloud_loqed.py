import logging
import os
from aiohttp import ClientSession
from .loqed import AbstractAPIClient
from .urls import CLOUD_BASE_URL


logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))
_LOGGER = logging.getLogger(__name__)

class CloudAPIClient(AbstractAPIClient):
    def __init__(
        self,
        websession: ClientSession,
        token: str | None = None,
        cloud_base_url: str = CLOUD_BASE_URL,
    ):
        """Initialize the auth."""
        super().__init__(websession, cloud_base_url, token)


class LoqedCloudAPI:
    def __init__(self, apiclient: CloudAPIClient):
        self.apiclient = apiclient

    async def async_get_locks(self):
        _LOGGER.debug("About to obtain list of locks from cloud")
        
        resp = await self.apiclient.request("get", "api/locks/")
        
        _LOGGER.debug("Got response: HTTP %s: %s", resp.status, await resp.text())
        resp.raise_for_status()
        return await resp.json()
