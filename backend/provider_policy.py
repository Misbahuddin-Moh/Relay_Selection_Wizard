"""Deny public provider operations independently of environment credentials.

Owner rule: future outbound payloads may contain engineering facts only.
See docs/PROVIDER_SECURITY.md before changing this gate.
"""
from fastapi.responses import JSONResponse

PROVIDER_PATHS = frozenset({
    "/api/protection-options", "/api/drawing/extract", "/api/requirements/extract",
})
DISABLED_REASON = "Provider operations disabled. Use manual entry and station checks."


async def deny_provider_requests(request, call_next):
    # Reject before reading request bodies or invoking route validation/providers.
    if request.url.path.rstrip("/") in PROVIDER_PATHS:
        return JSONResponse(status_code=403, content={"detail": DISABLED_REASON})
    return await call_next(request)
