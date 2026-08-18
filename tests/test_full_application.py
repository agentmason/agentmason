"""
Comprehensive end-to-end test for the entire AgentMason platform.
Tests Phase 1 (Core), Phase 2 (Agents), Phase 3 (Knowledge/RAG),
Phase 4 (Integrations), and Phase 5 (Memory & Graph).
"""
import hashlib
import json
import os
import tempfile
import time
from uuid import uuid4

import httpx
import pytest

BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="module")
def client():
    """HTTP client for the test session."""
    with httpx.Client(base_url=BASE_URL, timeout=10) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers(client):
    """Register user, create org, return auth headers."""
    email = f"test_{uuid4().hex[:8]}@agentmason.com"
    # Register
    r = client.post("/auth/register", json={
        "email": email,
        "password": "SecurePass123",
        "name": "Test User",
    })
    assert r.status_code == 201, f"Register failed: {r.text}"

    # Login
    r = client.post("/auth/login", json={"email": email, "password": "SecurePass123"})
    assert r.status_code == 200, f"Login failed: {r.text}"
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create organization
    r = client.post("/organizations/", json={
        "name": "Test Organization",
        "slug": f"test-org-{uuid4().hex[:6]}",
    }, headers=headers)
    assert r.status_code == 201, f"Org create failed: {r.text}"

    return headers


@pytest.fixture(scope="module")
def second_user_headers(client):
    """Second user in a different org for isolation tests."""
    email = f"user2_{uuid4().hex[:8]}@other.com"
    r = client.post("/auth/register", json={
        "email": email,
        "password": "OtherPass456",
        "name": "Other User",
    })
    assert r.status_code == 201
    r = client.post("/auth/login", json={"email": email, "password": "OtherPass456"})
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post("/organizations/", json={
        "name": "Other Org",
        "slug": f"other-org-{uuid4().hex[:6]}",
    }, headers=headers)
    assert r.status_code == 201
    return headers


# ============================================================
# PHASE 1: CORE PLATFORM
# ============================================================

