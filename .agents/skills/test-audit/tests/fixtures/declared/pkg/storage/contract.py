from .port import Store


def run_contract(store: Store) -> None:
    store.put("a", "1")
    assert store.get("a") == "1"
