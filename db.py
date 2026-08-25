"""
Storage abstraction layer.

Exposes get_collection(name) -> a Collection object with a small subset of
the pymongo Collection API (find, find_one, insert_one, update_one with
upsert, delete_one). This lets every blueprint be written exactly as it
would be against real MongoDB, while this project runs with zero external
services out of the box.

If config.USE_MONGO is True and pymongo is installed, real Mongo collections
are returned instead — no code changes needed anywhere else in the app.
"""

import json
import os
import threading
import copy

import config

_lock = threading.Lock()


def _load(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
        return json.loads(content) if content else []


def _save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp, path)


def _matches(doc, query):
    for key, val in query.items():
        if key not in doc or doc[key] != val:
            return False
    return True


class JSONCollection:
    """A tiny Mongo-collection-shaped wrapper around a JSON file."""

    def __init__(self, path):
        self.path = path
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path), exist_ok=True)

    def find(self, query=None):
        query = query or {}
        with _lock:
            data = _load(self.path)
        return [copy.deepcopy(d) for d in data if _matches(d, query)]

    def find_one(self, query=None):
        results = self.find(query)
        return results[0] if results else None

    def insert_one(self, doc):
        with _lock:
            data = _load(self.path)
            data.append(copy.deepcopy(doc))
            _save(self.path, data)
        return doc

    def update_one(self, query, update, upsert=False):
        with _lock:
            data = _load(self.path)
            updated = False
            for i, d in enumerate(data):
                if _matches(d, query):
                    if "$set" in update:
                        d.update(update["$set"])
                    if "$unset" in update:
                        for k in update["$unset"]:
                            d.pop(k, None)
                    data[i] = d
                    updated = True
                    break
            if not updated and upsert:
                new_doc = dict(query)
                if "$set" in update:
                    new_doc.update(update["$set"])
                data.append(new_doc)
                updated = True
            _save(self.path, data)
        return updated

    def delete_one(self, query):
        with _lock:
            data = _load(self.path)
            for i, d in enumerate(data):
                if _matches(d, query):
                    del data[i]
                    _save(self.path, data)
                    return True
        return False


_collections = {}


def get_collection(name):
    """Return a collection by logical name: 'teachers' or 'students'."""
    if name in _collections:
        return _collections[name]

    if getattr(config, "USE_MONGO", False):
        try:
            from pymongo import MongoClient
            client = MongoClient(config.MONGO_URI)
            db = client[config.MONGO_DB_NAME]
            coll = db[name]
            _collections[name] = coll
            return coll
        except Exception as exc:  # pragma: no cover
            print(f"[db] Mongo unavailable ({exc}); falling back to JSON store.")

    path = config.TEACHERS_FILE if name == "teachers" else config.STUDENTS_FILE
    coll = JSONCollection(path)
    _collections[name] = coll
    return coll
