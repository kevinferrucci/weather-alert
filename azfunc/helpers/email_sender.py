import os
import logging
from html import escape
from azure.communication.email import EmailClient
from azure.core.exceptions import HttpResponseError

# ACS secret and sender email
ACS_CONNECTION_STRING = os.getenv("ACS_CONNECTION_STRING")
ACS_SENDER_EMAIL = os.getenv("ACS_SENDER_EMAIL")
email_client = EmailClient.from_connection_string(ACS_CONNECTION_STRING)


def format_text_for_html(text: str):

    if not text:
        return "No description provided."
    # Escape unsafe characters
    text = escape(text)
    # Replace double newlines with paragraph breaks
    text = text.replace("\n\n", "</p><p>")
    # Replace single newlines with line breaks
    text = text.replace("\n", "<br/>")
    return text


def format_email(alert: dict):

    subject = f"Weather Alert: {alert.get('event') or 'Unknown Event'}"

    plain_body = (
        f"{alert.get('event') or 'Unknown Event'}\n\n"
        f"Headline: {alert.get('headline') or 'No headline provided.'}\n"
        f"Area: {alert.get('areaDesc') or 'Unknown area'}\n"
        f"Severity: {alert.get('severity') or 'N/A'} | "
        f"Certainty: {alert.get('certainty') or 'N/A'} | "
        f"Urgency: {alert.get('urgency') or 'N/A'}\n\n"
        f"Description: {alert.get('description') or 'No description provided.'}\n\n"
        f"Instructions: {alert.get('instruction') or 'No instructions provided. Stay alert and follow official guidance.'}\n"
        f"Response: {alert.get('response') or 'Unknown'}\n\n"
        f"Source: {alert.get('senderName') or 'Unknown source'}\n"
        f"More info: {alert.get('link') or 'N/A'}\n\n"
    )

    html_body = f"""
        <html><body style='font-family: Arial, sans-serif; color: #333;'>
            <h2 style='color: #d9534f;'>{alert.get('event') or 'Unknown Event'}</h2>
            <h3>Headline</h3>
            <p>{alert.get('headline') or 'No headline provided.'}</p>
            <p><strong>Area:</strong> {alert.get('areaDesc') or 'Unknown area'}</p>
            <p><strong>Severity:</strong> {alert.get('severity') or 'N/A'} | 
                <strong>Certainty:</strong> {alert.get('certainty') or 'N/A'} | 
                <strong>Urgency:</strong> {alert.get('urgency') or 'N/A'}</p>
            <h3>Description</h3>
            <p>{format_text_for_html(alert.get('description'))}</p>
            <h3>Instructions</h3>
            <p>{format_text_for_html(alert.get('instruction') or 'No instructions provided. Stay alert and follow official guidance.')}</p>
            <p><strong>Response:</strong> {alert.get('response') or 'Unknown'}</p>
            <p><strong>Source:</strong> {alert.get('senderName') or 'Unknown source'}</p>
            <p><a href='{alert.get('link') or '#'}'>More Information</a></p>
        </body></html>
    """

    return subject, plain_body, html_body


def send_email_via_acs(to_email: str, subject: str, plain_body: str, html_body: str):

    message = {
        "senderAddress": ACS_SENDER_EMAIL,
        "recipients": {"to": [{"address": to_email}]},
        "content": {
            "subject": subject,
            "plainText": plain_body,
            "html": html_body
        }
    }

    try:
        poller = email_client.begin_send(message)
        logging.info(f"ACS email send status: {poller.result()['status']}")
    except HttpResponseError as e:
        logging.error(f"ACS error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")