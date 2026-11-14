"""Tests des règles R1 à R5."""
import pandas as pd

from src.clean_product import (
    apply_types,
    clean_product,
    drop_duplicate_keys,
    fill_missing_category,
    flag_duplicated_names,
    normalize_category_names,
)
from src.common import RuleLog


def products(rows):
    return pd.DataFrame(rows, columns=["item_code", "item_name", "category_code", "category_name"])


def test_r1_codes_are_text():
    raw = pd.DataFrame({"Item Code": [" 102900005115168"], "Item Name": ["A"], "Category Code": ["1011"],
                        "Category Name": ["X"]})
    log = RuleLog()
    out = apply_types(raw, log)
    assert out.loc[0, "item_code"] == "102900005115168" and log.count("R1") == 1


def test_r2_nbsp_and_trailing_spaces_give_one_category():
    df = products([("1", "A", "10", "Flower/Leaf Vegetables"), ("2", "B", "10", "Flower/Leaf Vegetables "),
                   ("3", "C", "11", "Cabbage")])
    log = RuleLog()
    out = normalize_category_names(df, log)
    assert out["category_name"].nunique() == 2 and log.count("R2") == 2


def test_r3_duplicate_key_removed():
    df = products([("1", "A", "10", "X"), ("1", "A2", "10", "X")])
    log = RuleLog()
    assert len(drop_duplicate_keys(df, log)) == 1 and log.count("R3") == 1


def test_r4_missing_category_becomes_unknown():
    df = products([("1", "A", "10", None), ("2", "B", "10", "  "), ("3", "C", "10", "X")])
    out = fill_missing_category(df, RuleLog())
    assert out["category_name"].tolist() == ["Unknown", "Unknown", "X"]


def test_r5_duplicated_name_is_flagged_not_merged():
    df = products([("1", "Eggplant", "10", "X"), ("2", "Eggplant", "10", "X"), ("3", "Leek", "10", "X")])
    log = RuleLog()
    out = flag_duplicated_names(df, log)
    assert len(out) == 3 and out["is_name_duplicated"].tolist() == [True, True, False] and log.count("R5") == 2


def test_full_product_cleaning():
    raw = pd.DataFrame({"Item Code": ["1", "2"], "Item Name": ["A", "B"], "Category Code": ["10", "10"],
                        "Category Name": ["X Y", "X Y"]})
    out = clean_product(raw, RuleLog())
    assert out["category_name"].nunique() == 1
