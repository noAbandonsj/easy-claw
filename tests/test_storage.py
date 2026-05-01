from easy_claw.storage.db import initialize_product_db
from easy_claw.storage.repositories import MemoryRepository, SessionRepository


def test_initialize_product_db_creates_tables(tmp_path):
    db_path = tmp_path / "easy-claw.db"

    initialize_product_db(db_path)

    assert db_path.exists()


def test_session_repository_creates_and_lists_sessions(tmp_path):
    db_path = tmp_path / "easy-claw.db"
    initialize_product_db(db_path)
    repo = SessionRepository(db_path)

    session = repo.create_session(workspace_path=str(tmp_path), model="test:model")

    assert session.id
    assert repo.list_sessions()[0].id == session.id


def test_memory_repository_round_trips_memory_items(tmp_path):
    db_path = tmp_path / "easy-claw.db"
    initialize_product_db(db_path)
    repo = MemoryRepository(db_path)

    item = repo.remember(scope="project", key="decision", content="CLI first")

    assert repo.list_memory()[0].id == item.id
    assert repo.list_memory()[0].content == "CLI first"
