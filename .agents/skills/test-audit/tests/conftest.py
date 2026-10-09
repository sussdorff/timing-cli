"""Keep the fixture repositories out of pytest collection.

The fixtures under ``fixtures/`` are tiny repositories whose files are named like
tests so the boundary report can find them. They are read as text and never run.
"""

collect_ignore = ["fixtures"]
