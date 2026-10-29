"""Регрессия SEC-04: доступ к договорам и приватным шаблонам."""
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.contracts import generation_routes, template_routes
from src.api.dependencies import get_current_user
from src.api.v2 import templates as governance_routes
from src.agents.contract_generator_agent import ContractGeneratorAgent
from src.core.templates.models import TemplateVersion
from src.models.auth_models import User
from src.models.database import AnalysisResult, Contract, Template, get_db
from src.models.repositories import TemplateRepository
from src.services.contract_generation_service import ContractGenerationService, GenerationResult
from src.services.template_manager import TemplateManager


@pytest.fixture
def users(test_db):
    data = {}
    for name, role in (("a", "lawyer"), ("b", "lawyer"), ("demo", "demo"), ("admin", "admin")):
        user = User(id=name, email=f"{name}@example.test", name=name, role=role)
        test_db.add(user)
        data[name] = user
    test_db.commit()
    return data


@pytest.fixture
def api(test_db, users):
    app = FastAPI()
    app.include_router(template_routes.router, prefix="/contracts")
    app.include_router(generation_routes.router, prefix="/contracts")
    app.include_router(governance_routes.router, prefix="/v2")
    ctx = SimpleNamespace(user=users["a"])
    app.dependency_overrides[get_current_user] = lambda: ctx.user
    app.dependency_overrides[get_db] = lambda: test_db
    with TestClient(app) as client:
        yield client, ctx


@pytest.fixture
def contract(test_db, users, tmp_path):
    path = tmp_path / "private.xml"
    path.write_text("<contract>Личные условия A</contract>", encoding="utf-8")
    contract = Contract(
        file_name=path.name, file_path=str(path), document_type="contract",
        contract_type="supply", status="completed", assigned_to=users["a"].id,
    )
    test_db.add(contract)
    test_db.flush()
    test_db.add(AnalysisResult(contract_id=contract.id))
    test_db.commit()
    return contract


@pytest.fixture
def templates(test_db, users):
    data = {}
    for idx, (name, owner) in enumerate((("public", None), ("a", "a"), ("b", "b")), 1):
        template = Template(
            id=f"template-{name}", name=name, contract_type="supply",
            xml_content=f"<contract><metadata/><parties/><clauses>{name}</clauses></contract>",
            version=f"{idx}.0", owner_id=owner, created_by=users["admin"].id,
            created_at=datetime(2026, 1, 1) + timedelta(days=idx), active=True,
        )
        test_db.add(template)
        data[name] = template
    test_db.commit()
    return data


def _save(client, contract_id):
    return client.post(
        f"/contracts/{contract_id}/save-as-template",
        json={"name": "Личный шаблон", "contract_type": "supply"},
    )


@pytest.mark.parametrize("user", ["b", "demo"])
def test_foreign_contract_is_denied(api, users, contract, test_db, user):
    client, ctx = api
    ctx.user = users[user]
    assert _save(client, contract.id).status_code == 403
    assert client.get(f"/contracts/{contract.id}/template-status").status_code == 403
    assert _save(client, "missing").status_code == 404
    assert client.get("/contracts/missing/template-status").status_code == 404
    assert test_db.query(Template).count() == 0


@pytest.mark.parametrize("user", ["a", "admin", "demo"])
def test_owner_can_save_and_see_template(api, users, contract, test_db, user):
    client, ctx = api
    if user == "demo":
        contract.assigned_to = users["demo"].id
        test_db.commit()
    ctx.user = users[user]
    resp = _save(client, contract.id)
    assert resp.status_code == 200, resp.text
    template_id = resp.json()["template_id"]
    template = test_db.get(Template, template_id)
    assert template.owner_id == contract.assigned_to
    assert template.created_by == users[user].id
    assert template.xml_content == Path(contract.file_path).read_text(encoding="utf-8")
    assert _save(client, contract.id).status_code == 409
    ctx.user = users[contract.assigned_to]
    assert client.get(f"/contracts/{contract.id}/template-status").json()["template_id"] == template_id
    assert {row["id"] for row in client.get("/contracts/templates").json()} == {template_id}
    ctx.user = users["b"]
    assert client.get("/contracts/templates").json() == []


@pytest.mark.parametrize("user, names", [
    ("a", {"public", "a"}), ("b", {"public", "b"}),
    ("demo", {"public"}), ("admin", {"public", "a", "b"}),
])
def test_visible_templates(api, users, templates, user, names):
    client, ctx = api
    ctx.user = users[user]
    for url in ("/contracts/templates", "/contracts/templates?contract_type=supply"):
        resp = client.get(url)
        assert resp.status_code == 200
        assert {row["name"] for row in resp.json()} == names


