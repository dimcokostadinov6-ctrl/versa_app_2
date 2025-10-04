import sqlite3
from typing import List, Tuple, Optional
from core.ports import IRepository

class SQLiteRepo(IRepository):
    def __init__(self, db_path: str = "infra/veresia.db"):
        self.db_path = db_path

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def init(self) -> None:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS pages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT, ts TEXT
            )""")
            cur.execute("""CREATE TABLE IF NOT EXISTS entries(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, amount_st INTEGER, ts TEXT, page_id INTEGER
            )""")
            con.commit()

    def add_page(self, path: str, ts: str) -> int:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("INSERT INTO pages(path, ts) VALUES(?, ?)", (path, ts))
            con.commit()
            return cur.lastrowid

    def add_entry(self, name: str, amount_st: int, ts: str, page_id: Optional[int]) -> None:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("INSERT INTO entries(name, amount_st, ts, page_id) VALUES(?,?,?,?)",
                        (name, amount_st, ts, page_id))
            con.commit()

    # Агрегирана справка (оставяме я – може да е полезна)
    def search_by_name(self, q: str) -> List[Tuple[str, int]]:
        with self._conn() as con:
            cur = con.cursor()
            if (q or "").strip():
                cur.execute("""SELECT name, SUM(amount_st) FROM entries
                               WHERE name LIKE ? GROUP BY name ORDER BY 2 DESC""", (f"%{q}%",))
            else:
                cur.execute("""SELECT name, SUM(amount_st) FROM entries
                               GROUP BY name ORDER BY 2 DESC""")
            return [(r[0], int(r[1] or 0)) for r in cur.fetchall()]

    # Детайлна справка: всички записи за точно име
    def list_entries(self, name: str) -> List[Tuple[str, int, Optional[int]]]:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("""SELECT ts, amount_st, page_id
                           FROM entries
                           WHERE name = ?
                           ORDER BY ts ASC""", (name,))
            rows = cur.fetchall()
            return [(r[0], int(r[1] or 0), r[2]) for r in rows]

    def sum_for_name(self, name: str) -> int:
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("SELECT SUM(amount_st) FROM entries WHERE name = ?", (name,))
            val = cur.fetchone()[0]
            return int(val or 0)
