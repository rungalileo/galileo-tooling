import logging

from fastapi import FastAPI

from astra_gateway.dispatch import router as dispatch_router
from astra_gateway.webhook import router as webhook_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(title="astra-gateway", docs_url=None, redoc_url=None)
app.include_router(webhook_router)
app.include_router(dispatch_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
