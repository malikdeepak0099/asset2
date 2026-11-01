"""Each agent's personal listing database (SQLite on the server's /data volume)."""
import json
import os
import sqlite3
import threading
import time

_LOCK = threading.Lock()


class Store:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("""CREATE TABLE IF NOT EXISTS listings (
            agent_uid TEXT, source TEXT, id TEXT, data TEXT, hash TEXT,
            first_seen REAL, last_seen REAL, last_changed REAL, status TEXT,
            PRIMARY KEY (agent_uid, source, id))""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS activity (
            ts REAL, agent_uid TEXT, kind TEXT, source TEXT, id TEXT, detail TEXT)""")
        self.db.commit()

    def apply_snapshot(self, agent_uid, source, records, full=True):
        """Compare a fresh list of listings with the agent's database.

        full=True means `records` is the agent's whole profile on `source`, so listings
        that disappeared are marked Removed. Returns (new, updated, removed, unchanged) lists.
        """
        now = time.time()
        new, updated, removed, same = [], [], [], []
        with _LOCK:
            cur = self.db.execute("SELECT id, hash, status, data FROM listings WHERE agent_uid=? AND source=?",
                                  (agent_uid, source))
            old = {r[0]: r for r in cur.fetchall()}
            fresh_ids = set()
            for rec in records:
                fresh_ids.add(rec["id"])
                data = json.dumps(rec, ensure_ascii=False)
                if rec["id"] not in old:
                    self.db.execute("INSERT INTO listings VALUES (?,?,?,?,?,?,?,?,?)",
                                    (agent_uid, source, rec["id"], data, rec["hash"], now, now, now, "Active"))
                    new.append(rec)
                    self._log(now, agent_uid, "new", source, rec["id"], rec.get("title", ""))
                else:
                    _, h, status, old_data = old[rec["id"]]
                    if h != rec["hash"] or status != "Active":
                        rec["_changes"] = diff(json.loads(old_data), rec) if h != rec["hash"] else ["back on site"]
                        self.db.execute("UPDATE listings SET data=?, hash=?, last_seen=?, last_changed=?, status='Active' "
                                        "WHERE agent_uid=? AND source=? AND id=?",
                                        (data, rec["hash"], now, now, agent_uid, source, rec["id"]))
                        updated.append(rec)
                        self._log(now, agent_uid, "updated", source, rec["id"], ", ".join(rec["_changes"]))
                    else:
                        self.db.execute("UPDATE listings SET last_seen=? WHERE agent_uid=? AND source=? AND id=?",
                                        (now, agent_uid, source, rec["id"]))
                        same.append(rec)
            if full:
                for lid, (_, _, status, old_data) in old.items():
                    if lid not in fresh_ids and status == "Active":
                        self.db.execute("UPDATE listings SET status='Removed', last_changed=? "
                                        "WHERE agent_uid=? AND source=? AND id=?", (now, agent_uid, source, lid))
                        rec = json.loads(old_data)
                        removed.append(rec)
                        self._log(now, agent_uid, "removed", source, lid, rec.get("title", ""))
            self.db.commit()
        return new, updated, removed, same

    def _log(self, ts, agent_uid, kind, source, lid, detail):
        self.db.execute("INSERT INTO activity VALUES (?,?,?,?,?,?)", (ts, agent_uid, kind, source, lid, detail[:300]))

    def counts(self, agent_uid=None):
        q = "SELECT agent_uid, source, status, COUNT(*) FROM listings"
        args = ()
        if agent_uid:
            q += " WHERE agent_uid=?"
            args = (agent_uid,)
        q += " GROUP BY agent_uid, source, status"
        out = {}
        for a, s, st, n in self.db.execute(q, args):
            out.setdefault(a, {}).setdefault(s, {})[st] = n
        return out

    def activity_since(self, ts, agent_uid=None):
        q = "SELECT agent_uid, kind, COUNT(*) FROM activity WHERE ts>=?"
        args = [ts]
        if agent_uid:
            q += " AND agent_uid=?"
            args.append(agent_uid)
        q += " GROUP BY agent_uid, kind"
        out = {}
        for a, k, n in self.db.execute(q, args):
            out.setdefault(a, {})[k] = n
        return out

    def active(self, agent_uid, limit=10):
        cur = self.db.execute("SELECT data FROM listings WHERE agent_uid=? AND status='Active' "
                              "ORDER BY last_changed DESC LIMIT ?", (agent_uid, limit))
        return [json.loads(r[0]) for r in cur.fetchall()]


FIELD_NAMES = {"price_usd": "price $", "price_gel": "price ₾", "description": "description", "photos": "photos",
               "rooms": "rooms", "area": "area", "floor": "floor", "title": "title", "address": "address",
               "status_on_site": "status", "deal": "deal", "type": "type", "bedrooms": "bedrooms",
               "total_floors": "floors"}


def diff(old, new):
    out = []
    for k, name in FIELD_NAMES.items():
        if str(old.get(k) or "") != str(new.get(k) or ""):
            if k in ("price_usd", "price_gel"):
                out.append(f"{name} {old.get(k) or '—'} → {new.get(k) or '—'}")
            else:
                out.append(name)
    return out or ["details"]
