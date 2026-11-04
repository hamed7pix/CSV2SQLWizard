"""SQL generation, with no Qt in it.

This used to live inside CSVToSQLConverter.generate_sql, which meant the only
way to check the SQL was to start the application, open a file dialog and read
the preview window. Everything here is a plain function over a DataFrame, so
it can be tested directly.
"""

import pandas as pd

DEFAULT_TYPE = "VARCHAR(255)"
DEFAULT_TABLE_NAME = "table_name"
BATCH_SIZE = 50


def sql_literal(value):
    """One cell as a SQL literal.

    The type tests go through pandas rather than isinstance: a DataFrame hands
    back numpy scalars, and while np.float64 subclasses Python float, np.int64
    does not subclass int. isinstance(value, (int, float)) therefore missed
    every integer column, sent it to the text branch, and `if value` there
    turned a 0 into NULL.

    Booleans are tested before numbers, because bool is a Number.
    """
    if pd.isna(value):
        return "NULL"
    if pd.api.types.is_bool(value):
        return "TRUE" if value else "FALSE"
    if pd.api.types.is_number(value):
        return str(value)
    text = str(value)
    if not text:
        # An empty CSV field means no value. Unchanged.
        return "NULL"
    return "'" + text.replace("'", "''") + "'"


def create_table(table_name, columns):
    """`columns` is a sequence of (name, type) pairs."""
    lines = [f"    {name} {data_type}" for name, data_type in columns]
    return f"CREATE TABLE {table_name} (\n" + ",\n".join(lines) + "\n);"


def insert_statements(table_name, column_names, rows, batch_size=BATCH_SIZE):
    """One INSERT per `batch_size` rows, so a large CSV does not become a
    single statement no server will take."""
    header = f"INSERT INTO {table_name} ({', '.join(column_names)}) VALUES"
    tuples = ["(" + ", ".join(sql_literal(v) for v in row) + ")" for row in rows]

    statements = []
    for start in range(0, len(tuples), batch_size):
        batch = tuples[start:start + batch_size]
        statements.append(header + "\n" + ",\n".join(batch) + ";")
    return statements


def build(df, headers, renames=None, column_types=None,
          table_name=DEFAULT_TABLE_NAME, batch_size=BATCH_SIZE):
    """The CREATE TABLE followed by the INSERTs, in the order they belong in
    the script. `renames` maps an original header to its new name;
    `column_types` maps a *new* name to its SQL type."""
    renames = renames or {}
    column_types = column_types or {}

    names = [renames.get(h, h) for h in headers]
    types = [column_types.get(n, DEFAULT_TYPE) for n in names]
    rows = [[df.iloc[i, j] for j in range(len(headers))] for i in range(len(df))]

    return [create_table(table_name, zip(names, types))] + insert_statements(
        table_name, names, rows, batch_size)
