"""Tests for the SQL builder.

Nothing here imports CSV2SQLWizard, so the suite runs without PyQt5 and
without a display.
"""

import numpy as np
import pandas as pd
import pytest

import sql_builder


# --- literals ----------------------------------------------------------

def test_a_single_quote_is_doubled_not_dropped():
    """O'Brien has to survive the trip, or the INSERT is a syntax error."""
    assert sql_builder.sql_literal("O'Brien") == "'O''Brien'"


def test_a_missing_value_becomes_null_not_the_text_nan():
    assert sql_builder.sql_literal(np.nan) == "NULL"
    assert sql_builder.sql_literal(None) == "NULL"


def test_a_float_is_written_unquoted():
    assert sql_builder.sql_literal(9.5) == "9.5"


def test_text_is_quoted():
    assert sql_builder.sql_literal("hello") == "'hello'"


# --- CREATE TABLE ------------------------------------------------------

def test_create_table_lists_each_column_with_its_type():
    sql = sql_builder.create_table("people", [("id", "INT"), ("name", "VARCHAR(255)")])
    assert sql == (
        "CREATE TABLE people (\n"
        "    id INT,\n"
        "    name VARCHAR(255)\n"
        ");"
    )


def test_a_column_with_no_chosen_type_falls_back_to_varchar():
    df = pd.DataFrame({"a": [1], "b": [2]})
    create = sql_builder.build(df, ["a", "b"], column_types={"a": "INT"})[0]
    assert "a INT" in create
    assert f"b {sql_builder.DEFAULT_TYPE}" in create


def test_renaming_a_column_renames_it_in_both_statements():
    df = pd.DataFrame({"old": ["x"]})
    create, insert = sql_builder.build(df, ["old"], renames={"old": "new"})
    assert "new VARCHAR(255)" in create
    assert "(new)" in insert
    assert "old" not in create
    assert "old" not in insert


def test_a_type_is_looked_up_by_the_new_name():
    """HeaderEditWindow.get_column_types keys its result on the new header,
    so build has to resolve the rename before the type."""
    df = pd.DataFrame({"old": [1]})
    create = sql_builder.build(
        df, ["old"], renames={"old": "new"}, column_types={"new": "INT"})[0]
    assert "new INT" in create


# --- INSERT ------------------------------------------------------------

def test_the_create_table_comes_first():
    df = pd.DataFrame({"a": ["x"]})
    statements = sql_builder.build(df, ["a"])
    assert statements[0].startswith("CREATE TABLE")
    assert all(s.startswith("INSERT INTO") for s in statements[1:])


def test_rows_are_batched_so_one_statement_never_carries_a_whole_csv():
    df = pd.DataFrame({"a": [f"r{i}" for i in range(120)]})
    inserts = sql_builder.build(df, ["a"])[1:]
    assert len(inserts) == 3
    assert [s.count("('r") for s in inserts] == [50, 50, 20]


def test_every_statement_is_terminated():
    df = pd.DataFrame({"a": ["x"], "b": ["y"]})
    for statement in sql_builder.build(df, ["a", "b"]):
        assert statement.endswith(";")


def test_an_empty_frame_yields_the_table_and_no_inserts():
    df = pd.DataFrame({"a": []})
    assert len(sql_builder.build(df, ["a"])) == 1


def test_values_keep_the_column_order_of_headers():
    df = pd.DataFrame({"a": ["first"], "b": ["second"]})
    insert = sql_builder.build(df, ["a", "b"])[1]
    assert insert.endswith("('first', 'second');")


# --- numbers and booleans out of pandas --------------------------------
# A DataFrame hands back numpy scalars, not Python ones, and np.int64 is not
# an int as far as isinstance is concerned.

@pytest.mark.parametrize("value, expected", [
    (np.int64(5), "5"),
    (np.int64(0), "0"),          # a zero is a value, not a missing one
    (np.int64(-3), "-3"),
    (np.float64(9.5), "9.5"),
    (np.float64(0.0), "0.0"),
    (5, "5"),
    (0, "0"),
])
def test_a_number_is_written_unquoted_whatever_type_carries_it(value, expected):
    assert sql_builder.sql_literal(value) == expected


@pytest.mark.parametrize("value, expected", [
    (np.bool_(True), "TRUE"),
    (np.bool_(False), "FALSE"),
    (True, "TRUE"),
    (False, "FALSE"),
])
def test_a_boolean_becomes_a_sql_boolean(value, expected):
    assert sql_builder.sql_literal(value) == expected


def test_an_empty_field_is_still_null():
    """Unchanged: an empty CSV cell means no value."""
    assert sql_builder.sql_literal("") == "NULL"


def test_a_zero_in_an_int_column_survives_a_whole_frame():
    df = pd.DataFrame({"qty": [0, 5], "flag": [False, True]})
    insert = sql_builder.build(df, ["qty", "flag"])[1]
    assert "(0, FALSE)" in insert
    assert "(5, TRUE)" in insert
    assert "NULL" not in insert


def test_the_generated_script_runs_on_sqlite_and_round_trips():
    """The end the tool exists for: the SQL has to execute and give the data
    back."""
    import sqlite3

    df = pd.DataFrame({
        "id": [1, 0, -3],
        "price": [9.5, 0.0, 3.25],
        "name": ["a", "O'Brien", "zero below"],
        "flag": [True, False, True],
    })
    headers = list(df.columns)
    types = {"id": "INT", "price": "FLOAT", "name": "VARCHAR(255)", "flag": "BOOLEAN"}
    script = "\n".join(sql_builder.build(df, headers, column_types=types))

    conn = sqlite3.connect(":memory:")
    conn.executescript(script)
    rows = conn.execute("SELECT id, price, name, flag FROM table_name").fetchall()
    conn.close()

    assert rows == [
        (1, 9.5, "a", 1),
        (0, 0.0, "O'Brien", 0),
        (-3, 3.25, "zero below", 1),
    ]
