"""Tests for Phase 5: Business Memory & Business Graph."""

import pytest
from uuid import uuid4
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from apps.api.app.main import app
from apps.api.app.core.database import get_db, SessionLocal
from apps.api.app.models.memory import BusinessMemory, MemoryCategory, MemorySource, MemoryStatus
from apps.api.app.models.graph import GraphEntity, GraphRelationship, EntityType, RelationshipType
from packages.memory.service import MemoryService
from packages.memory.extraction import MemoryExtractionService
from packages.graph.service import GraphService


# --- Helpers ---

def get_test_client():
    return TestClient(app)


def register_and_login(client: TestClient, email: str = None) -> tuple[str, str]:
    """Register a user, create an org, and return (token, org_id)."""
    email = email or f"test_{uuid4().hex[:8]}@example.com"
    # Register
    client.post("/auth/register", json={
        "email": email,
        "password": "TestPass123!",
        "name": "Test User",
    })
    # Login
    login_res = client.post("/auth/login", json={
        "email": email,
        "password": "TestPass123!",
    })
    token = login_res.json()["access_token"]

    # Create org
    org_res = client.post("/organizations", json={
        "name": "Test Org",
        "slug": f"test-org-{uuid4().hex[:6]}",
    }, headers={"Authorization": f"Bearer {token}"})

    org_id = org_res.json().get("id", "")
    return token, org_id


# === MEMORY SERVICE UNIT TESTS ===

class TestMemoryService:
    def setup_method(self):
        self.db = SessionLocal()
        self.org_id = str(uuid4())
        self.service = MemoryService(self.db)

    def teardown_method(self):
        # Clean up test data
        self.db.rollback()
        self.db.close()

    def test_create_memory(self):
        memory = self.service.create(
            self.org_id,
            MemoryCategory.BUSINESS_FACT,
            "Company Name",
            "Our company is Acme Corp.",
            MemorySource.MANUAL,
        )
        assert memory.id is not None
        assert memory.title == "Company Name"
        assert memory.category == MemoryCategory.BUSINESS_FACT
        assert memory.status == MemoryStatus.ACTIVE
        assert memory.version == 1

    def test_get_memory(self):
        memory = self.service.create(
            self.org_id,
            MemoryCategory.PREFERENCE,
            "Preferred Vendor",
            "We prefer using Vendor X for office supplies.",
            MemorySource.MANUAL,
        )
        retrieved = self.service.get(memory.id, self.org_id)
        assert retrieved is not None
        assert retrieved.id == memory.id
        assert retrieved.last_accessed_at is not None

    def test_get_memory_wrong_org(self):
        """Tenant isolation: cannot access memory from another org."""
        memory = self.service.create(
            self.org_id,
            MemoryCategory.BUSINESS_FACT,
            "Secret",
            "Secret content",
            MemorySource.MANUAL,
        )
        other_org = str(uuid4())
        retrieved = self.service.get(memory.id, other_org)
        assert retrieved is None

    def test_search_memories(self):
        self.service.create(self.org_id, MemoryCategory.BUSINESS_FACT, "Product A", "Widget", MemorySource.MANUAL)
        self.service.create(self.org_id, MemoryCategory.GOAL, "Grow Sales", "Increase by 20%", MemorySource.MANUAL)

        results, total = self.service.search(self.org_id, query="Widget")
        assert total >= 1
        assert any("Widget" in m.content for m in results)

    def test_search_by_category(self):
        self.service.create(self.org_id, MemoryCategory.GOAL, "Goal 1", "Content", MemorySource.MANUAL)
        self.service.create(self.org_id, MemoryCategory.BUSINESS_FACT, "Fact 1", "Content", MemorySource.MANUAL)

        results, _ = self.service.search(self.org_id, category=MemoryCategory.GOAL)
        assert all(m.category == MemoryCategory.GOAL for m in results)

    def test_update_memory(self):
        memory = self.service.create(
            self.org_id, MemoryCategory.BUSINESS_FACT, "Old Title", "Old Content", MemorySource.MANUAL
        )
        updated = self.service.update(memory.id, self.org_id, title="New Title", content="New Content")
        assert updated.title == "New Title"
        assert updated.content == "New Content"

    def test_update_with_versioning(self):
        memory = self.service.create(
            self.org_id, MemoryCategory.BUSINESS_RULE, "Rule 1", "Original rule", MemorySource.MANUAL
        )
        new_version = self.service.update(
            memory.id, self.org_id,
            content="Updated rule", create_version=True
        )
        assert new_version.id != memory.id
        assert new_version.version == 2
        assert new_version.previous_version_id == memory.id
        # Old version should be marked outdated
        old = self.service.get(memory.id, self.org_id)
        assert old.status == MemoryStatus.OUTDATED

    def test_delete_memory(self):
        memory = self.service.create(
            self.org_id, MemoryCategory.PREFERENCE, "Pref", "Content", MemorySource.MANUAL
        )
        assert self.service.delete(memory.id, self.org_id) is True
        # Should still exist but be inactive
        retrieved = self.db.get(BusinessMemory, memory.id)
        assert retrieved.status == MemoryStatus.INACTIVE

    def test_delete_wrong_org(self):
        memory = self.service.create(
            self.org_id, MemoryCategory.PREFERENCE, "Pref", "Content", MemorySource.MANUAL
        )
        assert self.service.delete(memory.id, str(uuid4())) is False

    def test_find_conflicts(self):
        self.service.create(
            self.org_id, MemoryCategory.BUSINESS_RULE,
            "Invoice approval threshold",
            "Invoices above $5000 need manager approval",
            MemorySource.MANUAL,
        )
        conflicts = self.service.find_conflicts(
            self.org_id, MemoryCategory.BUSINESS_RULE,
            "Invoice approval threshold changed",
            "Invoices above $10000 need approval",
        )
        assert len(conflicts) >= 1

    def test_get_relevant_memories(self):
        self.service.create(
            self.org_id, MemoryCategory.BUSINESS_RULE,
            "Invoice approval",
            "Invoices over $10,000 require Sarah approval",
            MemorySource.MANUAL,
        )
        self.service.create(
            self.org_id, MemoryCategory.BUSINESS_FACT,
            "Company address",
            "123 Main Street",
            MemorySource.MANUAL,
        )
        results = self.service.get_relevant_memories(self.org_id, "Who approves invoices?")
        assert len(results) >= 1
        assert any("invoice" in m.content.lower() for m in results)


# === MEMORY EXTRACTION TESTS ===

class TestMemoryExtraction:
    def setup_method(self):
        self.extractor = MemoryExtractionService()

    def test_extract_business_rule(self):
        text = "For all invoices above $10,000, Sarah needs to approve them before payment."
        results = self.extractor.extract(text)
        assert len(results) >= 1
        assert results[0].category == MemoryCategory.BUSINESS_RULE

    def test_extract_decision(self):
        text = "We decided to switch to AWS for our cloud infrastructure going forward."
        results = self.extractor.extract(text)
        assert len(results) >= 1
        assert any(m.category == MemoryCategory.DECISION for m in results)

    def test_extract_goal(self):
        text = "Our goal is to increase sales by 30% by end of Q4."
        results = self.extractor.extract(text)
        assert len(results) >= 1
        assert any(m.category == MemoryCategory.GOAL for m in results)

    def test_extract_preference(self):
        text = "We prefer using Slack for internal communications instead of email."
        results = self.extractor.extract(text)
        assert len(results) >= 1
        assert any(m.category == MemoryCategory.PREFERENCE for m in results)

    def test_skip_trivial_text(self):
        text = "OK, sounds good."
        results = self.extractor.extract(text)
        assert len(results) == 0

    def test_skip_short_text(self):
        results = self.extractor.extract("Hi")
        assert len(results) == 0


# === GRAPH SERVICE UNIT TESTS ===

class TestGraphService:
    def setup_method(self):
        self.db = SessionLocal()
        self.org_id = str(uuid4())
        self.service = GraphService(self.db)

    def teardown_method(self):
        self.db.rollback()
        self.db.close()

    def test_create_entity(self):
        entity = self.service.create_entity(
            self.org_id, EntityType.COMPANY, "Acme Corp",
            description="Main company"
        )
        assert entity.id is not None
        assert entity.name == "Acme Corp"
        assert entity.entity_type == EntityType.COMPANY

    def test_get_entity(self):
        entity = self.service.create_entity(self.org_id, EntityType.PERSON, "John Doe")
        retrieved = self.service.get_entity(entity.id, self.org_id)
        assert retrieved is not None
        assert retrieved.name == "John Doe"

    def test_get_entity_wrong_org(self):
        """Tenant isolation for graph entities."""
        entity = self.service.create_entity(self.org_id, EntityType.COMPANY, "Secret Corp")
        retrieved = self.service.get_entity(entity.id, str(uuid4()))
        assert retrieved is None

    def test_search_entities(self):
        self.service.create_entity(self.org_id, EntityType.PRODUCT, "Widget Pro")
        self.service.create_entity(self.org_id, EntityType.PRODUCT, "Gadget Plus")

        results, total = self.service.search_entities(self.org_id, query="Widget")
        assert total >= 1
        assert any(e.name == "Widget Pro" for e in results)

    def test_search_by_type(self):
        self.service.create_entity(self.org_id, EntityType.CUSTOMER, "Client A")
        self.service.create_entity(self.org_id, EntityType.VENDOR, "Vendor B")

        results, _ = self.service.search_entities(self.org_id, entity_type=EntityType.CUSTOMER)
        assert all(e.entity_type == EntityType.CUSTOMER for e in results)

    def test_create_relationship(self):
        company = self.service.create_entity(self.org_id, EntityType.COMPANY, "Acme")
        employee = self.service.create_entity(self.org_id, EntityType.EMPLOYEE, "Jane")

        rel = self.service.create_relationship(
            self.org_id, employee.id, company.id, RelationshipType.WORKS_FOR
        )
        assert rel is not None
        assert rel.relationship_type == RelationshipType.WORKS_FOR

    def test_create_relationship_cross_org_fails(self):
        """Cannot create relationship with entity from another org."""
        entity1 = self.service.create_entity(self.org_id, EntityType.COMPANY, "A")
        other_org = str(uuid4())
        entity2 = self.service.create_entity(other_org, EntityType.COMPANY, "B")

        rel = self.service.create_relationship(
            self.org_id, entity1.id, entity2.id, RelationshipType.RELATED_TO
        )
        assert rel is None  # Target entity not found in this org

    def test_get_entity_relationships(self):
        company = self.service.create_entity(self.org_id, EntityType.COMPANY, "Acme")
        dept = self.service.create_entity(self.org_id, EntityType.DEPARTMENT, "Engineering")
        self.service.create_relationship(
            self.org_id, dept.id, company.id, RelationshipType.PART_OF
        )

        rels = self.service.get_entity_relationships(dept.id, self.org_id)
        assert len(rels) >= 1
        assert rels[0]["relationship_type"] == "part_of"

    def test_delete_entity_cascades_relationships(self):
        a = self.service.create_entity(self.org_id, EntityType.PERSON, "A")
        b = self.service.create_entity(self.org_id, EntityType.PERSON, "B")
        self.service.create_relationship(
            self.org_id, a.id, b.id, RelationshipType.MANAGES
        )

        assert self.service.delete_entity(a.id, self.org_id) is True
        # B should still exist
        assert self.service.get_entity(b.id, self.org_id) is not None
        # Relationship should be gone
        rels = self.service.get_entity_relationships(b.id, self.org_id)
        assert len(rels) == 0

    def test_get_related_entities(self):
        company = self.service.create_entity(self.org_id, EntityType.COMPANY, "Acme")
        dept = self.service.create_entity(self.org_id, EntityType.DEPARTMENT, "Sales")
        emp = self.service.create_entity(self.org_id, EntityType.EMPLOYEE, "Alice")

        self.service.create_relationship(self.org_id, dept.id, company.id, RelationshipType.PART_OF)
        self.service.create_relationship(self.org_id, emp.id, dept.id, RelationshipType.WORKS_FOR)

        # Depth 1 from company
        related = self.service.get_related_entities(company.id, self.org_id, depth=1)
        assert any(r["name"] == "Sales" for r in related)

        # Depth 2 from company should reach employee
        related_deep = self.service.get_related_entities(company.id, self.org_id, depth=2)
        assert any(r["name"] == "Alice" for r in related_deep)

    def test_delete_relationship(self):
        a = self.service.create_entity(self.org_id, EntityType.VENDOR, "V1")
        b = self.service.create_entity(self.org_id, EntityType.PRODUCT, "P1")
        rel = self.service.create_relationship(
            self.org_id, a.id, b.id, RelationshipType.PROVIDES
        )
        assert self.service.delete_relationship(rel.id, self.org_id) is True


# === API INTEGRATION TESTS ===

class TestMemoryAPI:
    def setup_method(self):
        self.client = get_test_client()

    def test_create_and_list_memories(self):
        token, _ = register_and_login(self.client)
        headers = {"Authorization": f"Bearer {token}"}

        # Create
        res = self.client.post("/api/memory", json={
            "category": "business_fact",
            "title": "Company Name",
            "content": "We are Acme Corp",
            "source": "manual",
        }, headers=headers)
        assert res.status_code == 201
        memory_id = res.json()["id"]

        # List
        res = self.client.get("/api/memory", headers=headers)
        assert res.status_code == 200
        assert res.json()["total"] >= 1

        # Get
        res = self.client.get(f"/api/memory/{memory_id}", headers=headers)
        assert res.status_code == 200
        assert res.json()["title"] == "Company Name"

    def test_update_memory(self):
        token, _ = register_and_login(self.client)
        headers = {"Authorization": f"Bearer {token}"}

        res = self.client.post("/api/memory", json={
            "category": "preference",
            "title": "Email tool",
            "content": "We use Gmail",
            "source": "manual",
        }, headers=headers)
        memory_id = res.json()["id"]

        res = self.client.patch(f"/api/memory/{memory_id}", json={
            "content": "We switched to Outlook",
        }, headers=headers)
        assert res.status_code == 200
        assert res.json()["content"] == "We switched to Outlook"

    def test_delete_memory(self):
        token, _ = register_and_login(self.client)
        headers = {"Authorization": f"Bearer {token}"}

        res = self.client.post("/api/memory", json={
            "category": "business_fact",
            "title": "To Delete",
            "content": "Temporary",
            "source": "manual",
        }, headers=headers)
        memory_id = res.json()["id"]

        res = self.client.delete(f"/api/memory/{memory_id}", headers=headers)
        assert res.status_code == 200

    def test_memory_tenant_isolation_api(self):
        """One user cannot access another org's memories."""
        token1, _ = register_and_login(self.client, "user1@test.com")
        token2, _ = register_and_login(self.client, "user2@test.com")

        headers1 = {"Authorization": f"Bearer {token1}"}
        headers2 = {"Authorization": f"Bearer {token2}"}

        # User 1 creates a memory
        res = self.client.post("/api/memory", json={
            "category": "business_fact",
            "title": "Secret Fact",
            "content": "Confidential",
            "source": "manual",
        }, headers=headers1)
        memory_id = res.json()["id"]

        # User 2 cannot access it
        res = self.client.get(f"/api/memory/{memory_id}", headers=headers2)
        assert res.status_code == 404

    def test_unauthorized_access(self):
        res = self.client.get("/api/memory")
        assert res.status_code in (401, 403)


