"""Conexión PostgreSQL; SQLite queda disponible únicamente para pruebas explícitas."""
from pathlib import Path
import sqlite3


class Record(dict):
    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


def row_factory(cursor):
    names = [column.name for column in (cursor.description or ())]
    return lambda values: Record(zip(names, values))


class PostgresConnection:
    def __init__(self, url):
        import psycopg
        self.connection = psycopg.connect(url, row_factory=row_factory, connect_timeout=5)

    def execute(self, statement, parameters=None):
        if statement == "PRAGMA foreign_keys = ON":
            return None
        if statement in ("BEGIN", "BEGIN IMMEDIATE"):
            if statement == "BEGIN IMMEDIATE":
                # Serializa apertura/cierre de sesiones entre procesos.
                return self.connection.execute("LOCK TABLE alerts, closed_alert_sessions IN EXCLUSIVE MODE")
            return None  # psycopg inicia la transacción al ejecutar la primera consulta.
        ignore = "INSERT OR IGNORE" in statement
        statement = statement.replace("INSERT OR IGNORE", "INSERT").replace("?", "%s")
        if statement.lstrip().startswith("CREATE TABLE"):
            statement = statement.replace(" REAL", " DOUBLE PRECISION")
        if ignore:
            statement += " ON CONFLICT DO NOTHING"
        if parameters is not None:
            parameters = tuple(int(value) if isinstance(value, bool) else value for value in parameters)
        return self.connection.execute(statement, parameters)

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        self.connection.rollback() if kind else self.connection.commit()

    def close(self):
        self.connection.close()


def connect(target):
    if str(target).startswith(("postgresql://", "postgres://")):
        return PostgresConnection(str(target))
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection
