from fastapi import Request
from fastapi.responses import JSONResponse
import traceback
from log.logging_config import logger

async def exception_handler(request: Request, exc: Exception):
    error_trace = traceback.format_exc()

    logger.error({
        "event": "exception",
        "error": str(exc),
        "traceback": error_trace,
        "url": str(request.url),
        "method": request.method
    })

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )
