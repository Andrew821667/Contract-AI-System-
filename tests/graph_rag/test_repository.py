# -*- coding: utf-8 -*-
"""
Tests for Graph-RAG Repository.

Тесты CRUD-операций, CTE traversal, аудита.
Используют test_db fixture из conftest.py (SQLite in-memory).
"""
import pytest

from src.core.graph_rag.repository import GraphRepository
from src.core.graph_rag.models import GraphDocument, GraphNode, GraphEdge, RAGAuditLog
from src.core.graph_rag.enums import (
    EdgeType, EdgeClass, EdgeStatus, ExtractedBy,
    DocumentStatus, AuditAction,
)


class TestGraphDocumentRepository:
    """Тесты GraphDocumentRepository."""

    def test_create_document(self, test_db):
        repo = GraphRepository(test_db)
        doc = repo.documents.create(
            layer="contract",
            title="Тестовый договор",
            document_type="supply",
        )
        test_db.flush()

        assert doc.id is not None
        assert doc.layer == "contract"
        assert doc.title == "Тестовый договор"
        assert doc.status == "active"

    def test_get_active_documents(self, test_db):
        repo = GraphRepository(test_db)
        repo.documents.create(layer="contract", title="Договор 1")
        repo.documents.create(layer="npa", title="ГК РФ")
        test_db.flush()

        all_docs = repo.documents.get_active()
        assert len(all_docs) == 2

        contracts = repo.documents.get_active(layer="contract")
        assert len(contracts) == 1

    def test_archive_document(self, test_db):
        repo = GraphRepository(test_db)
        doc = repo.documents.create(layer="contract", title="Для архива")
        test_db.flush()

        archived = repo.documents.archive(doc.id, reason="Тестовая архивация")
        assert archived.status == "archived"

        active = repo.documents.get_active()
        assert len(active) == 0

    def test_create_document_creates_audit(self, test_db):
        repo = GraphRepository(test_db)
        doc = repo.documents.create(layer="contract", title="Аудит тест")
        test_db.flush()

        logs = test_db.query(RAGAuditLog).filter(
            RAGAuditLog.entity_id == doc.id
        ).all()
        assert len(logs) >= 1
        assert logs[0].action == AuditAction.DOCUMENT_INGESTED


