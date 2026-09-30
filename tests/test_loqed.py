import pytest
import pytest_asyncio
from aioresponses import aioresponses
import aiohttp
import base64
import time
import hashlib
import re
import types
from loqedAPI.loqed import Lock, LoqedAPI, APIClient, Action

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_base64():
    # 44 chars -> 33 bytes when decoded; sufficient for HMAC key
    return "U2VjcmV0U2VjcmV0U2VjcmV0U2VjcmV0U2VjcmV0U2VjcmU="

@pytest.fixture
def raw_data():
    return {
        "bolt_state": "locked",
        "battery_percentage": 90,
        "battery_type": "AA",
        "bridge_mac_wifi": "lockid",
        "wifi_strength": "good",
        "ble_strength": "strong",
        "battery_voltage": "3.7",
        "lock_online": 1,
    }

@pytest_asyncio.fixture
async def aiohttp_session():
    async with aiohttp.ClientSession() as session:
        yield session

@pytest.fixture
def base_url():
    return "http://dummy"

@pytest.fixture
def client(aiohttp_session, base_url):
    return APIClient(aiohttp_session, base_url)

@pytest.fixture
def lock(raw_data, valid_base64, client):
    return Lock(raw_data.copy(), valid_base64, valid_base64, 1, "TestLock", client)


# Helper to compute webhook hash
def compute_webhook_hash(body: str, timestamp: int, bridgekey_b64: str) -> str:
    return hashlib.sha256(
        body.encode() + timestamp.to_bytes(8, "big", signed=False) + base64.b64decode(bridgekey_b64)
    ).hexdigest()


# ---------------------------------------------------------------------------
# Command & property tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_lock_properties_and_commands(lock):
    # Monkeypatch underlying apiclient.request to avoid complex URL matching
    class DummyResp:
        status = 200
        async def text(self):
            return "OK"
        def raise_for_status(self):
            return None
    async def fake_request(self, method, url, **kwargs):
        return DummyResp()
    lock.apiclient.request = types.MethodType(fake_request, lock.apiclient)
    for action in (lock.open, lock.lock, lock.unlock):
        resp = await action()
        assert await resp.text() == "OK"
    assert lock.bolt_state == "locked"
    assert lock.battery_percentage == 90
    assert lock.battery_type == "AA"
    assert lock.id == "lockid"
    assert lock.wifi_strength == "good"
    assert lock.ble_strength == "strong"
    assert lock.online is True


@pytest.mark.asyncio
async def test_loqedapi_get_lock(valid_base64, raw_data, client):
    api = LoqedAPI(client)
    with aioresponses() as m:
        m.get(f"{client.host}/status", payload=raw_data, status=200, headers={"Content-Type": "text/html"})
        lock = await api.async_get_lock(valid_base64, valid_base64, 1, "TestLock")
    assert lock.name == "TestLock"
    assert lock.id == "lockid"
    assert lock.bolt_state == "locked"


@pytest.mark.asyncio
async def test_async_get_lock_details(client, raw_data):
    """LoqedAPI.async_get_lock_details should return the parsed JSON from /status"""
    api = LoqedAPI(client)
    with aioresponses() as m:
        m.get(f"{client.host}/status", payload=raw_data, status=200, headers={"Content-Type": "text/html"})
        result = await api.async_get_lock_details()
    assert result == raw_data


# ---------------------------------------------------------------------------
# receiveWebhook tests (no network activity required)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_lock_receive_webhook_state_update(lock, valid_base64):
    body = '{"battery_percentage": 80, "key_local_id": 1, "event_type": "STATE_CHANGED_NIGHT_LOCK"}'
    timestamp = int(time.time())
    hash_val = compute_webhook_hash(body, timestamp, valid_base64)
    await lock.receiveWebhook(body, hash_val, str(timestamp))
    assert lock.battery_percentage == 80


@pytest.mark.asyncio
async def test_lock_receive_webhook_invalid_hash(lock):
    body = '{"battery_percentage": 80, "key_local_id": 1, "event_type": "STATE_CHANGED_NIGHT_LOCK"}'
    timestamp = str(int(time.time()))
    bad_hash = "deadbeef" * 8
    result = await lock.receiveWebhook(body, bad_hash, timestamp)
    assert result["error"] == "Hash incorrect"


