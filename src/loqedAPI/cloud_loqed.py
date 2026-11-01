import logging
import os
from urllib.parse import quote
from aiohttp import ClientSession
import aiohttp
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

    async def _async_setting_request(self, method: str, path: str, **kwargs):
        """Request a settings endpoint without following login redirects."""
        resp = await self.apiclient.request(
            method, path, headers={"Accept": "application/json"},
            allow_redirects=False, **kwargs
        )
        resp.raise_for_status()
        if 300 <= resp.status < 400:
            raise aiohttp.ClientResponseError(
                resp.request_info, resp.history, status=resp.status,
                message="Unexpected redirect from LOQED API",
            )
        return resp

    async def async_get_open_house_mode(self, lock_id: str) -> bool:
        """Return the reported Open House Mode for the selected lock."""
        resp = await self._async_setting_request("get", "api/locks/")
        data = await resp.json()
        for lock in data["data"]:
            if lock["id"] == lock_id:
                state = lock["guest_access_mode"]
                if not isinstance(state, bool):
                    raise ValueError("Invalid Open House Mode value")
                return state
        raise LookupError("Lock not found in LOQED account")

    async def async_set_open_house_mode(self, lock_id: str, enabled: bool) -> None:
        """Request a mode change; read the state separately to confirm it."""
        await self._async_setting_request(
            "post", f"api/locks/{quote(lock_id, safe='')}/setting",
            json={"setting_name": "open_house_mode", "setting_value": int(enabled)},
        )
