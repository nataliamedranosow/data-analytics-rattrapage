"""Tests des règles L1 à L5."""
import pandas as pd

from src.clean_loss_rate import (
    apply_types,
    clean_loss_rate,
    flag_category_outliers,
    flag_default_value,
    impute_zero_and_missing,
    mark_out_of_range_missing,
)
from src.common import RuleLog


def rates(values, category="X"):
    n = len(values)
    return pd.DataFrame({"item_code": [str(i) for i in range(n)], "item_name": "n", "loss_rate_pct": values,
                         "category_name": category, "loss_rate_status": "reported"})


def test_l1_trailing_space_and_bom_are_cleaned():
    raw = pd.DataFrame({"Item Code": ["1"], "Item Name": ["A"], "Loss Rate (%)": ["4.39 "]})
    log = RuleLog()
    out = apply_types(raw, log, had_bom=True)
    assert out.loc[0, "loss_rate_pct"] == 4.39 and log.count("L1") == 2


def test_l2_out_of_range_becomes_missing():
    log = RuleLog()
    out = mark_out_of_range_missing(rates([5.0, -1.0, 150.0]), log)
    assert out["loss_rate_pct"].isna().tolist() == [False, True, True] and log.count("L2") == 2


def test_l3_default_value_is_flagged_and_kept():
    log = RuleLog()
    out = flag_default_value(rates([9.43, 5.0]), log)
    assert out["loss_rate_status"].tolist() == ["default_value", "reported"]
    assert out["loss_rate_pct"].tolist() == [9.43, 5.0] and log.count("L3") == 1


def test_l4_zero_and_missing_use_category_median_of_positive_rates():
    df = rates([0.0, 4.0, 6.0, 100.0, None])  # médiane des > 0 = 6 ; la moyenne vaudrait 36.7
    log = RuleLog()
    out = impute_zero_and_missing(df, log)
    assert out.loc[0, "loss_rate_pct"] == 6.0 and out.loc[4, "loss_rate_pct"] == 6.0
    assert out.loc[0, "loss_rate_status"] == "imputed_median" and log.count("L4") == 2


def test_l4_uses_each_category_median():
    df = pd.concat([rates([0.0, 2.0, 4.0], "A"), rates([0.0, 20.0, 40.0], "B")], ignore_index=True)
    out = impute_zero_and_missing(df, RuleLog())
    assert out.loc[0, "loss_rate_pct"] == 3.0 and out.loc[3, "loss_rate_pct"] == 30.0


def test_l5_outlier_per_category_is_flagged_and_kept():
    df = pd.concat([rates([5.0, 5.1, 5.2, 5.3, 5.4, 30.0], "A"), rates([30.0, 31.0, 32.0, 33.0, 34.0], "B")],
                   ignore_index=True)
    log = RuleLog()
    out = flag_category_outliers(df, log)
    assert len(out) == 11 and out["is_loss_outlier"].sum() == 1 and out.loc[5, "is_loss_outlier"]
    assert log.count("L5") == 1


def test_full_loss_rate_cleaning_joins_category():
    raw = pd.DataFrame({"Item Code": ["1", "2", "3"], "Item Name": "n", "Loss Rate (%)": ["0.00 ", "5.00 ", "7.00 "]})
    product = pd.DataFrame({"item_code": ["1", "2", "3"], "category_name": ["C", "C", "C"]})
    out = clean_loss_rate(raw, product, RuleLog())
    assert out.loc[0, "loss_rate_pct"] == 6.0 and out["category_name"].eq("C").all()
