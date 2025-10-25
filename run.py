from app import create_app
from flask import Flask
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.azure.monitor.trace import AzureMonitorTraceExporter
import os

app = create_app()

FlaskInstrumentor().instrument_app(app)

if "APPLICATIONINSIGHTS_CONNECTION_STRING" in os.environ:
    provider = TracerProvider()
    exporter = AzureMonitorTraceExporter.from_connection_string(
        os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"]
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))

if __name__ == "__main__":
    app.run(debug=True)