class TestGraphNodeRepository:
    """Тесты GraphNodeRepository."""

    def _create_doc(self, repo):
        return repo.documents.create(layer="contract", title="Test Doc")

    def test_create_node(self, test_db):
        repo = GraphRepository(test_db)
        doc = self._create_doc(repo)
        node = repo.nodes.create(
            document_id=doc.id,
            layer="contract",
            node_type="clause",
            text="Текст пункта",
            number="1.1",
            level=1,
            position=0,
        )
        test_db.flush()

        assert node.id is not None
        assert node.number == "1.1"
        assert node.text == "Текст пункта"

    def test_create_node_creates_version(self, test_db):
        repo = GraphRepository(test_db)
        doc = self._create_doc(repo)
        node = repo.nodes.create(
            document_id=doc.id, layer="contract",
            node_type="clause", text="Текст", level=0, position=0,
        )
        test_db.flush()

        versions = repo.nodes.get_history(node.id)
        assert len(versions) == 1
        assert versions[0].version_number == 1
        assert versions[0].text == "Текст"

    def test_get_children(self, test_db):
        repo = GraphRepository(test_db)
        doc = self._create_doc(repo)
        parent = repo.nodes.create(
            document_id=doc.id, layer="contract",
            node_type="section", text="Раздел", number="1", level=0, position=0,
        )
        c1 = repo.nodes.create(
            document_id=doc.id, layer="contract",
            node_type="clause", text="П 1.1", number="1.1",
            parent_id=parent.id, level=1, position=0,
        )
        c2 = repo.nodes.create(
            document_id=doc.id, layer="contract",
            node_type="clause", text="П 1.2", number="1.2",
            parent_id=parent.id, level=1, position=1,
        )
        test_db.flush()

        children = repo.nodes.get_children(parent.id)
        assert len(children) == 2
        assert children[0].number == "1.1"
        assert children[1].number == "1.2"

    def test_get_ancestors_cte(self, test_db):
        repo = GraphRepository(test_db)
        doc = self._create_doc(repo)
        root = repo.nodes.create(
            document_id=doc.id, layer="contract",
            node_type="document", text="root", level=0, position=0,
        )
        sec = repo.nodes.create(
            document_id=doc.id, layer="contract",
            node_type="section", text="sec", number="1",
            parent_id=root.id, level=1, position=0,
        )
        clause = repo.nodes.create(
            document_id=doc.id, layer="contract",
            node_type="clause", text="clause", number="1.1",
            parent_id=sec.id, level=2, position=0,
        )
        test_db.flush()

        ancestors = repo.nodes.get_ancestors(clause.id)
        assert len(ancestors) == 2  # root + sec
        assert ancestors[0].node_type == "document"
        assert ancestors[1].node_type == "section"

    def test_get_subtree_cte(self, test_db):
        repo = GraphRepository(test_db)
        doc = self._create_doc(repo)
        root = repo.nodes.create(
            document_id=doc.id, layer="contract",
            node_type="section", text="sec", number="1", level=0, position=0,
        )
        c1 = repo.nodes.create(
            document_id=doc.id, layer="contract",
            node_type="clause", text="c1", number="1.1",
            parent_id=root.id, level=1, position=0,
        )
        c2 = repo.nodes.create(
            document_id=doc.id, layer="contract",
            node_type="clause", text="c2", number="1.2",
            parent_id=root.id, level=1, position=1,
        )
        test_db.flush()

        subtree = repo.nodes.get_subtree(root.id)
        assert len(subtree) == 2

    def test_find_by_number(self, test_db):
        repo = GraphRepository(test_db)
        doc = self._create_doc(repo)
        repo.nodes.create(
            document_id=doc.id, layer="contract",
            node_type="clause", text="Текст", number="5.1", level=1, position=0,
        )
        test_db.flush()

        found = repo.nodes.find_by_number(doc.id, "5.1")
        assert found is not None
        assert found.number == "5.1"

        not_found = repo.nodes.find_by_number(doc.id, "99.99")
        assert not_found is None

    def test_update_text_versioning(self, test_db):
        repo = GraphRepository(test_db)
        doc = self._create_doc(repo)
        node = repo.nodes.create(
            document_id=doc.id, layer="contract",
            node_type="clause", text="Старый текст", level=0, position=0,
        )
        test_db.flush()

        updated = repo.nodes.update_text(
            node.id, "Новый текст", reason="Корректировка",
        )
        test_db.flush()

        assert updated.text == "Новый текст"
        versions = repo.nodes.get_history(node.id)
        assert len(versions) == 2
        assert versions[0].text == "Старый текст"
        assert versions[1].text == "Новый текст"

    def test_archive_node_soft_delete(self, test_db):
        repo = GraphRepository(test_db)
        doc = self._create_doc(repo)
        node = repo.nodes.create(
            document_id=doc.id, layer="contract",
            node_type="clause", text="Удаляемый", level=0, position=0,
        )
        test_db.flush()

        archived = repo.nodes.archive(node.id, reason="Тест архивации")
        assert archived.is_archived is True

        # Не находится без include_archived
        assert repo.nodes.get_by_id(node.id) is None
        # Находится с include_archived
        assert repo.nodes.get_by_id(node.id, include_archived=True) is not None


