from easy_claw.storage.db import connect_product_db, initialize_product_db
from easy_claw.storage.repositories import MemoryRepository, SessionRecord, SessionRepository


class FakeConnection:
    def __init__(self):
        self.row_factory = None
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def close(self):
        self.closed = True


def test_initialize_product_db_creates_tables(tmp_path):
    db_path = tmp_path / "easy-claw.db"

    initialize_product_db(db_path)

    assert db_path.exists()


def test_connect_product_db_closes_connection(tmp_path, monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr("easy_claw.storage.db.sqlite3.connect", lambda _: connection)

    with connect_product_db(tmp_path / "easy-claw.db") as opened:
        assert opened is connection

    assert connection.closed is True


def test_session_repository_creates_and_lists_sessions(tmp_path):
    db_path = tmp_path / "easy-claw.db"
    initialize_product_db(db_path)
    repo = SessionRepository(db_path)

    session = repo.create_session(workspace_path=str(tmp_path), model="test:model")

    assert session.id
    assert repo.list_sessions()[0].id == session.id


def test_session_repository_gets_session_by_id(tmp_path):
    db_path = tmp_path / "easy-claw.db"
    initialize_product_db(db_path)
    repo = SessionRepository(db_path)
    first = repo.create_session(workspace_path=str(tmp_path), model="test:first")
    repo.create_session(workspace_path=str(tmp_path), model="test:second")

    result = repo.get_session(first.id)

    assert isinstance(result, SessionRecord)
    assert result.id == first.id
    assert repo.get_session("missing") is None


def test_memory_repository_round_trips_memory_items(tmp_path):
    db_path = tmp_path / "easy-claw.db"
    initialize_product_db(db_path)
    repo = MemoryRepository(db_path)

    item = repo.remember(scope="project", key="decision", content="CLI first")

    assert repo.list_memory()[0].id == item.id
    assert repo.list_memory()[0].content == "CLI first"