@pytest.mark.asyncio
async def test_lock_receive_webhook_invalid_timestamp(lock, valid_base64):
    body = '{"battery_percentage": 80, "key_local_id": 1, "event_type": "STATE_CHANGED_NIGHT_LOCK"}'
    old_timestamp = int(time.time()) - 1000
    hash_val = compute_webhook_hash(body, old_timestamp, valid_base64)
    result = await lock.receiveWebhook(body, hash_val, str(old_timestamp))
    assert result["error"] == "Timestamp incorrect, possible replaying"


@pytest.mark.asyncio
async def test_receive_webhook_empty_body(lock, valid_base64):
    timestamp = int(time.time())
    hash_val = compute_webhook_hash("", timestamp, valid_base64)
    result = await lock.receiveWebhook("", hash_val, str(timestamp))
    assert result["error"].startswith("Received invalid data from LOQED. Data needs to be formatted as JSON")


@pytest.mark.asyncio
async def test_receive_webhook_non_dict(lock, valid_base64):
    body = '"notadict"'
    timestamp = int(time.time())
    hash_val = compute_webhook_hash(body, timestamp, valid_base64)
    result = await lock.receiveWebhook(body, hash_val, str(timestamp))
    assert result["error"].endswith("be a dictionary")


@pytest.mark.asyncio
async def test_receive_webhook_unknown_event(lock, valid_base64):
    body = '{"key_local_id": 1, "event_type": "UNKNOWN_EVENT"}'
    timestamp = int(time.time())
    hash_val = compute_webhook_hash(body, timestamp, valid_base64)
    await lock.receiveWebhook(body, hash_val, str(timestamp))
    assert lock.last_event == "unknown_event"


@pytest.mark.asyncio
async def test_receive_webhook_ble_strength(lock, valid_base64):
    body = '{"ble_strength": "weak", "key_local_id": 2, "event_type": "STATE_CHANGED_LATCH"}'
    timestamp = int(time.time())
    hash_val = compute_webhook_hash(body, timestamp, valid_base64)
    await lock.receiveWebhook(body, hash_val, str(timestamp))
    assert lock.raw_data["ble_strength"] == "weak"


@pytest.mark.asyncio
async def test_online_falls_back_to_ble_strength(lock):
    del lock.raw_data["lock_online"]
    lock.raw_data["ble_strength"] = -1
    assert lock.online is False
    lock.raw_data["ble_strength"] = -60
    assert lock.online is True


@pytest.mark.asyncio
async def test_update_offline(lock, raw_data):
    with aioresponses() as m:
        offline = {**raw_data, "lock_online": 0, "battery_percentage": -1}
        m.get(f"{lock.apiclient.host}/status", payload=offline, status=200, headers={"Content-Type": "text/html"})
        await lock.update()
    assert lock.online is False


@pytest.mark.asyncio
async def test_receive_webhook_online_status(lock, valid_base64):
    timestamp = int(time.time())

    body = '{"ble_strength": -1, "wifi_strength": -50}'
    await lock.receiveWebhook(body, compute_webhook_hash(body, timestamp, valid_base64), str(timestamp))
    assert lock.online is False
    assert lock.raw_data["wifi_strength"] == -50

    body = '{"ble_strength": -60, "wifi_strength": -48}'
    await lock.receiveWebhook(body, compute_webhook_hash(body, timestamp, valid_base64), str(timestamp))
    assert lock.online is True
    assert lock.ble_strength == -60


@pytest.mark.asyncio
async def test_receive_webhook_battery_and_ble_strength(lock, valid_base64):
    body = '{"battery_percentage": 70, "ble_strength": -1}'
    timestamp = int(time.time())
    await lock.receiveWebhook(body, compute_webhook_hash(body, timestamp, valid_base64), str(timestamp))
    assert lock.battery_percentage == 70
    assert lock.online is False


@pytest.mark.asyncio
async def test_receive_webhook_bolt_state_change(lock, valid_base64):
    body = '{"key_local_id": 3, "event_type": "STATE_CHANGED_NIGHT_LOCK"}'
    timestamp = int(time.time())
    hash_val = compute_webhook_hash(body, timestamp, valid_base64)
    lock.bolt_state = "unlocked"
    await lock.receiveWebhook(body, hash_val, str(timestamp))
    assert lock.bolt_state == "night_lock"
    assert lock.last_event == "state_changed_night_lock"
    assert lock.last_key_id == 3


