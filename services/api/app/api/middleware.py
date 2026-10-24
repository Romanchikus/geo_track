from starlette.types import ASGIApp, Receive, Scope, Send

from app.services.traffic import note_request


class RequestRateMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path") != "/health":
            note_request()
        await self.app(scope, receive, send)
