import json
import logging
from typing import Any, Optional, Dict, List
from datetime import datetime, date

try:
    import redis
    from redis.exceptions import RedisError, ConnectionError, TimeoutError
except ImportError:
    redis = None
    RedisError = Exception
    ConnectionError = Exception
    TimeoutError = Exception

from app.core.config import settings

logger = logging.getLogger("datapulse.cache")

class JSONEncoderWithDates(json.JSONEncoder):
    """Custom JSON encoder handling datetime, date, and Pydantic model objects."""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
        return super().default(obj)

class CacheService:
    """
    Enterprise Redis caching service with:
    - Organization-scoped key namespacing (strict tenant isolation)
    - Circuit-breaker graceful degradation (transparent fallback to DB when Redis is unreachable)
    - SCAN-based non-blocking pattern invalidation
    - Telemetry tracking (hits, misses, hit rate, latency)
    - Anti-cache protection for sensitive credentials and authentication tokens
    """

    def __init__(self):
        self._client: Optional[Any] = None
        self._is_enabled: bool = settings.REDIS_ENABLED
        self._is_available: bool = False
        self._has_logged_failure: bool = False

        # Performance & Telemetry metrics
        self._hits: int = 0
        self._misses: int = 0
        self._writes: int = 0
        self._invalidations: int = 0
        self._errors: int = 0

        if self._is_enabled and redis is not None:
            self._init_client()

    def _init_client(self):
        """Initializes Redis connection pool with configured timeouts."""
        try:
            if settings.REDIS_URL:
                self._client = redis.Redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_timeout=settings.REDIS_TIMEOUT_SECONDS,
                    socket_connect_timeout=settings.REDIS_TIMEOUT_SECONDS,
                )
            else:
                self._client = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    password=settings.REDIS_PASSWORD or None,
                    db=settings.REDIS_DB,
                    decode_responses=True,
                    socket_timeout=settings.REDIS_TIMEOUT_SECONDS,
                    socket_connect_timeout=settings.REDIS_TIMEOUT_SECONDS,
                )
            # Test connectivity
            self._client.ping()
            self._is_available = True
            self._has_logged_failure = False
            logger.info("Connected to Redis cache server successfully.")
        except Exception as exc:
            self._is_available = False
            self._client = None
            if not self._has_logged_failure:
                logger.warning(f"Redis cache is unreachable ({exc}). Falling back to direct database queries.")
                self._has_logged_failure = True

    def set_client(self, client: Any):
        """Allows injecting a custom Redis or fakeredis client for automated testing."""
        self._client = client
        self._is_available = True
        self._is_enabled = True

    @property
    def is_connected(self) -> bool:
        """Checks if Redis client is ready and responsive."""
        if not self._is_enabled or not self._is_available or self._client is None:
            return False
        try:
            return bool(self._client.ping())
        except Exception:
            self._is_available = False
            return False

    # ── Key Building with Strict Multi-Tenancy ────────────────────────────────

    def build_key(self, org_id: str, resource_type: str, *parts: str) -> str:
        """
        Constructs an organization-scoped cache key.
        Format: {prefix}:{org_id}:{resource_type}:{part1}:{part2}...
        Example: datapulse:org_default_001:overview:summary
        """
        clean_parts = [str(p) for p in parts if p is not None and str(p) != ""]
        suffix = f":{':'.join(clean_parts)}" if clean_parts else ""
        return f"{settings.REDIS_KEY_PREFIX}:{org_id}:{resource_type}{suffix}"

    # ── Core Operations ───────────────────────────────────────────────────────

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieves and deserializes JSON value for key.
        Returns None on cache miss, connection error, or disabled cache.
        """
        if not self._is_enabled or not self._is_available or self._client is None:
            self._misses += 1
            return None

        # Disallow reading sensitive auth tokens or passwords from cache
        if any(sens in key.lower() for sens in ("password", "refresh_token", "secret", "jwt")):
            return None

        try:
            raw = self._client.get(key)
            if raw is None:
                self._misses += 1
                return None
            self._hits += 1
            return json.loads(raw)
        except (RedisError, ConnectionError, TimeoutError) as exc:
            self._errors += 1
            self._misses += 1
            self._is_available = False
            if not self._has_logged_failure:
                logger.warning(f"Redis get failed ({exc}); bypassing cache.")
                self._has_logged_failure = True
            return None
        except Exception as exc:
            self._errors += 1
            logger.error(f"Cache deserialization error for key '{key}': {exc}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Serializes and sets JSON value with optional TTL expiration in seconds.
        Returns True if stored, False on error or fallback.
        """
        if not self._is_enabled or not self._is_available or self._client is None:
            return False

        # Reject sensitive authentication data from being cached
        if any(sens in key.lower() for sens in ("password", "refresh_token", "secret", "jwt")):
            logger.warning(f"Rejected attempt to cache sensitive credential key '{key}'.")
            return False

        try:
            serialized = json.dumps(value, cls=JSONEncoderWithDates)
            if ttl is not None and ttl > 0:
                self._client.set(key, serialized, ex=ttl)
            else:
                self._client.set(key, serialized)
            self._writes += 1
            return True
        except (RedisError, ConnectionError, TimeoutError) as exc:
            self._errors += 1
            self._is_available = False
            if not self._has_logged_failure:
                logger.warning(f"Redis set failed ({exc}); continuing without cache.")
                self._has_logged_failure = True
            return False
        except Exception as exc:
            self._errors += 1
            logger.error(f"Cache serialization error for key '{key}': {exc}")
            return False

    def delete(self, key: str) -> bool:
        """Deletes a single cache key."""
        if not self._is_enabled or not self._is_available or self._client is None:
            return False
        try:
            res = bool(self._client.delete(key))
            self._invalidations += 1
            return res
        except (RedisError, ConnectionError, TimeoutError):
            self._errors += 1
            self._is_available = False
            return False

    def delete_pattern(self, pattern: str) -> int:
        """
        Safely scans and deletes keys matching pattern in batches without blocking Redis.
        Returns the count of deleted keys.
        """
        if not self._is_enabled or not self._is_available or self._client is None:
            return 0
        try:
            deleted_count = 0
            keys_to_delete = []
            for key in self._client.scan_iter(match=pattern, count=100):
                keys_to_delete.append(key)
                if len(keys_to_delete) >= 100:
                    self._client.delete(*keys_to_delete)
                    deleted_count += len(keys_to_delete)
                    keys_to_delete = []

            if keys_to_delete:
                self._client.delete(*keys_to_delete)
                deleted_count += len(keys_to_delete)

            self._invalidations += deleted_count
            return deleted_count
        except (RedisError, ConnectionError, TimeoutError):
            self._errors += 1
            self._is_available = False
            return 0

    # ── Safe Organization Invalidation Helpers ────────────────────────────────

    def invalidate_overview(self, org_id: str) -> int:
        """Invalidates overview summary cache for an organization."""
        key = self.build_key(org_id, "overview", "summary")
        return 1 if self.delete(key) else 0

    def invalidate_datasets(self, org_id: str, dataset_id: Optional[str] = None) -> int:
        """
        Invalidates dataset list cache and overview metrics for an organization.
        If dataset_id is given, also clears that specific dataset's detail cache.
        """
        count = 0
        # Invalidate dataset catalog lists
        pattern = self.build_key(org_id, "datasets", "list*")
        count += self.delete_pattern(pattern)

        if dataset_id:
            detail_key = self.build_key(org_id, "datasets", dataset_id, "detail")
            if self.delete(detail_key):
                count += 1

        # Overview counters change when datasets are modified
        count += self.invalidate_overview(org_id)
        return count

    def invalidate_pipelines(self, org_id: str, pipeline_id: Optional[str] = None) -> int:
        """
        Invalidates pipeline list cache and overview metrics for an organization.
        If pipeline_id is given, also clears that pipeline's details, metrics, and alerts.
        """
        count = 0
        # Invalidate pipeline lists
        pattern = self.build_key(org_id, "pipelines", "list*")
        count += self.delete_pattern(pattern)

        if pipeline_id:
            pipe_pattern = self.build_key(org_id, "pipelines", pipeline_id, "*")
            count += self.delete_pattern(pipe_pattern)

        # Overview counters change when pipelines are modified
        count += self.invalidate_overview(org_id)
        return count

    def invalidate_alerts(self, org_id: str, pipeline_id: Optional[str] = None) -> int:
        """Invalidates alerts cache for an organization and pipeline."""
        count = 0
        if pipeline_id:
            pattern = self.build_key(org_id, "pipelines", pipeline_id, "alerts*")
            count += self.delete_pattern(pattern)
        else:
            pattern = self.build_key(org_id, "pipelines", "*", "alerts*")
            count += self.delete_pattern(pattern)

        count += self.invalidate_overview(org_id)
        return count

    def invalidate_organization(self, org_id: str) -> int:
        """Invalidates all cached keys belonging strictly to one organization."""
        pattern = f"{settings.REDIS_KEY_PREFIX}:{org_id}:*"
        return self.delete_pattern(pattern)

    # ── Telemetry & Observability ─────────────────────────────────────────────

    def get_metrics(self) -> Dict[str, Any]:
        """Returns runtime caching telemetry for health audits and performance benchmarking."""
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100.0) if total_requests > 0 else 0.0
        return {
            "enabled": self._is_enabled,
            "connected": self.is_connected,
            "hits": self._hits,
            "misses": self._misses,
            "writes": self._writes,
            "invalidations": self._invalidations,
            "errors": self._errors,
            "total_requests": total_requests,
            "hit_rate_pct": round(hit_rate, 2),
        }

    def reset_metrics(self):
        """Resets telemetry metrics counters."""
        self._hits = 0
        self._misses = 0
        self._writes = 0
        self._invalidations = 0
        self._errors = 0

# Global CacheService Singleton
cache_service = CacheService()
