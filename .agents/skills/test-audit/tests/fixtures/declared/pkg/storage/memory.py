class MemoryStore:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._values.get(key)

    def put(self, key: str, value: str) -> None:
        self._values[key] = value