@pytest.mark.asyncio
async def test_receive_webhook_goto_state_night_lock(lock, valid_base64):
    body = '{"key_local_id": 4, "event_type": "GOTO_STATE_NIGHT_LOCK"}'
    timestamp = int(time.time())
    hash_val = compute_webhook_hash(body, timestamp, valid_base64)
    lock.bolt_state = "unlocked"
    await lock.receiveWebhook(body, hash_val, str(timestamp))
    assert lock.bolt_state == "locking"
    assert lock.last_event == "goto_state_night_lock"
    assert lock.last_key_id == 4


@pytest.mark.asyncio
async def test_receive_webhook_goto_state_open(lock, valid_base64):
    body = '{"key_local_id": 5, "event_type": "GOTO_STATE_OPEN"}'
    timestamp = int(time.time())
    hash_val = compute_webhook_hash(body, timestamp, valid_base64)
    lock.bolt_state = "locked"
    await lock.receiveWebhook(body, hash_val, str(timestamp))
    assert lock.bolt_state == "opening"
    assert lock.last_event == "goto_state_open"
    assert lock.last_key_id == 5


@pytest.mark.asyncio
async def test_receive_webhook_goto_state_latch(lock, valid_base64):
    body = '{"key_local_id": 6, "event_type": "GOTO_STATE_LATCH"}'
    timestamp = int(time.time())
    hash_val = compute_webhook_hash(body, timestamp, valid_base64)
    lock.bolt_state = "locked"
    await lock.receiveWebhook(body, hash_val, str(timestamp))
    assert lock.bolt_state == "unlocking"
    assert lock.last_event == "goto_state_latch"
    assert lock.last_key_id == 6


# ---------------------------------------------------------------------------
# Update & webhook management (network interactions via aioresponses)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_update(lock, raw_data):
    with aioresponses() as m:
        raw_data_updated = raw_data.copy()
        raw_data_updated["bolt_state"] = "locked"  # unchanged but explicit
        m.get(f"{lock.apiclient.host}/status", payload=raw_data_updated, status=200, headers={"Content-Type": "text/html"})
        result = await lock.update()
    assert result["bolt_state"] == "locked"
    assert lock.bolt_state == "locked"


@pytest.mark.asyncio
async def test_get_webhooks(lock):
    with aioresponses() as m:
        m.get(f"{lock.apiclient.host}/webhooks", payload=[{"url": "http://test.com"}], status=200, headers={"Content-Type": "text/html"})
        webhooks = await lock.getWebhooks()
    assert isinstance(webhooks, list)
    assert webhooks[0]["url"] == "http://test.com"


@pytest.mark.asyncio
async def test_register_webhook_created(lock):
    with aioresponses() as m:
        # First call returns no webhooks -> triggers creation
        m.get(f"{lock.apiclient.host}/webhooks", payload=[], status=200, headers={"Content-Type": "text/html"})
        m.post(f"{lock.apiclient.host}/webhooks", payload={}, status=200)
        result = await lock.registerWebhook("http://newwebhook.com")
    assert result == "CREATED"


@pytest.mark.asyncio
async def test_register_webhook_exists_already(lock):
    with aioresponses() as m:
        m.get(f"{lock.apiclient.host}/webhooks", payload=[{"url": "http://test.com"}], status=200, headers={"Content-Type": "text/html"})
        result = await lock.registerWebhook("http://test.com")
    assert result == "EXISTS ALREADY"


@pytest.mark.asyncio
async def test_delete_webhook(lock):
    with aioresponses() as m:
        m.delete(re.compile(rf"{re.escape(lock.apiclient.host)}/webhooks/\d+"), status=200, body="OK")
        await lock.deleteWebhook(123)


@pytest.mark.asyncio
async def test_update_state(lock):
    await lock.updateState("unlocked")
    assert lock.bolt_state == "unlocked"


# ---------------------------------------------------------------------------
# Additional: ensure command URL signature changes each call (basic sanity)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_command_signature_varies(lock, base_url):
    with aioresponses() as m:
        pattern = re.compile(rf"{re.escape(base_url)}/to_lock\?command_signed_base64=.*")
        m.get(pattern, status=200, body="OK")
        cmd1 = lock.getcommand(Action.OPEN)
        time.sleep(1)
        cmd2 = lock.getcommand(Action.OPEN)
        assert cmd1 != cmd2  # timestamp included makes them different
        # Execute one to ensure mocked endpoint matches
        await lock.open()

