"""
Security Middleware for FastAPI

Features:
- Rate limiting (token bucket algorithm, Redis-backed if available)
- CORS configuration
- Security headers
- IP blocking/whitelisting
"""

import ipaddress

from fastapi import Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from typing import Dict, Optional, List
from collections import defaultdict
from datetime import datetime, timedelta
import time

from loguru import logger


def _get_redis_client():
    """Try to connect to Redis. Returns client or None."""
    try:
        import redis
    except ImportError:
        return None
    try:
        from config.settings import settings
        client = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=1)
        client.ping()
        return client
    except (redis.RedisError, ConnectionError, OSError):
        return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using token bucket algorithm.
    Uses Redis if available (survives restarts, works with multiple workers).
    Falls back to in-memory if Redis is unavailable.
    """

    requests_per_minute: int = 1000
    burst_limit: int = 50

    def __init__(self, app, requests_per_minute: int = 1000):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute

        # Try Redis first
        self._redis = _get_redis_client()
        if self._redis:
            logger.info("Rate limiter: using Redis backend")
        else:
            logger.warning("Rate limiter: Redis unavailable, using in-memory (not suitable for multi-worker)")

        # In-memory fallback
        self.buckets: Dict[str, Dict] = defaultdict(lambda: {
            'tokens': requests_per_minute,
            'last_update': time.time()
        })

        # Specific limits for endpoints
        self.endpoint_limits = {
            '/api/v1/auth/login': 10,
            '/api/v1/auth/register': 5,
            '/api/v1/auth/demo-activate': 10,
        }

    async def dispatch(self, request: Request, call_next):
        # Get client IP
        client_ip = self._get_client_ip(request)

        # Check rate limit
        path = request.url.path
        limit = self.endpoint_limits.get(path, self.requests_per_minute)

        if not self._allow_request(client_ip, limit):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Please try again later.",
                    "retry_after": 60
                },
                headers={"Retry-After": "60"}
            )

        response = await call_next(request)
        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, trusting X-Forwarded-For only from internal proxies."""
        direct_ip = request.client.host if request.client else "unknown"
        try:
            addr = ipaddress.ip_address(direct_ip)
            if addr.is_private or addr.is_loopback:
                forwarded = request.headers.get("X-Forwarded-For")
                if forwarded:
                    return forwarded.split(",")[0].strip()
        except ValueError:
            pass
        return direct_ip

    def _allow_request(self, client_ip: str, limit: int) -> bool:
        """
        Token bucket algorithm for rate limiting.
        Uses Redis if available, falls back to in-memory.
        """
        if self._redis:
            return self._allow_request_redis(client_ip, limit)
        return self._allow_request_memory(client_ip, limit)

    def _allow_request_redis(self, client_ip: str, limit: int) -> bool:
        """Redis-backed sliding window rate limiter."""
        try:
            key = f"ratelimit:{client_ip}:{limit}"
            now = time.time()
            window = 60  # 1 minute

            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(key, 0, now - window)  # Remove expired entries
            pipe.zadd(key, {str(now): now})  # Add current request
            pipe.zcard(key)  # Count requests in window
            pipe.expire(key, window + 1)  # Auto-cleanup
            results = pipe.execute()

            count = results[2]
            return count <= limit
        except (ConnectionError, OSError, TimeoutError) as e:
            # Redis error — fallback to memory
            logger.warning(f"Rate limiter Redis error, falling back to memory: {e}")
            return self._allow_request_memory(client_ip, limit)

    def _allow_request_memory(self, client_ip: str, limit: int) -> bool:
        """In-memory token bucket (original implementation)."""
        bucket = self.buckets[client_ip]
        now = time.time()

        # Refill tokens based on time passed
        time_passed = now - bucket['last_update']
        bucket['tokens'] = min(
            limit,
            bucket['tokens'] + time_passed * (limit / 60)
        )
        bucket['last_update'] = now

        # Periodically clean up stale entries
        if len(self.buckets) > 1000:
            stale_threshold = now - 3600  # 1 hour
            stale_keys = [k for k, v in self.buckets.items() if v['last_update'] < stale_threshold]
            for k in stale_keys:
                del self.buckets[k]

        # Check if we have tokens
        if bucket['tokens'] >= 1:
            bucket['tokens'] -= 1
            return True

        return False


class IPFilterMiddleware(BaseHTTPMiddleware):
    """
    IP filtering middleware

    Features:
    - Blacklist: Block specific IPs
    - Whitelist: Allow only specific IPs (if enabled)
    """

    def __init__(
        self,
        app,
        blacklist: Optional[List[str]] = None,
        whitelist: Optional[List[str]] = None,
        whitelist_enabled: bool = False
    ):
        super().__init__(app)
        self.blacklist = set(blacklist or [])
        self.whitelist = set(whitelist or [])
        self.whitelist_enabled = whitelist_enabled

    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)

        # Check blacklist
        if client_ip in self.blacklist:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Access denied",
                    "message": "Your IP address has been blocked"
                }
            )

        # Check whitelist (if enabled)
        if self.whitelist_enabled and client_ip not in self.whitelist:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Access denied",
                    "message": "Your IP address is not authorized"
                }
            )

        response = await call_next(request)
        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request (only trust X-Forwarded-For behind reverse proxy)"""
        return request.client.host if request.client else "unknown"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Security headers middleware

    Adds security-related HTTP headers:
    - X-Content-Type-Options
    - X-Frame-Options
    - X-XSS-Protection
    - Strict-Transport-Security (HSTS)
    - Content-Security-Policy (CSP)
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' https: data:; "
            "connect-src 'self' ws: wss:; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'"
        )

        # Remove server header (security through obscurity)
        if "server" in response.headers:
            del response.headers["server"]

        return response


def setup_cors(app):
    """
    Setup CORS middleware

    Allows:
    - Specific origins (production domains)
    - Credentials (cookies, authorization headers)
    - Common HTTP methods
    - Common headers
    """
    from config.settings import settings

    allowed_origins = [
        "http://localhost:3000",  # Next.js frontend (dev)
        "http://localhost:8090",  # Nginx proxy (Docker)
    ]

    # Add production origins from settings if available
    if hasattr(settings, 'allowed_origins'):
        allowed_origins.extend(settings.allowed_origins)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept",
            "Origin",
            "User-Agent",
            "DNT",
            "Cache-Control",
            "X-Requested-With"
        ],
        expose_headers=["Content-Length", "X-Total-Count"],
        max_age=600,  # Cache preflight requests for 10 minutes
    )


def setup_security_middleware(app):
    """
    Setup all security middleware

    Call this in your FastAPI app initialization:

    ```python
    from fastapi import FastAPI
    from src.middleware.security import setup_security_middleware

    app = FastAPI()
    setup_security_middleware(app)
    ```
    """

    # CORS (must be first)
    setup_cors(app)

    # Rate limiting
    app.add_middleware(RateLimitMiddleware, requests_per_minute=1000)

    # Security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # IP filtering (optional - disabled by default)
    # app.add_middleware(
    #     IPFilterMiddleware,
    #     blacklist=["192.168.1.100"],  # Example
    #     whitelist_enabled=False
    # )

    return app