@pytest.mark.parametrize("user, expected", [
    ("a", "a"), ("b", "b"), ("demo", "public"), ("admin", "b"),
])
def test_generation_uses_only_visible_template(api, users, templates, monkeypatch, user, expected):
    client, ctx = api
    ctx.user = users[user]
    generate = Mock(return_value=GenerationResult(success=False, error="Тестовая заглушка"))
    monkeypatch.setattr(ContractGenerationService, "generate", generate)
    monkeypatch.setattr(ContractGenerationService, "__init__", lambda self: None)
    resp = client.post("/contracts/generate", json={"contract_type": "supply", "params": {}})
    # Останавливаем генерацию после выбора: LLM и файловый экспорт не вызываются.
    assert resp.status_code == 502
    assert generate.call_args.kwargs["template_text"] == templates[expected].xml_content


def test_generation_without_visible_template(api, users, templates, test_db, monkeypatch):
    client, ctx = api
    ctx.user = users["b"]
    templates["public"].active = False
    templates["b"].active = False
    test_db.commit()
    generate = Mock(return_value=GenerationResult(success=False, error="Тестовая заглушка"))
    monkeypatch.setattr(ContractGenerationService, "generate", generate)
    monkeypatch.setattr(ContractGenerationService, "__init__", lambda self: None)
    resp = client.post("/contracts/generate", json={"contract_type": "supply", "params": {}})
    assert resp.status_code == 502
    assert generate.call_args.kwargs["template_text"] == ""


def test_type_catalog_hides_foreign_template(api, users, templates, test_db):
    client, ctx = api
    templates["public"].active = False
    templates["b"].active = False
    test_db.commit()
    for user, expected in (("b", False), ("demo", False), ("a", True), ("admin", True)):
        ctx.user = users[user]
        resp = client.get("/contracts/generate/types")
        assert resp.status_code == 200
        supply = next(row for row in resp.json() if row["code"] == "supply")
        assert supply["has_template"] is expected


def test_repository_and_manager_are_scoped(test_db, users, templates, tmp_path):
    repo = TemplateRepository(test_db, users["b"].id)
    for rows in (repo.get_all(), repo.get_by_type("supply"), repo.get_active_templates()):
        assert {row.id for row in rows} == {templates["public"].id, templates["b"].id}
    assert repo.get_by_id(templates["a"].id) is None
    assert TemplateRepository(test_db).get_latest_version("supply").id == templates["public"].id
    manager = TemplateManager(test_db, str(tmp_path), user_id=users["b"].id)
    assert manager.get_template("supply").id == templates["b"].id
    assert manager.get_template("supply", version="2.0") is None
    with pytest.raises(ValueError):
        manager.fill_template(templates["a"].id, {})
    version = manager.create_version(templates["b"].id, "4.0")
    assert version.owner_id == users["b"].id


def test_template_inheritance_preserves_owner(test_db, templates, tmp_path):
    manager = TemplateManager(test_db, str(tmp_path), user_id="a")
    path = tmp_path / "child.xml"
    path.write_text("<contract><metadata/><parties/><clauses/></contract>", encoding="utf-8")
    template = manager.load_template_from_file(
        str(path), "supply", "Наследник", version="4.0",
        base_template_id=templates["a"].id,
    )
    assert template.owner_id == "a"
    assert TemplateRepository(test_db, "b").get_by_id(template.id) is None


@pytest.mark.parametrize("user, expected", [("a", "a"), ("b", "b"), ("demo", "public"), (None, "public")])
def test_agent_selects_visible_template(test_db, templates, tmp_path, user, expected):
    manager = TemplateManager(test_db, str(tmp_path))
    agent = ContractGeneratorAgent(Mock(), test_db, template_manager=manager)
    assert agent._find_template({"contract_type": "supply"}, user_id=user).id == templates[expected].id


@pytest.mark.parametrize("user, found", [("a", True), ("b", False), ("demo", False), ("admin", True), (None, False)])
def test_rag_selection_respects_owner(test_db, templates, tmp_path, user, found):
    rag = Mock()
    rag.search.return_value = [{"metadata": {"template_id": templates["a"].id}}]
    agent = ContractGeneratorAgent(
        Mock(), test_db, TemplateManager(test_db, str(tmp_path)), rag_system=rag,
    )
    template = agent._find_template({"contract_type": "other"}, user_id=user)
    assert (template is not None) is found


def test_rag_does_not_select_inactive_template(test_db, templates, tmp_path):
    templates["a"].active = False
    test_db.commit()
    rag = Mock()
    rag.search.return_value = [{"metadata": {"template_id": templates["a"].id}}]
    agent = ContractGeneratorAgent(
        Mock(), test_db, TemplateManager(test_db, str(tmp_path)), rag_system=rag,
    )
    assert agent._find_template({"contract_type": "other"}, user_id="a") is None


def test_agent_passes_user_to_selection(test_db, templates, tmp_path, monkeypatch):
    agent = ContractGeneratorAgent(Mock(), test_db, TemplateManager(test_db, str(tmp_path)))
    monkeypatch.setattr(agent, "_extract_parameters", lambda *args: {"contract_type": "supply"})
    generate = Mock(return_value="<contract/>")
    monkeypatch.setattr(agent, "_generate_contract", generate)
    monkeypatch.setattr(agent, "_validate_contract", lambda *args: {"passed": True})
    result = agent.execute({"contract_id": "test", "parsed_xml": "<request/>", "user_id": "a"})
    assert result.success
    assert result.data["template_id"] == templates["a"].id


