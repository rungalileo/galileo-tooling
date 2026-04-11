import os

GCP_PROJECT = os.environ.get("GCP_PROJECT", "rungalileo-dev")
GCP_REGION = os.environ.get("GCP_REGION", "us-west1")
JOB_NAME = os.environ.get("JOB_NAME", "astra-job")
BOT_USER = os.environ.get("BOT_USER", "galileo-astra[bot]")
