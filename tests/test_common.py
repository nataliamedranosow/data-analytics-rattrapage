"""Tests des fonctions partagées."""

import pandas as pd

from src.common import RuleLog, file_has_bom, iqr_bounds, read_csv


def test_iqr_bounds_follow_the_course_formula():
    values = pd.Series([1, 2, 3, 4, 5, 6, 7, 8])  # Q1 = 2,75 ; Q3 = 6,25 ; IQR = 3,5
    low, high = iqr_bounds(values)
    assert low == 2.75 - 1.5 * 3.5 and high == 6.25 + 1.5 * 3.5


def test_rule_log_counts_rows_per_rule():
    log = RuleLog()
    log.add("T1", "transaction", "règle", "corrigé", 3)
    log.add("T1", "transaction", "règle", "corrigé", 2)
    assert log.count("T1") == 5 and list(log.to_frame().columns) == RuleLog.COLUMNS


def test_read_csv_strips_bom_and_keeps_item_code_as_text(tmp_path):
    path = tmp_path / "x.csv"
    path.write_bytes("﻿Item Code,Value\n102900005115168,1\n".encode("utf-8"))
    df = read_csv(path)
    assert file_has_bom(path) and list(df.columns) == ["Item Code", "Value"]
    assert df.loc[0, "Item Code"] == "102900005115168"
