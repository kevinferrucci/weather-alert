from app import create_app
from flask import Flask
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
import os

app = create_app()

FlaskInstrumentor().instrument_app(app)

if __name__ == "__main__":
    app.run(debug=True)
