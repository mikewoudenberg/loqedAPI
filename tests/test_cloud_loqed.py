
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


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_open_house_mode_reads_selected_lock(enabled):
    with aioresponses() as mocked:
        mocked.get(f"{CLOUD_BASE_URL}/api/locks/", payload={"data": [
            {"id": "other", "guest_access_mode": not enabled},
            {"id": "target", "guest_access_mode": enabled},
        ]})
        async with aiohttp.ClientSession() as session:
            api = LoqedCloudAPI(CloudAPIClient(session, token="dummy-token"))
            assert await api.async_get_open_house_mode("target") is enabled


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_open_house_mode_setting(enabled):
    with aioresponses() as mocked:
        url = f"{CLOUD_BASE_URL}/api/locks/target/setting"
        mocked.post(url, status=204)
        async with aiohttp.ClientSession() as session:
            api = LoqedCloudAPI(CloudAPIClient(session, token="dummy-token"))
            await api.async_set_open_house_mode("target", enabled)
        request = mocked.requests[("post", aiohttp.client.URL(url))][0]
        assert request.kwargs["json"] == {"setting_name": "open_house_mode", "setting_value": int(enabled)}
        assert request.kwargs["headers"]["authorization"] == "Bearer dummy-token"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [302, 401, 500])
async def test_open_house_mode_rejects_errors_and_redirects(status):
    with aioresponses() as mocked:
        mocked.get(f"{CLOUD_BASE_URL}/api/locks/", status=status)
        async with aiohttp.ClientSession() as session:
            api = LoqedCloudAPI(CloudAPIClient(session, token="dummy-token"))
            with pytest.raises(aiohttp.ClientResponseError) as err:
                await api.async_get_open_house_mode("target")
        assert err.value.status == status


@pytest.mark.asyncio
@pytest.mark.parametrize("payload, error", [
    ({"data": []}, LookupError),
    ({"data": [{"id": "target", "guest_access_mode": "false"}]}, ValueError),
])
async def test_open_house_mode_rejects_invalid_state(payload, error):
    with aioresponses() as mocked:
        mocked.get(f"{CLOUD_BASE_URL}/api/locks/", payload=payload)
        async with aiohttp.ClientSession() as session:
            api = LoqedCloudAPI(CloudAPIClient(session, token="dummy-token"))
            with pytest.raises(error):
                await api.async_get_open_house_mode("target")