def test_template_status_does_not_disclose_foreign_template(api, templates, users, contract, test_db):
    client, ctx = api
    templates["b"].meta_info = {"source_contract_id": contract.id}
    test_db.commit()
    resp = client.get(f"/contracts/{contract.id}/template-status")
    assert resp.status_code == 200
    assert resp.json()["has_template"] is False
    assert _save(client, contract.id).status_code == 200


def test_governance_cannot_bypass_owner(api, users, templates, test_db):
    client, ctx = api
    template = templates["a"]
    version = TemplateVersion(template_id=template.id, version=1, content={"text": "Личное"}, status="active")
    test_db.add(version)
    test_db.commit()
    ctx.user = users["b"]
    for url in (f"/v2/templates/{template.id}/versions", f"/v2/templates/{template.id}/versions/active"):
        assert client.get(url).status_code == 404
    assert client.post(
        f"/v2/templates/{template.id}/versions",
        json={"template_id": template.id, "content": {"text": "Чужая версия"}},
    ).status_code == 404
    assert client.post(f"/v2/templates/versions/{version.id}/activate").status_code == 404
    assert test_db.query(TemplateVersion).count() == 1
    for user in ("a", "admin"):
        ctx.user = users[user]
        assert client.get(f"/v2/templates/{template.id}/versions/active").status_code == 200


@pytest.mark.parametrize("user", ["b", "demo"])
def test_disagreements_check_contract_access(api, users, contract, monkeypatch, user):
    client, ctx = api
    ctx.user = users[user]
    gateway = Mock(side_effect=AssertionError("LLM не должен вызываться"))
    monkeypatch.setattr(generation_routes, "LLMGateway", gateway)
    resp = client.post("/contracts/disagreements", json={"contract_id": contract.id, "analysis_id": "test"})
    assert resp.status_code == 403
    gateway.assert_not_called()


def test_template_owner_migration(tmp_path):
    path = Path(__file__).resolve().parents[1] / "alembic/versions/028_template_owner.py"
    spec = importlib.util.spec_from_file_location("template_owner_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        conn.exec_driver_sql("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, role TEXT)")
        conn.exec_driver_sql("CREATE TABLE contracts (id VARCHAR(36) PRIMARY KEY, assigned_to VARCHAR(36))")
        conn.exec_driver_sql(
            "CREATE TABLE templates (id VARCHAR(36) PRIMARY KEY, xml_content TEXT NOT NULL, meta_info JSON)"
        )
        conn.exec_driver_sql("INSERT INTO templates VALUES ('legacy', 'Общий шаблон', NULL)")
        # Сохранённые до исправления из договоров: админа — образец организации, демо — приватный.
        conn.exec_driver_sql("INSERT INTO users VALUES ('adm', 'admin'), ('demo', 'demo')")
        conn.exec_driver_sql("INSERT INTO contracts VALUES ('c-adm', 'adm'), ('c-demo', 'demo')")
        conn.exec_driver_sql(
            "INSERT INTO templates VALUES ('from-adm', 'x', '{\"source_contract_id\": \"c-adm\"}'), "
            "('from-demo', 'x', '{\"source_contract_id\": \"c-demo\"}')"
        )
        conn.exec_driver_sql(
            "CREATE TABLE template_versions (id VARCHAR(36) PRIMARY KEY, "
            "template_id VARCHAR(36) REFERENCES templates(id) ON DELETE CASCADE)"
        )
        conn.exec_driver_sql("INSERT INTO template_versions VALUES ('v1', 'legacy')")
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
        owners = dict(conn.exec_driver_sql("SELECT id, owner_id FROM templates").all())
        assert owners == {"legacy": None, "from-adm": None, "from-demo": "demo"}
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM template_versions").scalar() == 1
        fk = conn.exec_driver_sql("PRAGMA foreign_key_list(templates)").one()
        assert (fk[2], fk[3], fk[6]) == ("users", "owner_id", "CASCADE")
        conn.exec_driver_sql("INSERT INTO users VALUES ('owner', 'lawyer')")
        conn.exec_driver_sql("INSERT INTO templates VALUES ('private', 'Личное', NULL, 'owner')")
        conn.exec_driver_sql("DELETE FROM users WHERE id IN ('owner', 'demo')")
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM templates").scalar() == 2
        with Operations.context(MigrationContext.configure(conn)):
            migration.downgrade()
        assert "owner_id" not in {col["name"] for col in sa.inspect(conn).get_columns("templates")}
        assert conn.exec_driver_sql("SELECT xml_content FROM templates WHERE id='legacy'").scalar() == "Общий шаблон"
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM template_versions").scalar() == 1
    engine.dispose()
