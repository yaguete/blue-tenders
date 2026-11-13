"""Cliente de Supabase en memoria, solo para los tests del almacén. No habla con la red."""


class Result:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class FakeSupabase:
    def __init__(self):
        self.tables: dict[str, list[dict]] = {}

    def table(self, name: str) -> "Query":
        self.tables.setdefault(name, [])
        return Query(self.tables, name)


_PK = {
    "partner_participations": ("org_id", "project_id"),
    "opportunity_partner_matches": ("opportunity_id", "org_id"),
    "opportunity_track_record": ("opportunity_id",),
}


class Query:
    def __init__(self, tables: dict, name: str):
        self.tables = tables
        self.name = name
        self.filters: list[tuple] = []
        self.op = "select"
        self.payload = None
        self.span = None
        self._count = None
        self._head = False

    def select(self, _columns: str = "*", count=None, head: bool = False):
        self.op = "select"
        self._count = count
        self._head = head
        return self

    def eq(self, column: str, value):
        self.filters.append(("eq", column, value))
        return self

    def in_(self, column: str, values):
        self.filters.append(("in", column, set(values)))
        return self

    def is_(self, column: str, value):
        self.filters.append(("is", column, value))
        return self

    def range(self, start: int, end: int):
        self.span = (start, end + 1)
        return self

    def limit(self, count: int):
        self.span = (0, count)
        return self

    def order(self, *_args, **_kwargs):
        return self

    def upsert(self, rows):
        self.op = "upsert"
        self.payload = rows if isinstance(rows, list) else [rows]
        return self

    def insert(self, rows):
        self.op = "insert"
        self.payload = rows if isinstance(rows, list) else [rows]
        return self

    def update(self, fields: dict):
        self.op = "update"
        self.payload = fields
        return self

    def delete(self):
        self.op = "delete"
        return self

    def execute(self) -> Result:
        table = self.tables.setdefault(self.name, [])
        if self.op == "upsert":
            keys = _PK.get(self.name, ("id",))
            for row in self.payload:
                identity = tuple(row.get(key) for key in keys)
                for index, current in enumerate(table):
                    if tuple(current.get(key) for key in keys) == identity:
                        merged = dict(current)
                        merged.update(row)
                        table[index] = merged
                        break
                else:
                    table.append(dict(row))
            return Result(list(self.payload))
        if self.op == "insert":
            copied = [dict(row) for row in self.payload]
            table.extend(copied)
            return Result(copied)
        matched = [row for row in table if self._matches(row)]
        if self.op == "update":
            for row in matched:
                row.update(self.payload)
            return Result(matched)
        if self.op == "delete":
            self.tables[self.name] = [row for row in table if row not in matched]
            if self.name == "partner_projects":
                gone = {row["id"] for row in matched}
                parts = self.tables.get("partner_participations", [])
                self.tables["partner_participations"] = [
                    row for row in parts if row.get("project_id") not in gone
                ]
            return Result(matched)
        if self.span:
            matched = matched[self.span[0] : self.span[1]]
        if getattr(self, "_count", None) == "exact":
            full = [row for row in self.tables.setdefault(self.name, []) if self._matches(row)]
            if self._head:
                return Result([], count=len(full))
            return Result(matched, count=len(full))
        return Result(matched)

    def _matches(self, row: dict) -> bool:
        for kind, column, value in self.filters:
            current = row.get(column)
            if kind == "eq" and current != value:
                return False
            if kind == "in" and current not in value:
                return False
            if kind == "is" and value == "null" and current is not None:
                return False
        return True
