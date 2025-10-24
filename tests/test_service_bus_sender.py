import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock
from azfunc.helpers import service_bus_sender


"""Fixture that patches ServiceBusClient and returns (mock_client, mock_sender)."""
@pytest.fixture
def mock_servicebus():

    with patch("azfunc.helpers.service_bus_sender.ServiceBusClient.from_connection_string",
               new_callable=MagicMock) as mock_client_cls:
        mock_client = MagicMock()
        mock_sender = AsyncMock()

        # Make get_queue_sender return a fake sender
        mock_client.get_queue_sender.return_value = mock_sender

        # Teach the client to work as an async context manager
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_cls.return_value = mock_client

        # Same for sender (nested async context manager)
        mock_sender.__aenter__.return_value = mock_sender
        mock_sender.__aexit__.return_value = None

        yield mock_client, mock_sender


@pytest.mark.asyncio
async def test_send_messages_to_queue_calls_send_messages(mock_servicebus):

    mock_client, mock_sender = mock_servicebus
    messages = [{"id": 1}, {"id": 2}]

    await service_bus_sender.send_messages_to_queue(messages)

    assert mock_sender.send_messages.call_count == len(messages)


@pytest.mark.asyncio
async def test_send_messages_to_queue_payload_are_correct(mock_servicebus):

    mock_client, mock_sender = mock_servicebus
    messages = [{"id": 1}, {"id": 2}]

    await service_bus_sender.send_messages_to_queue(messages)

    sent_payloads = []
    for call_arg in mock_sender.send_messages.call_args_list:
        sb_msg = call_arg[0][0]
        body_bytes = b"".join(sb_msg.body)
        sent_payloads.append(json.loads(body_bytes.decode()))

    assert sent_payloads == messages


@pytest.mark.asyncio
async def test_send_messages_to_queue_empty_list(mock_servicebus):

    mock_client, mock_sender = mock_servicebus

    await service_bus_sender.send_messages_to_queue([])

    mock_sender.send_messages.assert_not_called()


@pytest.mark.asyncio
async def test_send_messages_to_queue_correct_queue_name(mock_servicebus):

    mock_client, mock_sender = mock_servicebus

    await service_bus_sender.send_messages_to_queue([{"id": 123}])

    mock_client.get_queue_sender.assert_called_once_with(queue_name=service_bus_sender.QUEUE_NAME)

