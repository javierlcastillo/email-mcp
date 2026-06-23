import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class TokenAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path == "/health":
            return await call_next(request)

        auth_token = os.getenv("MCP_AUTH_TOKEN")
        if not auth_token:
            return Response("Server misconfigured: missing MCP_AUTH_TOKEN", status_code=500)

        token = request.headers.get("Authorization") or \
                f"Bearer {request.query_params.get('token', '')}"

        expected = f"Bearer {auth_token}"
        if token != expected:
            return Response("Unauthorized", status_code=401)
        return await call_next(request)
