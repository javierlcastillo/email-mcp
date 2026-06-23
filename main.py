from dotenv import load_dotenv
load_dotenv()

import uvicorn
from starlette.middleware.trustedhost import TrustedHostMiddleware
from src.mcp.tools import mcp, health
from src.middleware.middleware import TokenAuthMiddleware

if __name__ == "__main__":
    app = mcp.sse_app()
    app.add_middleware(TokenAuthMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
    app.add_route("/health", health, methods=["GET"])
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        proxy_headers=True,
        forwarded_allow_ips="*"
    )
