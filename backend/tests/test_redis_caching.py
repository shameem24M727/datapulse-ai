import time
import json
import unittest
import fakeredis
from fastapi.testclient import TestClient

from app.main import app
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models.auth import OrganizationModel, UserModel, UserOrganizationModel
from app.models.pipeline import PipelineModel
from app.core.security import create_access_token, get_password_hash
from app.core.roles import UserRole
from app.services.cache_service import cache_service, CacheService
from tests.test_helpers import get_admin_headers

class TestRedisCaching(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.db = SessionLocal()

        # Seed two organizations for multi-tenancy verification
        cls.org_1 = cls.db.query(OrganizationModel).filter(OrganizationModel.slug == "cache-org-1").first()
        if not cls.org_1:
            cls.org_1 = OrganizationModel(name="Cache Org One", slug="cache-org-1", is_active=True)
            cls.db.add(cls.org_1)
            cls.db.commit()

        cls.org_2 = cls.db.query(OrganizationModel).filter(OrganizationModel.slug == "cache-org-2").first()
        if not cls.org_2:
            cls.org_2 = OrganizationModel(name="Cache Org Two", slug="cache-org-2", is_active=True)
            cls.db.add(cls.org_2)
            cls.db.commit()

        # Seed user for Org 1
        cls.user_1 = cls.db.query(UserModel).filter(UserModel.email == "cache_user_1@test.com").first()
        if not cls.user_1:
            cls.user_1 = UserModel(
                email="cache_user_1@test.com",
                hashed_password=get_password_hash("TestPass2026!"),
                full_name="Cache User One",
                role=UserRole.ADMIN.value,
                is_active=True,
            )
            cls.db.add(cls.user_1)
            cls.db.commit()
            cls.db.add(UserOrganizationModel(user_id=cls.user_1.id, organization_id=cls.org_1.id, role=UserRole.ADMIN.value))
            cls.db.commit()

        cls.token_1 = create_access_token({
            "sub": cls.user_1.id,
            "role": cls.user_1.role,
            "org_id": cls.org_1.id,
            "email": cls.user_1.email,
        })
        cls.client_1 = TestClient(app, headers={"Authorization": f"Bearer {cls.token_1}"})

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def setUp(self):
        # Attach fresh in-memory FakeRedis instance for each test
        self.fake_redis = fakeredis.FakeRedis(decode_responses=True)
        cache_service.set_client(self.fake_redis)
        cache_service.reset_metrics()

    # ── 1. Connection & FakeRedis Integration ────────────────────────────────

    def test_01_redis_connection_and_client_state(self):
        self.assertTrue(cache_service.is_connected)
        metrics = cache_service.get_metrics()
        self.assertTrue(metrics["enabled"])
        self.assertTrue(metrics["connected"])
        self.assertEqual(metrics["hits"], 0)
        self.assertEqual(metrics["misses"], 0)

    # ── 2. Cache Hits, Misses & Serialization ────────────────────────────────

    def test_02_cache_hits_and_misses(self):
        key = cache_service.build_key(self.org_1.id, "test", "metric")

        # 1. First get is a cache miss
        val_miss = cache_service.get(key)
        self.assertIsNone(val_miss)
        self.assertEqual(cache_service._misses, 1)
        self.assertEqual(cache_service._hits, 0)

        # 2. Store dictionary
        data_to_store = {
            "status": "healthy",
            "quality_score": 94.5,
            "columns": ["id", "timestamp", "amount"],
            "nested": {"active": True, "count": 42},
        }
        set_success = cache_service.set(key, data_to_store, ttl=60)
        self.assertTrue(set_success)
        self.assertEqual(cache_service._writes, 1)

        # 3. Second get is a cache hit
        val_hit = cache_service.get(key)
        self.assertIsNotNone(val_hit)
        self.assertEqual(val_hit["quality_score"], 94.5)
        self.assertEqual(val_hit["nested"]["count"], 42)
        self.assertEqual(cache_service._hits, 1)

        # 4. Telemetry hit rate check
        metrics = cache_service.get_metrics()
        self.assertEqual(metrics["total_requests"], 2)
        self.assertEqual(metrics["hit_rate_pct"], 50.0)

    # ── 3. TTL Expiration ────────────────────────────────────────────────────

    def test_03_ttl_expiration(self):
        key = cache_service.build_key(self.org_1.id, "test", "short_lived")
        # Store with 1 second TTL
        cache_service.set(key, {"value": "transient_data"}, ttl=1)

        # Immediate fetch -> present
        self.assertIsNotNone(cache_service.get(key))

        # Sleep past TTL
        time.sleep(1.2)

        # Fetch after TTL -> expired, returns None
        self.assertIsNone(cache_service.get(key))

    # ── 4. Multi-Tenant Organization Isolation ───────────────────────────────

    def test_04_organization_tenant_isolation(self):
        key_org1 = cache_service.build_key(self.org_1.id, "overview", "summary")
        key_org2 = cache_service.build_key(self.org_2.id, "overview", "summary")

        # Store distinct metrics per tenant
        cache_service.set(key_org1, {"org": "One", "datasets_count": 10}, ttl=60)
        cache_service.set(key_org2, {"org": "Two", "datasets_count": 99}, ttl=60)

        # Verify cross-tenant isolation: Org 1 gets only Org 1's data
        self.assertEqual(cache_service.get(key_org1)["datasets_count"], 10)
        self.assertEqual(cache_service.get(key_org2)["datasets_count"], 99)

        # Invalidate Org 1's cache
        cache_service.invalidate_overview(self.org_1.id)

        # Org 1's key must be purged, Org 2's key MUST remain intact
        self.assertIsNone(cache_service.get(key_org1))
        self.assertIsNotNone(cache_service.get(key_org2))
        self.assertEqual(cache_service.get(key_org2)["datasets_count"], 99)

    # ── 5. Security: Credential Anti-Caching ─────────────────────────────────

    def test_05_anti_cache_protection_for_sensitive_data(self):
        # Attempt to cache password or token
        sec_key = cache_service.build_key(self.org_1.id, "auth", "user_password_hash")
        res = cache_service.set(sec_key, {"password": "secret_bcrypt_hash"}, ttl=60)
        self.assertFalse(res)
        self.assertIsNone(cache_service.get(sec_key))

        token_key = cache_service.build_key(self.org_1.id, "auth", "refresh_token")
        res2 = cache_service.set(token_key, {"token": "jwt_secret_value"}, ttl=60)
        self.assertFalse(res2)
        self.assertIsNone(cache_service.get(token_key))

    # ── 6. Domain-Specific Invalidation Strategies ───────────────────────────

    def test_06_invalidation_patterns(self):
        # Setup multiple keys across resources
        k_ov = cache_service.build_key(self.org_1.id, "overview", "summary")
        k_ds_list = cache_service.build_key(self.org_1.id, "datasets", "list:skip=0:limit=50")
        k_ds_det = cache_service.build_key(self.org_1.id, "datasets", "ds-123", "detail")
        k_pl_list = cache_service.build_key(self.org_1.id, "pipelines", "list:status=active")
        k_pl_det = cache_service.build_key(self.org_1.id, "pipelines", "pipe-abc", "detail")

        cache_service.set(k_ov, {"summary": True}, ttl=60)
        cache_service.set(k_ds_list, [{"id": "ds-123"}], ttl=60)
        cache_service.set(k_ds_det, {"id": "ds-123", "score": 95}, ttl=60)
        cache_service.set(k_pl_list, [{"id": "pipe-abc"}], ttl=60)
        cache_service.set(k_pl_det, {"id": "pipe-abc", "status": "active"}, ttl=60)

        # Invalidate datasets: clears ds_list, ds_det, and overview
        cache_service.invalidate_datasets(self.org_1.id, "ds-123")
        self.assertIsNone(cache_service.get(k_ds_list))
        self.assertIsNone(cache_service.get(k_ds_det))
        self.assertIsNone(cache_service.get(k_ov))

        # Pipelines should still be cached
        self.assertIsNotNone(cache_service.get(k_pl_list))
        self.assertIsNotNone(cache_service.get(k_pl_det))

        # Invalidate pipelines: clears pl_list and pl_det
        cache_service.invalidate_pipelines(self.org_1.id, "pipe-abc")
        self.assertIsNone(cache_service.get(k_pl_list))
        self.assertIsNone(cache_service.get(k_pl_det))

    # ── 7. Graceful Fallback When Redis is Unavailable ───────────────────────

    def test_07_graceful_fallback_when_redis_offline(self):
        # 1. Break Redis connection to simulate network partition / server crash
        cache_service._client = None
        cache_service._is_available = False

        # 2. Get, Set, Delete must not throw exceptions
        self.assertIsNone(cache_service.get("any_key"))
        self.assertFalse(cache_service.set("any_key", {"data": 1}))
        self.assertFalse(cache_service.delete("any_key"))
        self.assertEqual(cache_service.delete_pattern("any*"), 0)

        # 3. HTTP Endpoints continue working seamlessly using DB queries
        res = self.client_1.get("/api/v1/overview/summary")
        self.assertEqual(res.status_code, 200)
        self.assertIn("average_quality_score", res.json())

        # Health endpoint reports fallback mode
        res_health = self.client_1.get("/api/v1/health/cache")
        self.assertEqual(res_health.status_code, 200)
        self.assertEqual(res_health.json()["status"], "fallback_mode")

    # ── 8. API End-to-End Caching & Automatic Invalidation ────────────────────

    def test_08_api_caching_and_invalidation_lifecycle(self):
        # 1. First call to overview summary: cache miss, cached
        cache_service.reset_metrics()
        res1 = self.client_1.get("/api/v1/overview/summary")
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(cache_service._misses, 1)
        self.assertEqual(cache_service._writes, 1)
        self.assertEqual(cache_service._hits, 0)

        # 2. Immediate second call: served from Redis (cache hit)
        res2 = self.client_1.get("/api/v1/overview/summary")
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res1.json(), res2.json())
        self.assertEqual(cache_service._hits, 1)

        # 3. Invalidate via mutation (e.g. creating pipeline)
        schema_def = {
            "fields": [{"name": "id", "type": "string", "required": True}],
            "strict": False,
        }
        res_create = self.client_1.post(
            "/api/v1/pipelines/",
            json={
                "name": "Cache Invalidation Trigger Stream",
                "source": "Kafka",
                "destination": "Postgres",
                "schema_definition": schema_def,
            },
        )
        self.assertEqual(res_create.status_code, 201)
        pipe_id = res_create.json()["id"]

        # 4. Third call to overview summary: must miss and refresh
        res3 = self.client_1.get("/api/v1/overview/summary")
        self.assertEqual(res3.status_code, 200)
        self.assertEqual(cache_service._misses, 2)

        # Clean up created pipeline
        self.client_1.delete(f"/api/v1/pipelines/{pipe_id}")

    # ── 9. Performance Benchmark: Redis vs Database Latency ──────────────────

    def test_09_performance_benchmark(self):
        """
        Benchmarks response times across repeated requests
        comparing un-cached DB execution vs cached Redis retrieval.
        """
        # Benchmark DB path (bypassing cache)
        cache_service._is_enabled = False
        db_times = []
        for _ in range(10):
            t0 = time.perf_counter()
            res = self.client_1.get("/api/v1/overview/summary")
            self.assertEqual(res.status_code, 200)
            db_times.append(time.perf_counter() - t0)

        avg_db_time_ms = (sum(db_times) / len(db_times)) * 1000.0

        # Benchmark Redis cache path
        cache_service._is_enabled = True
        cache_service.set_client(self.fake_redis)

        # Prime cache once
        self.client_1.get("/api/v1/overview/summary")

        cache_times = []
        for _ in range(10):
            t0 = time.perf_counter()
            res = self.client_1.get("/api/v1/overview/summary")
            self.assertEqual(res.status_code, 200)
            cache_times.append(time.perf_counter() - t0)

        avg_cache_time_ms = (sum(cache_times) / len(cache_times)) * 1000.0

        # Print measurements for report
        print(f"\n[PERFORMANCE BENCHMARK] Database Average Latency: {avg_db_time_ms:.2f} ms")
        print(f"[PERFORMANCE BENCHMARK] Redis Cache Average Latency: {avg_cache_time_ms:.2f} ms")
        speedup = (avg_db_time_ms / avg_cache_time_ms) if avg_cache_time_ms > 0 else 1.0
        print(f"[PERFORMANCE BENCHMARK] Speedup Factor: {speedup:.1f}x faster with Redis")

        self.assertGreater(speedup, 1.0, "Redis cache should deliver faster latency than DB query")

if __name__ == "__main__":
    unittest.main()
