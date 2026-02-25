import sqlite3 as sql


class _Db_columns:
    def __init__(self, cur: sql.Cursor, table_name: str, cols: list[str]) -> None:
        self._cur = cur
        self._table_name = table_name
        self._cols = cols

    def append(self, vals: list) -> None:
        placeholders = ", ".join('?' * len(self._cols))
        self._cur.execute(
            f"INSERT INTO {self._table_name} ({", ".join(self._cols)}) VALUES ({placeholders})",
            vals
        )

    def get(self) -> list:
        raise NotImplementedError()

    def commit(self):
        self._cur.connection.commit()

    def __del__(self):
        self.commit()


class Sql_db_wrapper:
    def __init__(self, path: str, table_name: str, columns: dict[str, str]):
        self.columns = list(columns.keys())

        self._table_name = table_name
        self._conn = sql.connect(path)
        self._cur = self._conn.cursor()

        columns_str = ", ".join([f"{k} {v}" for k,v in columns.items()])
        self._cur.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({columns_str});")
        self._conn.commit()

    def __getitem__(self, key: slice | int | list[str] | list[int]) -> _Db_columns:
        if isinstance(key, slice):
            cols = self.columns[key]
            return _Db_columns(self._cur, self._table_name, cols)
        elif isinstance(key, int):
            cols = [self.columns[key]]
            return _Db_columns(self._cur, self._table_name, cols)
        elif isinstance(key, list):
            if all(isinstance(x, str) for x in key):
                return _Db_columns(self._cur, self._table_name, key)  # pyright: ignore
            elif all(isinstance(x, int) for x in key):
                return _Db_columns(self._cur, self._table_name, [self.columns[k] for k in key])  # pyright: ignore
            else:
                raise Exception("Invalid types in keys; The key shoud be a slice, int, list[str] or list[int]")
        else:
            raise Exception("Invalid types in keys; The key shoud be a slice, int, list[str] or list[int]")

    def close(self):
        self._conn.close()

    def __del__(self):
        self.close()