class TestGraphEdgeRepository:
    """Тесты GraphEdgeRepository."""

    def _create_two_nodes(self, repo):
        doc = repo.documents.create(layer="contract", title="Edge Test")
        n1 = repo.nodes.create(
            document_id=doc.id, layer="contract",
            node_type="clause", text="N1", level=0, position=0,
        )
        n2 = repo.nodes.create(
            document_id=doc.id, layer="contract",
            node_type="clause", text="N2", level=0, position=1,
        )
        return n1, n2

    def test_create_edge(self, test_db):
        repo = GraphRepository(test_db)
        n1, n2 = self._create_two_nodes(repo)
        edge = repo.edges.create(
            source_id=n1.id, target_id=n2.id,
            edge_type=EdgeType.REFERENCES.value,
            edge_class=EdgeClass.FACT.value,
            status=EdgeStatus.MACHINE_EXTRACTED.value,
            extracted_by=ExtractedBy.RULE.value,
            confidence=0.9,
        )
        test_db.flush()

        assert edge.id is not None
        assert edge.edge_type == "references"

    def test_get_outgoing_incoming(self, test_db):
        repo = GraphRepository(test_db)
        n1, n2 = self._create_two_nodes(repo)
        repo.edges.create(
            source_id=n1.id, target_id=n2.id,
            edge_type=EdgeType.REFERENCES.value,
            edge_class=EdgeClass.FACT.value,
            status=EdgeStatus.VERIFIED.value,
            extracted_by=ExtractedBy.PARSER.value,
        )
        test_db.flush()

        outgoing = repo.edges.get_outgoing(n1.id)
        assert len(outgoing) == 1

        incoming = repo.edges.get_incoming(n2.id)
        assert len(incoming) == 1

    def test_expand_graph(self, test_db):
        repo = GraphRepository(test_db)
        doc = repo.documents.create(layer="contract", title="Expand test")
        n1 = repo.nodes.create(document_id=doc.id, layer="contract",
                                node_type="clause", text="A", level=0, position=0)
        n2 = repo.nodes.create(document_id=doc.id, layer="contract",
                                node_type="clause", text="B", level=0, position=1)
        n3 = repo.nodes.create(document_id=doc.id, layer="contract",
                                node_type="clause", text="C", level=0, position=2)
        repo.edges.create(
            source_id=n1.id, target_id=n2.id,
            edge_type=EdgeType.REFERENCES.value,
            edge_class=EdgeClass.FACT.value,
            status=EdgeStatus.VERIFIED.value,
            extracted_by=ExtractedBy.PARSER.value,
        )
        repo.edges.create(
            source_id=n2.id, target_id=n3.id,
            edge_type=EdgeType.REFERENCES.value,
            edge_class=EdgeClass.FACT.value,
            status=EdgeStatus.VERIFIED.value,
            extracted_by=ExtractedBy.PARSER.value,
        )
        test_db.flush()

        # Depth 1: от n1 должны найти n2
        edges_d1 = repo.edges.expand([n1.id], max_depth=1)
        target_ids = {e.target_id for e in edges_d1}
        assert n2.id in target_ids

        # Depth 2: от n1 должны найти n2 и n3
        edges_d2 = repo.edges.expand([n1.id], max_depth=2)
        all_ids = {e.source_id for e in edges_d2} | {e.target_id for e in edges_d2}
        assert n3.id in all_ids


class TestCandidateEdgeRepository:
    """Тесты CandidateEdgeRepository."""

    def test_create_and_review_accept(self, test_db):
        from src.core.graph_rag.models import CandidateEdge
        from src.models.auth_models import User

        repo = GraphRepository(test_db)
        doc = repo.documents.create(layer="contract", title="Candidate test")
        n1 = repo.nodes.create(document_id=doc.id, layer="contract",
                                node_type="clause", text="A", level=0, position=0)
        n2 = repo.nodes.create(document_id=doc.id, layer="contract",
                                node_type="clause", text="B", level=0, position=1)

        # Создаём пользователя для ревью
        user = User(email="reviewer@test.com", name="Reviewer", password_hash="x",
                     role="lawyer", subscription_tier="pro")
        test_db.add(user)
        test_db.flush()

        # Создаём кандидата
        candidate = repo.candidates.create(
            source_id=n1.id, target_id=n2.id,
            proposed_type="similar_to_clause",
            proposed_class="analytical",
            rationale="Похожие формулировки",
            confidence=0.7,
        )
        test_db.flush()

        # Pending
        pending = repo.candidates.get_pending()
        assert len(pending) == 1

        # Accept
        reviewed, edge = repo.candidates.review(
            candidate.id, "accepted", user.id, comment="OK",
        )
        test_db.flush()

        assert reviewed.review_result == "accepted"
        assert edge is not None
        assert edge.edge_type == "similar_to_clause"

    def test_create_and_review_reject(self, test_db):
        from src.models.auth_models import User

        repo = GraphRepository(test_db)
        doc = repo.documents.create(layer="contract", title="Reject test")
        n1 = repo.nodes.create(document_id=doc.id, layer="contract",
                                node_type="clause", text="A", level=0, position=0)
        n2 = repo.nodes.create(document_id=doc.id, layer="contract",
                                node_type="clause", text="B", level=0, position=1)

        user = User(email="r2@test.com", name="R2", password_hash="x",
                     role="lawyer", subscription_tier="pro")
        test_db.add(user)
        test_db.flush()

        candidate = repo.candidates.create(
            source_id=n1.id, target_id=n2.id,
            proposed_type="potential_conflict_with_npa",
            proposed_class="risk_signal",
            rationale="Возможный конфликт",
            confidence=0.3,
        )
        test_db.flush()

        reviewed, edge = repo.candidates.review(
            candidate.id, "rejected", user.id, comment="Нет конфликта",
        )
        test_db.flush()

        assert reviewed.review_result == "rejected"
        assert edge is None
