import json
import logging
import azure.functions as func
from alert_worker import get_alerts
from helpers.email_sender import format_email, send_email_via_acs

app = func.FunctionApp()


@app.timer_trigger(schedule="0 */2 * * * *", arg_name="mytimer", run_on_startup=False,
              use_monitor=False)
def poll_alerts(mytimer: func.TimerRequest) -> None:
    
    logging.info("Timer trigger fired -> running get_alerts()")
    try:
        get_alerts()
        logging.info("get_alerts() completed successfully.")

    except Exception as e:
        logging.error(f"Error in get_alerts(): {e}", exc_info=True)


@app.service_bus_queue_trigger(arg_name="msg", queue_name="weather_alerts_queue", connection="ServiceBusConnection")
def send_emails(msg: func.ServiceBusMessage):
    logging.info('Python ServiceBus Queue trigger processed a message: %s', msg.get_body().decode('utf-8'))
    try:
        message_body = msg.get_body().decode('utf-8')
        alert_data = json.loads(message_body)
        subject, plain_body, html_body = format_email(alert_data)
        send_email_via_acs(
            to_email=alert_data["email"],
            subject=subject,
            plain_body=plain_body,
            html_body=html_body
        )
        logging.info(f"Processing email for {alert_data['email']}")
    except Exception as e:
        logging.error(f"Function error: {e}")
