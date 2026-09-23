from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, status
from fastapi.responses import JSONResponse
from backend.core.logging import logger

class ExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as e:
            logger.exception(f"Unhandled exception occured processing the request {request.method} {request.url.path}: {str(e)}")
            return JSONResponse(
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                content = {
                    "detail" : "An unexpected error occured on the server.",
                    "error": str(e)
                }
            )