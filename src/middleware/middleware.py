import os
from starlette.requests import Request
from starlette.responses import Response


class TokenAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        if request.url.path == "/health" or request.url.path.startswith("/messages/"):
            await self.app(scope, receive, send)
            return

        auth_token = os.getenv("MCP_AUTH_TOKEN")
        if not auth_token:
            response = Response("Server misconfhoigured: missing MCP_AUTH_TOKEN", status_code=500)
            await response(scope, receive, send)
            return

        token = request.headers.get("Authorization") or \
                f"Bearer {request.query_params.get('token', '')}"

        if token != f"Bearer {auth_token}":
            response = Response("Unauthorized", status_code=401)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
