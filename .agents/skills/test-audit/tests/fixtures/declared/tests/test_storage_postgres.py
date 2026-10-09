from pkg.storage.postgres import PostgresStore


def test_postgres_store_constructs() -> None:
    assert PostgresStore()
