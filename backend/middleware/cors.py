from fastapi.middleware.cors import CORSMiddleware
from backend.core.config import settings

class CORSMiddlewareConfig:
    def __init__(self, backend):
        self.backend = backend

    def apply_middleware(self):
        self.backend.add_middleware(
            CORSMiddleware,
            allow_origins = settings.ALLOWED_ORIGINS,
            allow_credentials = True,
            allow_methods = ["*"],
            allow_headers = ["*"],
        )