
import pytest
from aioresponses import aioresponses
import aiohttp
from loqedAPI.cloud_loqed import LoqedCloudAPI, CloudAPIClient, CLOUD_BASE_URL

@pytest.mark.asyncio
async def test_loqedcloudapi_get_locks():
    with aioresponses() as m:
        url = f"{CLOUD_BASE_URL}/api/locks/"
        m.get(url, payload={"data": [{"id": "cloudlock1", "name": "Cloud Door"}]}, status=200)
        async with aiohttp.ClientSession() as session:
            client = CloudAPIClient(session, token="dummy-token")
            api = LoqedCloudAPI(client)
            locks = await api.async_get_locks()
            assert "data" in locks
            assert locks["data"][0]["id"] == "cloudlock1"
            assert locks["data"][0]["name"] == "Cloud Door"

@pytest.mark.asyncio
async def test_loqedcloudapi_custom_base_url():
    custom_base_url = "https://integrations.example.test"
    with aioresponses() as m:
        url = f"{custom_base_url}/api/locks/"
        m.get(url, payload={"data": [{"id": "cloudlock1"}]}, status=200)
        async with aiohttp.ClientSession() as session:
            client = CloudAPIClient(session, token="dummy-token", cloud_base_url=custom_base_url)
            api = LoqedCloudAPI(client)
            locks = await api.async_get_locks()
            assert locks["data"][0]["id"] == "cloudlock1"
