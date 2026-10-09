class PostgresStore:
    def get(self, key: str) -> str | None:
        raise NotImplementedError

    def put(self, key: str, value: str) -> None:
        raise NotImplementedError
