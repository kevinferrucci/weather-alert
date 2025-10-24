import requests
import logging
import asyncio
from datetime import datetime, timezone
from azure.cosmos.exceptions import CosmosResourceExistsError, CosmosHttpResponseError
from azfunc.helpers import (
    get_zone_to_users,
    get_user_emails,
    alert_check,
    get_active_alerts,
    send_messages_to_queue
)


def get_alerts():

    # Fetch active alerts from the NWS API
    try:
        all_alerts = get_active_alerts()
    except requests.RequestException as e:
        logging.error(f"Failed to fetch NWS alerts: {e}")
        return

    # Collect affected zone IDs
    affected_zone_ids = set()
    for alert in all_alerts:
        for zone in alert["properties"]["geocode"].get("UGC", []):
            affected_zone_ids.add(zone)
    if not affected_zone_ids:
        logging.info("No affected zones in current NWS alerts.")
        return

    # Query only the zone_id that are present in the NWS alerts
    try:
        zone_to_users = get_zone_to_users(list(affected_zone_ids))
        logging.info(f"All zone ids: {zone_to_users}")
    except Exception as e:
        logging.error(f"Failed to query zone subscriptions: {e}")
        return

    # Batch-query users' emails
    all_user_ids = set()
    for users in zone_to_users.values():
        for user in users:
            all_user_ids.add(user)
    try:
        user_email_list = get_user_emails(all_user_ids)
    except Exception as e:
        logging.error(f"Failed to query user emails: {e}")
        return

    """
    Loop through all alerts and find the users that are associated with that zone so they can be alerted
    Call service_bus_sender to send messages to queue
    """
    all_messages = []
    seen_alerts = set() # (alert_id, user_id)
    for alert in all_alerts:
        alert_properties = alert["properties"]
        alert_id = alert_properties.get("id")
        ugc = alert_properties.get("geocode", {}).get("UGC", [])

        for zone_id in ugc:
            users = zone_to_users.get(zone_id, [])
            if users:
                for user_id in users:
                    if (alert_id, user_id) in seen_alerts:
                        continue # already processed this user for this alert
                    seen_alerts.add((alert_id, user_id))

                    email = user_email_list.get(user_id)
                    if not email:
                        continue

                    alert_sent_details = {
                        "alert_id": alert_id,
                        "user_id": user_id,
                        "email": email,
                        "created_at": alert_properties.get("sent"),
                        "sent_at": datetime.now(timezone.utc).isoformat(),
                        "zone_id": zone_id,
                        "event": alert_properties.get("event"),
                        "link": alert_properties.get("web")
                    }

                    try:
                        alert_check(alert_sent_details)
                        all_messages.append({
                            "user_id": user_id,
                            "email": email,
                            "alert_id": alert_properties.get("id"),
                            "zone_id": zone_id,
                            "areaDesc": alert_properties.get("areaDesc"),
                            "created_at": alert_properties.get("sent"),
                            "effective_at": alert_properties.get("effective"),
                            "severity": alert_properties.get("severity"),
                            "certainty": alert_properties.get("certainty"),
                            "urgency": alert_properties.get("urgency"),
                            "event": alert_properties.get("event"),
                            "senderName": alert_properties.get("senderName"),
                            "headline": alert_properties.get("headline"),
                            "description": alert_properties.get("description"),
                            "instruction": alert_properties.get("instruction"),
                            "response": alert_properties.get("response"),
                            "link": alert_properties.get("web")
                        })
                    except CosmosResourceExistsError:
                        continue
                    except CosmosHttpResponseError as e:
                        logging.error(f"Cosmos DB error when processing alert {alert_id} for user {user_id}: {e}")
                        continue
                    except Exception as e:
                        logging.error(f"Unexpected error when processing alert {alert_id} for user {user_id}: {e}")
                        continue

    # Send messages to Service Bus
    if all_messages:
        try:
            asyncio.run(send_messages_to_queue(all_messages))
            logging.info(f"Queued {len(all_messages)} messages successfully.")
        except Exception as e:
            logging.error(f"Failed to queue messages: {e}")