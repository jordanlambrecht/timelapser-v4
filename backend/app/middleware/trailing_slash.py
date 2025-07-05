from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

# DISABLED AND NOT USED


class TrailingSlashRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Only apply to GET requests for API routes
        if request.method == "GET" and request.url.path.startswith("/api/"):
            path = request.url.path
            # Only add trailing slash if not present and not a file
            if not path.endswith("/") and "." not in path.split("/")[-1]:
                # Avoid double slashes before query string
                url_str = str(request.url)
                if url_str.endswith("/"):
                    redirect_url = url_str
                else:
                    # Insert slash before query string if present
                    if request.url.query:
                        redirect_url = url_str.replace("?", "/?")
                    else:
                        redirect_url = url_str + "/"
                return RedirectResponse(url=redirect_url)
        return await call_next(request)
