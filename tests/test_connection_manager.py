
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.realtime.connection_manager import ConnectionManager


@pytest.mark.anyio
async def test_connect_adds_new_connection():
    manager = ConnectionManager()
    websocket = MagicMock()

    await manager.connect(1, websocket)

    assert websocket in manager.active_connections[1]


@pytest.mark.anyio
async def test_duplicate_connection_is_not_added_twice():
    manager = ConnectionManager()
    websocket = MagicMock()

    await manager.connect(1, websocket)
    await manager.connect(1, websocket)

    assert len(manager.active_connections[1]) == 1


@pytest.mark.anyio
async def test_disconnect_removes_connection_and_empty_user():
    manager = ConnectionManager()
    websocket = MagicMock()

    await manager.connect(1, websocket)
    manager.disconnect(1, websocket)

    assert 1 not in manager.active_connections


@pytest.mark.anyio
async def test_disconnect_does_not_remove_other_connections():
    manager = ConnectionManager()
    websocket1 = MagicMock()
    websocket2 = MagicMock()

    await manager.connect(1, websocket1)
    await manager.connect(1, websocket2)
    manager.disconnect(1, websocket1)

    assert websocket1 not in manager.active_connections[1]
    assert websocket2 in manager.active_connections[1]


@pytest.mark.anyio
async def test_personal_message_goes_only_to_selected_user():
    manager = ConnectionManager()
    user1_socket = MagicMock()
    user1_socket.send_json = AsyncMock()
    user2_socket = MagicMock()
    user2_socket.send_json = AsyncMock()

    await manager.connect(1, user1_socket)
    await manager.connect(2, user2_socket)

    message = {"type": "test", "payload": {"value": 123}}
    await manager.send_personal_message(message, 1)

    user1_socket.send_json.assert_awaited_once_with(message)
    user2_socket.send_json.assert_not_awaited()


@pytest.mark.anyio
async def test_broadcast_sends_to_all_connections():
    manager = ConnectionManager()
    websocket1 = MagicMock()
    websocket1.send_json = AsyncMock()
    websocket2 = MagicMock()
    websocket2.send_json = AsyncMock()

    await manager.connect(1, websocket1)
    await manager.connect(2, websocket2)

    message = {"type": "announcement"}
    await manager.broadcast(message)

    websocket1.send_json.assert_awaited_once_with(message)
    websocket2.send_json.assert_awaited_once_with(message)


@pytest.mark.anyio
async def test_failed_connection_does_not_block_other_clients():
    manager = ConnectionManager()
    failed_socket = MagicMock()
    failed_socket.send_json = AsyncMock(
        side_effect=RuntimeError("Connection failed")
    )
    working_socket = MagicMock()
    working_socket.send_json = AsyncMock()

    await manager.connect(1, failed_socket)
    await manager.connect(2, working_socket)

    message = {"type": "announcement"}
    await manager.broadcast(message)

    failed_socket.send_json.assert_awaited_once_with(message)
    working_socket.send_json.assert_awaited_once_with(message)
    assert 1 not in manager.active_connections
    assert 2 in manager.active_connections


@pytest.mark.anyio
async def test_disconnect_unknown_connection_is_safe():
    manager = ConnectionManager()
    websocket = MagicMock()

    manager.disconnect(999, websocket)

    assert manager.active_connections == {}

@pytest.mark.anyio
async def test_subscribe_to_match_registers_connection():
    manager = ConnectionManager()
    websocket = MagicMock()

    await manager.connect(1, websocket)
    manager.subscribe_to_match(10, websocket)

    assert websocket in manager.match_connections[10]


@pytest.mark.anyio
async def test_broadcast_to_match_only_reaches_subscribers():
    manager = ConnectionManager()

    match_10_socket = MagicMock()
    match_10_socket.send_json = AsyncMock()

    match_20_socket = MagicMock()
    match_20_socket.send_json = AsyncMock()

    await manager.connect(1, match_10_socket)
    await manager.connect(2, match_20_socket)

    manager.subscribe_to_match(10, match_10_socket)
    manager.subscribe_to_match(20, match_20_socket)

    message = {
        "type": "live_score:update",
        "payload": {"match_id": 10},
    }

    await manager.broadcast_to_match(10, message)

    match_10_socket.send_json.assert_awaited_once_with(message)
    match_20_socket.send_json.assert_not_awaited()


@pytest.mark.anyio
async def test_unsubscribe_from_match_stops_updates():
    manager = ConnectionManager()
    websocket = MagicMock()
    websocket.send_json = AsyncMock()

    await manager.connect(1, websocket)
    manager.subscribe_to_match(10, websocket)
    manager.unsubscribe_from_match(10, websocket)

    await manager.broadcast_to_match(
        10,
        {"type": "live_score:update", "payload": {"match_id": 10}},
    )

    websocket.send_json.assert_not_awaited()
    assert 10 not in manager.match_connections


@pytest.mark.anyio
async def test_disconnect_removes_match_subscriptions():
    manager = ConnectionManager()
    websocket = MagicMock()

    await manager.connect(1, websocket)
    manager.subscribe_to_match(10, websocket)
    manager.subscribe_to_match(20, websocket)

    manager.disconnect(1, websocket)

    assert 1 not in manager.active_connections
    assert 10 not in manager.match_connections
    assert 20 not in manager.match_connections