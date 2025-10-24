import logging
import os
import uuid
from datetime import datetime, timezone
from azure.cosmos import CosmosClient, PartitionKey, exceptions

# Azure secrets and endpoints
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
AZURE_KEY = os.getenv("AZURE_KEY")

# Initialize client and create DB
client = CosmosClient(AZURE_ENDPOINT, AZURE_KEY)
database = client.create_database_if_not_exists(id="weather_app_db")

# Set up containers
users_container = database.create_container_if_not_exists(
    id="users",
    partition_key=PartitionKey(path="/id")
)
zones_container = database.create_container_if_not_exists(
    id="zone_subscriptions",
    partition_key=PartitionKey(path="/id")
)
alerts_container = database.create_container_if_not_exists(
    id="sent_alerts",
    partition_key=PartitionKey(path="/alert_id")
)


# Create new user in the Cosmos DB container
def create_user(first_name, email, lat, lng, zone_ids):

    new_user = {
        "id": str(uuid.uuid4()),
        "first_name": first_name,
        "email": email,
        "lat": lat,
        "lng": lng,
        "zone_ids": zone_ids,
        "registered_at": datetime.now(timezone.utc).isoformat()
    }
    users_container.create_item(body=new_user)

    for zone_id in new_user["zone_ids"]:
        update_zone_subscriptions(zone_id, new_user["id"])


def update_zone_subscriptions(zone_id, user_id):

    try:
        zone_data = zones_container.read_item(item=zone_id, partition_key=zone_id)
        if user_id not in zone_data["user_ids"]:
            zone_data["user_ids"].append(user_id)
            zones_container.replace_item(item=zone_id, body=zone_data)
    except exceptions.CosmosResourceNotFoundError:
        zones_container.create_item({
            "id": zone_id,
            "user_ids": [user_id]
        })


# Query only the zone_id that are present in the NWS alerts to get a list of users and the zone ids that they are in
def get_zone_to_users(affected_zone_ids):

    query = """
        SELECT c.id, c.user_ids 
        FROM c 
        WHERE ARRAY_LENGTH(c.user_ids) > 0 
        AND ARRAY_CONTAINS(@affected_zone_ids, c.id)
    """
    params = [{"name": "@affected_zone_ids", "value": affected_zone_ids}]
    results = zones_container.query_items(
        query=query,
        parameters=params,
        enable_cross_partition_query=True
    )
    test = {i["id"]: i["user_ids"] for i in results}
    logging.info(f"Here's the list: {test}")
    return test


# Batch query users to get emails
def get_user_emails(all_user_ids):

    query = "SELECT c.id, c.email FROM c WHERE ARRAY_CONTAINS(@ids, c.id)"
    params = [{"name": "@ids", "value": list(all_user_ids)}]
    results = users_container.query_items(query=query, parameters=params, enable_cross_partition_query=True)
    return {user["id"]: user["email"] for user in results}


def alert_check(alert_details):

    doc_id = f"{alert_details["alert_id"]}-{alert_details["user_id"]}"
    alerts_container.create_item(body={
        "id": doc_id,
        "alert_id": alert_details["alert_id"],
        "user_id": alert_details["user_id"],
        "email": alert_details["email"],
        "created_at": alert_details["created_at"],
        "sent_at": alert_details["sent_at"],
        "zone_id": alert_details["zone_id"],
        "event": alert_details["event"],
        "link": alert_details["link"]
    })