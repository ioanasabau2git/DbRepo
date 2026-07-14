import importlib.util
from pathlib import Path


class DummyResp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class DummySession:
    def __init__(self, pages):
        # pages: list of dicts to return from json()
        self.pages = pages
        self.calls = 0

    def get(self, url, params=None, headers=None, timeout=None):
        if self.calls < len(self.pages):
            data = self.pages[self.calls]
        else:
            data = {"results": []}
        self.calls += 1
        return DummyResp(data)


def load_utils_module():
    repo_root = Path(__file__).resolve().parents[1]
    utils_path = repo_root / "Air quality" / "utils.py"
    spec = importlib.util.spec_from_file_location("utils", str(utils_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fetch_paginated_multiple_pages():
    utils = load_utils_module()

    pages = [
        {"results": [{"id": 1}, {"id": 2}]},
        {"results": [{"id": 3}]},
        {"results": []},
    ]
    session = DummySession(pages)

    items = list(utils.fetch_paginated(
        session, "https://api.openaq.org/v3/locations", items_key="results", limit=2))
    assert items == [{"id": 1}, {"id": 2}, {"id": 3}]


def test_fetch_paginated_handles_missing_key():
    utils = load_utils_module()

    pages = [
        {"not_results": [{"a": 1}]},
        {"results": []},
    ]
    session = DummySession(pages)

    items = list(utils.fetch_paginated(
        session, "https://api.openaq.org/v3/locations", items_key="results", limit=10))
    assert items == []
