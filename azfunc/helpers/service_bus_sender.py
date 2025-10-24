import asyncio
import json
import os
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage

# Service bus secrets
NAMESPACE_CONNECTION_STR = os.getenv("NAMESPACE_CONNECTION_STR")
QUEUE_NAME = os.getenv("QUEUE_NAME")


async def send_messages_to_queue(messages):

    async with ServiceBusClient.from_connection_string(
            conn_str=NAMESPACE_CONNECTION_STR,
            logging_enable=True
    ) as servicebus_client:
        sender = servicebus_client.get_queue_sender(queue_name=QUEUE_NAME)
        async with sender:
            # Prepare messages as ServiceBusMessage objects
            sb_messages = [ServiceBusMessage(json.dumps(msg)) for msg in messages]
            # Send messages all at once
            await asyncio.gather(*[sender.send_messages(sb_msg) for sb_msg in sb_messages])