class TestGraphAPI:
    def setup_method(self):
        self.client = get_test_client()

    def test_create_and_list_entities(self):
        token, _ = register_and_login(self.client)
        headers = {"Authorization": f"Bearer {token}"}

        res = self.client.post("/api/graph/entities", json={
            "entity_type": "company",
            "name": "Acme Corp",
            "description": "Main company",
        }, headers=headers)
        assert res.status_code == 201

        res = self.client.get("/api/graph/entities", headers=headers)
        assert res.status_code == 200
        assert res.json()["total"] >= 1

    def test_create_relationship_api(self):
        token, _ = register_and_login(self.client)
        headers = {"Authorization": f"Bearer {token}"}

        # Create two entities
        res1 = self.client.post("/api/graph/entities", json={
            "entity_type": "employee", "name": "Alice",
        }, headers=headers)
        res2 = self.client.post("/api/graph/entities", json={
            "entity_type": "department", "name": "Engineering",
        }, headers=headers)

        e1_id = res1.json()["id"]
        e2_id = res2.json()["id"]

        # Create relationship
        res = self.client.post("/api/graph/relationships", json={
            "source_entity_id": e1_id,
            "target_entity_id": e2_id,
            "relationship_type": "works_for",
        }, headers=headers)
        assert res.status_code == 201

        # Get relationships
        res = self.client.get(f"/api/graph/entities/{e1_id}/relationships", headers=headers)
        assert res.status_code == 200
        assert len(res.json()["relationships"]) >= 1

    def test_graph_tenant_isolation_api(self):
        """One user cannot access another org's graph entities."""
        token1, _ = register_and_login(self.client, "graph1@test.com")
        token2, _ = register_and_login(self.client, "graph2@test.com")

        headers1 = {"Authorization": f"Bearer {token1}"}
        headers2 = {"Authorization": f"Bearer {token2}"}

        res = self.client.post("/api/graph/entities", json={
            "entity_type": "company", "name": "Secret Corp",
        }, headers=headers1)
        entity_id = res.json()["id"]

        # User 2 cannot see it
        res = self.client.get(f"/api/graph/entities/{entity_id}", headers=headers2)
        assert res.status_code == 404

    def test_delete_entity_api(self):
        token, _ = register_and_login(self.client)
        headers = {"Authorization": f"Bearer {token}"}

        res = self.client.post("/api/graph/entities", json={
            "entity_type": "vendor", "name": "To Delete",
        }, headers=headers)
        entity_id = res.json()["id"]

        res = self.client.delete(f"/api/graph/entities/{entity_id}", headers=headers)
        assert res.status_code == 200


# === RAG + MEMORY INTEGRATION TEST ===

class TestRAGMemoryIntegration:
    def test_context_builder_with_memory(self):
        from packages.rag.context import ContextBuilder
        from packages.rag.retrieval import RetrievedChunk

        # Simulate a memory object
        class FakeMemory:
            category = MemoryCategory.BUSINESS_RULE
            title = "Invoice Approval"
            content = "Invoices over $10k need Sarah's approval"
            source_reference = "conversation-123"

        chunks = [
            RetrievedChunk(
                chunk_id="c1", content="Approval policy doc content",
                score=0.9, metadata={"document_name": "Policy.pdf", "page_number": 3}
            )
        ]
        memories = [FakeMemory()]

        context = ContextBuilder.build_combined_context(
            "Who approves invoices?",
            chunks=chunks,
            memories=memories,
        )
        assert "Invoice Approval" in context
        assert "Approval policy doc content" in context
        assert "Who approves invoices?" in context
