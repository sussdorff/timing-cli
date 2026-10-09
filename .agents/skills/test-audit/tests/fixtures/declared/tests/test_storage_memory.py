from pkg.storage.contract import run_contract
from pkg.storage import memory


def test_memory_store_meets_contract() -> None:
    run_contract(memory.MemoryStore())