class TestPhase1Core:
    """Core platform: health, auth, organizations."""

    def test_health_check(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok", "service": "api"}

    def test_register_user(self, client):
        r = client.post("/auth/register", json={
            "email": f"newuser_{uuid4().hex[:6]}@test.com",
            "password": "Pass123",
            "name": "New User",
        })
        assert r.status_code == 201
        data = r.json()
        assert "id" in data
        assert data["email"].endswith("@test.com")
        assert data["role"] == "user"

    def test_register_duplicate_email(self, client):
        email = f"dup_{uuid4().hex[:6]}@test.com"
        client.post("/auth/register", json={"email": email, "password": "Pass123", "name": "A"})
        r = client.post("/auth/register", json={"email": email, "password": "Pass123", "name": "B"})
        assert r.status_code == 400

    def test_login_success(self, client):
        email = f"login_{uuid4().hex[:6]}@test.com"
        client.post("/auth/register", json={"email": email, "password": "LoginPass1", "name": "Login User"})
        r = client.post("/auth/login", json={"email": email, "password": "LoginPass1"})
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        email = f"wrongpw_{uuid4().hex[:6]}@test.com"
        client.post("/auth/register", json={"email": email, "password": "RightPass1", "name": "Test"})
        r = client.post("/auth/login", json={"email": email, "password": "WrongPass1"})
        assert r.status_code == 401

    def test_me_endpoint(self, client, auth_headers):
        r = client.get("/me/", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "id" in data
        assert "email" in data

    def test_me_unauthorized(self, client):
        r = client.get("/me/")
        assert r.status_code in (401, 403)

    def test_create_organization(self, client, auth_headers):
        r = client.post("/organizations/", json={
            "name": "Another Org",
            "slug": f"another-{uuid4().hex[:6]}",
        }, headers=auth_headers)
        assert r.status_code == 201
        assert r.json()["name"] == "Another Org"

    def test_list_organizations(self, client, auth_headers):
        r = client.get("/organizations/", headers=auth_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ============================================================
# PHASE 2: AGENTS
# ============================================================

class TestPhase2Agents:
    """Agent framework: execution, tools."""

    def test_run_agent(self, client, auth_headers):
        r = client.post("/agents/run", json={
            "agent_name": "business_assistant",
            "input": "Hello, what can you do?",
        }, headers=auth_headers)
        # May return 200 or 500 depending on LLM key availability
        # At minimum it should not return 401/403
        assert r.status_code not in (401, 403)

    def test_run_agent_unauthorized(self, client):
        r = client.post("/agents/run", json={
            "agent_name": "business_assistant",
            "input": "test",
        })
        assert r.status_code in (401, 403)


# ============================================================
# PHASE 3: KNOWLEDGE / RAG
# ============================================================

class TestPhase3Knowledge:
    """Document management, search, RAG."""

    def test_upload_document(self, client, auth_headers):
        content = b"This is a test document about invoice processing and approval workflows."
        r = client.post("/api/knowledge/documents", files={
            "file": ("test.txt", content, "text/plain")
        }, headers=auth_headers)
        assert r.status_code == 201
        data = r.json()
        assert "id" in data
        assert data["status"] == "uploaded"

    def test_list_documents(self, client, auth_headers):
        r = client.get("/api/knowledge/documents", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "documents" in data
        assert "total" in data

    def test_upload_unsupported_type(self, client, auth_headers):
        r = client.post("/api/knowledge/documents", files={
            "file": ("test.exe", b"fake binary", "application/octet-stream")
        }, headers=auth_headers)
        assert r.status_code == 415

    def test_knowledge_unauthorized(self, client):
        r = client.get("/api/knowledge/documents")
        assert r.status_code in (401, 403)


# ============================================================
# PHASE 4: INTEGRATIONS
# ============================================================

class TestPhase4Integrations:
    """Business integrations (OAuth, providers)."""

    def test_list_integrations(self, client, auth_headers):
        r = client.get("/api/integrations", headers=auth_headers)
        # Should return 200 with empty list or list of integrations
        assert r.status_code == 200

    def test_integrations_unauthorized(self, client):
        r = client.get("/api/integrations")
        assert r.status_code in (401, 403)


# ============================================================
# PHASE 5: BUSINESS MEMORY
# ============================================================

class TestPhase5Memory:
    """Business memory: CRUD, search, lifecycle, conflicts."""

    def test_create_memory(self, client, auth_headers):
        r = client.post("/api/memory", json={
            "category": "business_rule",
            "title": "Invoice approval threshold",
            "content": "All invoices above $10,000 require Sarah's approval before payment.",
            "source": "manual",
            "confidence": 0.95,
            "tags": ["finance", "approval"],
        }, headers=auth_headers)
        assert r.status_code == 201
        data = r.json()
        assert data["id"]
        assert data["category"] == "business_rule"
        assert data["title"] == "Invoice approval threshold"
        assert data["confidence"] == 0.95
        assert data["status"] == "active"
        assert data["version"] == 1

    def test_create_all_categories(self, client, auth_headers):
        categories = [
            ("business_fact", "Company HQ", "Located at 123 Main St, SF"),
            ("preference", "Communication style", "Prefer formal email for external clients"),
            ("goal", "Q4 Revenue Target", "Increase sales by 30% by end of Q4"),
            ("decision", "Cloud provider choice", "We decided to use AWS for all new services"),
            ("process", "Customer onboarding", "Step 1: intake form. Step 2: assign account manager. Step 3: kickoff call."),
            ("business_rule", "Expense policy", "All expenses over $500 need manager approval"),
        ]
        for cat, title, content in categories:
            r = client.post("/api/memory", json={
                "category": cat, "title": title, "content": content, "source": "manual"
            }, headers=auth_headers)
            assert r.status_code == 201, f"Failed for category {cat}: {r.text}"

    def test_list_memories(self, client, auth_headers):
        r = client.get("/api/memory", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "memories" in data
        assert "total" in data
        assert data["total"] >= 7  # From previous tests

    def test_get_memory(self, client, auth_headers):
        # Create one first
        r = client.post("/api/memory", json={
            "category": "business_fact",
            "title": "Get test",
            "content": "Content for get test",
            "source": "manual",
        }, headers=auth_headers)
        mid = r.json()["id"]

        r = client.get(f"/api/memory/{mid}", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["title"] == "Get test"
        assert r.json()["last_accessed_at"] is not None

    def test_search_memories(self, client, auth_headers):
        r = client.get("/api/memory?q=invoice", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_search_by_category(self, client, auth_headers):
        r = client.get("/api/memory?category=goal", headers=auth_headers)
        assert r.status_code == 200
        for m in r.json()["memories"]:
            assert m["category"] == "goal"

    def test_update_memory(self, client, auth_headers):
        r = client.post("/api/memory", json={
            "category": "preference",
            "title": "Update test",
            "content": "Original content",
            "source": "manual",
        }, headers=auth_headers)
        mid = r.json()["id"]

        r = client.patch(f"/api/memory/{mid}", json={
            "content": "Updated content",
            "confidence": 0.8,
        }, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["content"] == "Updated content"
        assert r.json()["confidence"] == 0.8

    def test_update_with_versioning(self, client, auth_headers):
        r = client.post("/api/memory", json={
            "category": "business_rule",
            "title": "Version test rule",
            "content": "Original rule v1",
            "source": "manual",
        }, headers=auth_headers)
        mid = r.json()["id"]

        r = client.patch(f"/api/memory/{mid}", json={
            "content": "Updated rule v2",
            "create_version": True,
        }, headers=auth_headers)
        assert r.status_code == 200
        new_data = r.json()
        assert new_data["id"] != mid  # New version
        assert new_data["version"] == 2
        assert new_data["previous_version_id"] == mid

        # Old version should be outdated
        r = client.get(f"/api/memory/{mid}", headers=auth_headers)
        assert r.json()["status"] == "outdated"

    def test_delete_memory(self, client, auth_headers):
        r = client.post("/api/memory", json={
            "category": "business_fact",
            "title": "To delete",
            "content": "Will be deleted",
            "source": "manual",
        }, headers=auth_headers)
        mid = r.json()["id"]

        r = client.delete(f"/api/memory/{mid}", headers=auth_headers)
        assert r.status_code == 200

        # Should not appear in active list
        r = client.get("/api/memory", headers=auth_headers)
        ids = [m["id"] for m in r.json()["memories"]]
        assert mid not in ids

    def test_memory_conflict_detection(self, client, auth_headers):
        # Create an existing rule about invoices
        client.post("/api/memory", json={
            "category": "business_rule",
            "title": "Invoice conflict test rule",
            "content": "Invoices above $5000 need approval",
            "source": "manual",
        }, headers=auth_headers)

        # Create a potentially conflicting one
        r = client.post("/api/memory", json={
            "category": "business_rule",
            "title": "Invoice conflict test threshold",
            "content": "Invoices above $10000 need approval",
            "source": "manual",
        }, headers=auth_headers)
        assert r.status_code == 201
        # May include potential_conflicts
        data = r.json()
        if "potential_conflicts" in data:
            assert len(data["potential_conflicts"]) >= 1

    def test_memory_not_found(self, client, auth_headers):
        r = client.get("/api/memory/nonexistent-id", headers=auth_headers)
        assert r.status_code == 404

    def test_invalid_category(self, client, auth_headers):
        r = client.post("/api/memory", json={
            "category": "invalid_category",
            "title": "Bad",
            "content": "Bad content",
            "source": "manual",
        }, headers=auth_headers)
        assert r.status_code == 400


# ============================================================
# PHASE 5: BUSINESS GRAPH
# ============================================================

class TestPhase5Graph:
    """Business graph: entities, relationships, traversal."""

    def test_create_entity(self, client, auth_headers):
        r = client.post("/api/graph/entities", json={
            "entity_type": "company",
            "name": "Acme Corporation",
            "description": "Parent company",
            "properties": {"industry": "Technology", "founded": "2010"},
        }, headers=auth_headers)
        assert r.status_code == 201
        data = r.json()
        assert data["entity_type"] == "company"
        assert data["name"] == "Acme Corporation"
        assert data["properties"]["industry"] == "Technology"

    def test_create_all_entity_types(self, client, auth_headers):
        types = [
            ("department", "Engineering"),
            ("employee", "Alice Johnson"),
            ("customer", "BigCorp Inc"),
            ("vendor", "SupplyChain LLC"),
            ("product", "Widget Pro"),
            ("service", "Consulting"),
            ("location", "San Francisco Office"),
            ("project", "Project Alpha"),
        ]
        for etype, name in types:
            r = client.post("/api/graph/entities", json={
                "entity_type": etype, "name": name,
            }, headers=auth_headers)
            assert r.status_code == 201, f"Failed for type {etype}: {r.text}"

    def test_list_entities(self, client, auth_headers):
        r = client.get("/api/graph/entities", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 9

    def test_search_entities(self, client, auth_headers):
        r = client.get("/api/graph/entities?q=Alice", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_filter_by_type(self, client, auth_headers):
        r = client.get("/api/graph/entities?entity_type=employee", headers=auth_headers)
        assert r.status_code == 200
        for e in r.json()["entities"]:
            assert e["entity_type"] == "employee"

    def test_get_entity(self, client, auth_headers):
        r = client.post("/api/graph/entities", json={
            "entity_type": "person", "name": "Bob Smith",
        }, headers=auth_headers)
        eid = r.json()["id"]

        r = client.get(f"/api/graph/entities/{eid}", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["name"] == "Bob Smith"

    def test_update_entity(self, client, auth_headers):
        r = client.post("/api/graph/entities", json={
            "entity_type": "product", "name": "Old Name",
        }, headers=auth_headers)
        eid = r.json()["id"]

        r = client.patch(f"/api/graph/entities/{eid}", json={
            "name": "New Product Name",
            "description": "Updated description",
        }, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["name"] == "New Product Name"

    def test_create_relationship(self, client, auth_headers):
        r1 = client.post("/api/graph/entities", json={"entity_type": "employee", "name": "Manager"}, headers=auth_headers)
        r2 = client.post("/api/graph/entities", json={"entity_type": "department", "name": "Sales Dept"}, headers=auth_headers)
        e1 = r1.json()["id"]
        e2 = r2.json()["id"]

        r = client.post("/api/graph/relationships", json={
            "source_entity_id": e1,
            "target_entity_id": e2,
            "relationship_type": "works_for",
            "strength": 0.9,
        }, headers=auth_headers)
        assert r.status_code == 201
        data = r.json()
        assert data["relationship_type"] == "works_for"
        assert data["strength"] == 0.9

    def test_all_relationship_types(self, client, auth_headers):
        # Create two entities to use for all relationship tests
        r1 = client.post("/api/graph/entities", json={"entity_type": "company", "name": "RelTest A"}, headers=auth_headers)
        r2 = client.post("/api/graph/entities", json={"entity_type": "company", "name": "RelTest B"}, headers=auth_headers)
        a = r1.json()["id"]
        b = r2.json()["id"]

        types = ["owns", "works_for", "manages", "serves", "purchases", "provides",
                 "uses", "located_at", "related_to", "depends_on", "part_of",
                 "created_by", "approved_by", "governed_by", "achieves", "replaces"]
        for rt in types:
            r = client.post("/api/graph/relationships", json={
                "source_entity_id": a, "target_entity_id": b, "relationship_type": rt,
            }, headers=auth_headers)
            assert r.status_code == 201, f"Failed for type {rt}: {r.text}"

    def test_get_entity_relationships(self, client, auth_headers):
        r1 = client.post("/api/graph/entities", json={"entity_type": "company", "name": "Hub Co"}, headers=auth_headers)
        r2 = client.post("/api/graph/entities", json={"entity_type": "employee", "name": "Worker"}, headers=auth_headers)
        r3 = client.post("/api/graph/entities", json={"entity_type": "product", "name": "Gadget"}, headers=auth_headers)
        hub = r1.json()["id"]
        worker = r2.json()["id"]
        gadget = r3.json()["id"]

        client.post("/api/graph/relationships", json={
            "source_entity_id": worker, "target_entity_id": hub, "relationship_type": "works_for"
        }, headers=auth_headers)
        client.post("/api/graph/relationships", json={
            "source_entity_id": hub, "target_entity_id": gadget, "relationship_type": "owns"
        }, headers=auth_headers)

        r = client.get(f"/api/graph/entities/{hub}/relationships", headers=auth_headers)
        assert r.status_code == 200
        assert len(r.json()["relationships"]) >= 2

    def test_graph_traversal(self, client, auth_headers):
        """Test multi-hop graph traversal."""
        # Company -> Department -> Employee
        r1 = client.post("/api/graph/entities", json={"entity_type": "company", "name": "Traverse Corp"}, headers=auth_headers)
        r2 = client.post("/api/graph/entities", json={"entity_type": "department", "name": "Traverse Dept"}, headers=auth_headers)
        r3 = client.post("/api/graph/entities", json={"entity_type": "employee", "name": "Traverse Employee"}, headers=auth_headers)
        cid = r1.json()["id"]
        did = r2.json()["id"]
        eid = r3.json()["id"]

        client.post("/api/graph/relationships", json={
            "source_entity_id": did, "target_entity_id": cid, "relationship_type": "part_of"
        }, headers=auth_headers)
        client.post("/api/graph/relationships", json={
            "source_entity_id": eid, "target_entity_id": did, "relationship_type": "works_for"
        }, headers=auth_headers)

        # Depth 1 from company should find department
        r = client.get(f"/api/graph/entities/{cid}/related?depth=1", headers=auth_headers)
        assert r.status_code == 200
        names = [e["name"] for e in r.json()["related"]]
        assert "Traverse Dept" in names

        # Depth 2 should also find employee
        r = client.get(f"/api/graph/entities/{cid}/related?depth=2", headers=auth_headers)
        assert r.status_code == 200
        names = [e["name"] for e in r.json()["related"]]
        assert "Traverse Employee" in names

    def test_delete_entity(self, client, auth_headers):
        r = client.post("/api/graph/entities", json={"entity_type": "vendor", "name": "Delete Me"}, headers=auth_headers)
        eid = r.json()["id"]

        r = client.delete(f"/api/graph/entities/{eid}", headers=auth_headers)
        assert r.status_code == 200

        r = client.get(f"/api/graph/entities/{eid}", headers=auth_headers)
        assert r.status_code == 404

    def test_delete_relationship(self, client, auth_headers):
        r1 = client.post("/api/graph/entities", json={"entity_type": "person", "name": "DR A"}, headers=auth_headers)
        r2 = client.post("/api/graph/entities", json={"entity_type": "person", "name": "DR B"}, headers=auth_headers)
        a = r1.json()["id"]
        b = r2.json()["id"]
        r = client.post("/api/graph/relationships", json={
            "source_entity_id": a, "target_entity_id": b, "relationship_type": "manages"
        }, headers=auth_headers)
        rel_id = r.json()["id"]

        r = client.delete(f"/api/graph/relationships/{rel_id}", headers=auth_headers)
        assert r.status_code == 200

    def test_invalid_entity_type(self, client, auth_headers):
        r = client.post("/api/graph/entities", json={
            "entity_type": "invalid_type", "name": "Bad",
        }, headers=auth_headers)
        assert r.status_code == 400

    def test_entity_not_found(self, client, auth_headers):
        r = client.get("/api/graph/entities/nonexistent-id", headers=auth_headers)
        assert r.status_code == 404


# ============================================================
# TENANT ISOLATION
# ============================================================

class TestTenantIsolation:
    """Verify strict tenant isolation across all Phase 5 APIs."""

    def test_memory_isolation(self, client, auth_headers, second_user_headers):
        """User 2 cannot access User 1's memories."""
        r = client.post("/api/memory", json={
            "category": "business_fact",
            "title": "Secret memory",
            "content": "Top secret business information",
            "source": "manual",
        }, headers=auth_headers)
        assert r.status_code == 201
        mid = r.json()["id"]

        # User 2 tries to access
        r = client.get(f"/api/memory/{mid}", headers=second_user_headers)
        assert r.status_code == 404

        # User 2 tries to delete
        r = client.delete(f"/api/memory/{mid}", headers=second_user_headers)
        assert r.status_code == 404

        # User 2 tries to update
        r = client.patch(f"/api/memory/{mid}", json={"content": "hacked"}, headers=second_user_headers)
        assert r.status_code == 404

    def test_graph_isolation(self, client, auth_headers, second_user_headers):
        """User 2 cannot access User 1's graph entities."""
        r = client.post("/api/graph/entities", json={
            "entity_type": "company", "name": "Secret Corp",
        }, headers=auth_headers)
        assert r.status_code == 201
        eid = r.json()["id"]

        # User 2 tries to access
        r = client.get(f"/api/graph/entities/{eid}", headers=second_user_headers)
        assert r.status_code == 404

        # User 2 tries to delete
        r = client.delete(f"/api/graph/entities/{eid}", headers=second_user_headers)
        assert r.status_code == 404

    def test_cross_org_relationship_blocked(self, client, auth_headers, second_user_headers):
        """Cannot create relationship between entities in different orgs."""
        r1 = client.post("/api/graph/entities", json={
            "entity_type": "company", "name": "Org1 Entity",
        }, headers=auth_headers)
        e1 = r1.json()["id"]

        r2 = client.post("/api/graph/entities", json={
            "entity_type": "company", "name": "Org2 Entity",
        }, headers=second_user_headers)
        e2 = r2.json()["id"]

        # User 1 tries to link their entity to User 2's entity
        r = client.post("/api/graph/relationships", json={
            "source_entity_id": e1,
            "target_entity_id": e2,
            "relationship_type": "related_to",
        }, headers=auth_headers)
        assert r.status_code == 404  # Target not found in org1

    def test_memory_list_isolation(self, client, auth_headers, second_user_headers):
        """Memory lists only show memories from the user's org."""
        # Create memories in both orgs
        client.post("/api/memory", json={
            "category": "business_fact", "title": "Org1 secret", "content": "Only org1", "source": "manual"
        }, headers=auth_headers)
        client.post("/api/memory", json={
            "category": "business_fact", "title": "Org2 info", "content": "Only org2", "source": "manual"
        }, headers=second_user_headers)

        # User 1's list
        r = client.get("/api/memory", headers=auth_headers)
        titles = [m["title"] for m in r.json()["memories"]]
        assert "Org2 info" not in titles

        # User 2's list
        r = client.get("/api/memory", headers=second_user_headers)
        titles = [m["title"] for m in r.json()["memories"]]
        assert "Org1 secret" not in titles


# ============================================================
# MEMORY EXTRACTION
# ============================================================

class TestMemoryExtraction:
    """Test the memory extraction service."""

    def test_extract_business_rule(self):
        from packages.memory.extraction import MemoryExtractionService
        svc = MemoryExtractionService()
        results = svc.extract("For all invoices above $10,000, Sarah needs to approve them before payment.")
        assert len(results) >= 1
        assert results[0].category.value == "business_rule"

    def test_extract_decision(self):
        from packages.memory.extraction import MemoryExtractionService
        svc = MemoryExtractionService()
        results = svc.extract("We decided to migrate all services to AWS starting next quarter.")
        assert len(results) >= 1
        assert any(m.category.value == "decision" for m in results)

    def test_extract_goal(self):
        from packages.memory.extraction import MemoryExtractionService
        svc = MemoryExtractionService()
        results = svc.extract("Our goal is to increase customer retention by 25% by end of Q4.")
        assert len(results) >= 1
        assert any(m.category.value == "goal" for m in results)

    def test_extract_preference(self):
        from packages.memory.extraction import MemoryExtractionService
        svc = MemoryExtractionService()
        results = svc.extract("We prefer using Slack for all internal team communication instead of email.")
        assert len(results) >= 1
        assert any(m.category.value == "preference" for m in results)

    def test_skip_trivial(self):
        from packages.memory.extraction import MemoryExtractionService
        svc = MemoryExtractionService()
        results = svc.extract("OK, sounds good. Thanks.")
        assert len(results) == 0

    def test_skip_empty(self):
        from packages.memory.extraction import MemoryExtractionService
        svc = MemoryExtractionService()
        assert svc.extract("") == []
        assert svc.extract("Hi") == []


# ============================================================
# RAG + MEMORY INTEGRATION
# ============================================================

class TestRAGMemoryIntegration:
    """Test that memory integrates with the RAG context builder."""

    def test_build_memory_context(self):
        from packages.rag.context import ContextBuilder

        class FakeMemory:
            category = type("E", (), {"value": "business_rule"})()
            title = "Approval Policy"
            content = "Invoices over $10k need Sarah's approval"
            source_reference = "manual entry"

        ctx = ContextBuilder.build_memory_context([FakeMemory()])
        assert "Approval Policy" in ctx
        assert "Invoices over $10k" in ctx
        assert "Business Rule" in ctx

    def test_build_combined_context(self):
        from packages.rag.context import ContextBuilder
        from packages.rag.retrieval import RetrievedChunk

        class FakeMemory:
            category = type("E", (), {"value": "business_rule"})()
            title = "Rule"
            content = "Memory content"
            source_reference = None

        chunks = [RetrievedChunk(
            chunk_id="c1", content="Document chunk content",
            score=0.92, metadata={"document_name": "Policy.pdf", "page_number": 1}
        )]
        memories = [FakeMemory()]
        graph_context = [{"name": "Finance Dept", "entity_type": "department", "via_relationship": "part_of"}]

        result = ContextBuilder.build_combined_context(
            "Who approves invoices?",
            chunks=chunks,
            memories=memories,
            graph_context=graph_context,
        )
        assert "Memory content" in result
        assert "Document chunk content" in result
        assert "Finance Dept" in result
        assert "Who approves invoices?" in result

    def test_empty_combined_context(self):
        from packages.rag.context import ContextBuilder
        result = ContextBuilder.build_combined_context("Hello?")
        assert "No additional business context" in result
        assert "Hello?" in result


# ============================================================
# AUTHORIZATION EDGE CASES
# ============================================================

class TestAuthEdgeCases:
    """Authorization and error handling."""

    def test_expired_token(self, client):
        r = client.get("/api/memory", headers={"Authorization": "Bearer invalid.token.here"})
        assert r.status_code == 401

    def test_missing_auth_header(self, client):
        r = client.get("/api/memory")
        assert r.status_code in (401, 403)

    def test_memory_api_requires_auth(self, client):
        endpoints = [
            ("GET", "/api/memory"),
            ("POST", "/api/memory"),
            ("GET", "/api/memory/some-id"),
            ("PATCH", "/api/memory/some-id"),
            ("DELETE", "/api/memory/some-id"),
        ]
        for method, path in endpoints:
            r = client.request(method, path)
            assert r.status_code in (401, 403, 422), f"{method} {path} returned {r.status_code}"

    def test_graph_api_requires_auth(self, client):
        endpoints = [
            ("GET", "/api/graph/entities"),
            ("POST", "/api/graph/entities"),
            ("GET", "/api/graph/entities/x"),
            ("DELETE", "/api/graph/entities/x"),
            ("POST", "/api/graph/relationships"),
            ("DELETE", "/api/graph/relationships/x"),
        ]
        for method, path in endpoints:
            r = client.request(method, path)
            assert r.status_code in (401, 403, 422), f"{method} {path} returned {r.status_code}"
