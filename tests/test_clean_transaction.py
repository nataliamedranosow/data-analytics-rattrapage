"""Tests des règles T1 à T7 sur de petits DataFrames construits à la main."""
import pandas as pd

from src.clean_transaction import (
    apply_types,
    cap_quantity_per_line,
    clean_transaction,
    drop_exact_duplicates,
    drop_lines_without_sale,
    fix_price_typos,
    fix_quantity_sign,
    flag_quantity_outliers,
    normalize_time,
)
from src.common import RuleLog


def make_raw(**overrides):
    base = {
        "Date": ["2022-07-01"], "Time": ["09:15:07.9"], "Item Code": ["102900005115168"],
        "Quantity Sold (kilo)": [1.0], "Unit Selling Price (RMB/kg)": [5.0],
        "Sale or Return": ["Sale "], "Discount (Yes/No)": ["No"],
    }
    base.update(overrides)
    return pd.DataFrame(base)


def typed(rows):
    """Construit un DataFrame déjà typé (sortie de T1) : (date, time, item, qty, price, type, promo)."""
    cols = ["date", "time", "item_code", "quantity_kg", "unit_selling_price", "sale_or_return", "is_promo"]
    df = pd.DataFrame(rows, columns=cols)
    df["date"] = pd.to_datetime(df["date"])
    return df


def test_t1_normalize_time_pads_milliseconds():
    out = normalize_time(pd.Series(["09:15:07.9", "09:15:07", "09:15:07.924"]))
    assert out.tolist() == ["09:15:07.900", "09:15:07.000", "09:15:07.924"]


def test_t1_types_and_log():
    log = RuleLog()
    df = apply_types(make_raw(), log)
    assert df["is_promo"].dtype == bool and not df.loc[0, "is_promo"]
    assert df.loc[0, "sale_or_return"] == "sale"
    assert df.loc[0, "time"] == "09:15:07.900"
    assert log.count("T1") == 1


def test_t2_drops_missing_zero_qty_and_bad_price():
    df = typed([
        ("2022-07-01", "09:00:00.000", "A", 1.0, 5.0, "sale", False),
        ("2022-07-01", "09:00:01.000", "A", 0.0, 5.0, "sale", False),
        ("2022-07-01", "09:00:02.000", "A", 1.0, 0.0, "sale", False),
        ("2022-07-01", "09:00:03.000", "A", None, 5.0, "sale", False),
    ])
    log = RuleLog()
    out = drop_lines_without_sale(df, log)
    assert len(out) == 1 and log.count("T2") == 3


def test_t3_only_exact_duplicates_are_removed():
    same = ("2022-07-01", "09:00:00.000", "A", 1.0, 5.0, "sale", False)
    other_time = ("2022-07-01", "09:00:00.001", "A", 1.0, 5.0, "sale", False)
    log = RuleLog()
    out = drop_exact_duplicates(typed([same, same, other_time]), log)
    assert len(out) == 2 and log.count("T3") == 1


def test_t4_return_negative_sale_positive():
    df = typed([
        ("2022-07-01", "09:00:00.000", "A", 2.0, 5.0, "return", False),
        ("2022-07-01", "09:00:01.000", "A", -3.0, 5.0, "sale", False),
        ("2022-07-01", "09:00:02.000", "A", -1.0, 5.0, "return", False),
    ])
    log = RuleLog()
    out = fix_quantity_sign(df, log)
    assert out["quantity_kg"].tolist() == [-2.0, 3.0, -1.0]
    assert log.count("T4") == 2


def test_t5_quantity_above_50_replaced_by_item_median():
    rows = [("2022-07-01", f"09:00:0{i}.000", "A", q, 5.0, "sale", False) for i, q in enumerate([1.0, 2.0, 3.0, 160.0])]
    log = RuleLog()
    out = cap_quantity_per_line(typed(rows), log)
    assert out["quantity_kg"].tolist() == [1.0, 2.0, 3.0, 2.0]  # médiane de 1, 2, 3
    assert out["is_qty_corrected"].tolist() == [False, False, False, True]
    assert log.count("T5") == 1


def test_t5_keeps_return_sign():
    rows = [("2022-07-01", "09:00:00.000", "A", 1.0, 5.0, "sale", False),
            ("2022-07-01", "09:00:01.000", "A", -80.0, 5.0, "return", False)]
    out = cap_quantity_per_line(typed(rows), RuleLog())
    assert out.loc[1, "quantity_kg"] == -1.0


def test_t6_price_above_10x_median_replaced_but_small_rise_and_promo_kept():
    prices = [5.0, 5.0, 5.0, 5.0, 50.1, 12.0, 1.0]  # 50,1 > 10 x 5 ; 12 = vraie hausse ; 1.0 = promo
    rows = [("2022-07-01", f"09:00:0{i}.000", "A", 1.0, p, "sale", False) for i, p in enumerate(prices)]
    log = RuleLog()
    out = fix_price_typos(typed(rows), log)
    assert out["unit_selling_price"].tolist() == [5.0, 5.0, 5.0, 5.0, 5.0, 12.0, 1.0]
    assert log.count("T6") == 1


def test_t7_iqr_is_computed_per_item_and_rows_are_kept():
    rows = [("2022-07-01", f"09:00:{i:02d}.000", "A", q, 5.0, "sale", False)
            for i, q in enumerate([1, 1, 1, 1, 1, 1, 1, 1, 1, 9])]
    rows += [("2022-07-01", f"10:00:{i:02d}.000", "B", 9.0, 5.0, "sale", False) for i in range(10)]  # 9 = normal pour B
    log = RuleLog()
    out = flag_quantity_outliers(typed(rows), log)
    assert len(out) == 20
    assert out["is_qty_outlier"].sum() == 1 and out.loc[9, "is_qty_outlier"]
    assert log.count("T7") == 1


def test_full_pipeline_on_tiny_table():
    log = RuleLog()
    out = clean_transaction(make_raw(), log)
    assert len(out) == 1 and set(["is_qty_corrected", "is_price_corrected", "is_qty_outlier"]) <= set(out.columns)
