"""Tests des règles P1 à P6."""

import pandas as pd

from src.clean_price import (
    apply_types,
    clean_price,
    impute_missing_prices,
    keep_one_price_per_day,
    local_median,
    mark_isolated_spikes_missing,
    mark_tiny_prices_missing,
)
from src.common import RuleLog


def prices(values, item="A"):
    dates = pd.date_range("2022-01-01", periods=len(values))
    return pd.DataFrame({"date": dates, "item_code": item, "wholesale_price": values, "is_wholesale_imputed": False})


def test_p1_types_item_code_stays_text():
    raw = pd.DataFrame({"Date": ["2022-01-01"], "Item Code": ["102900005115168"], "Wholesale Price (RMB/kg)": ["abc"]})
    log = RuleLog()
    df = apply_types(raw, log)
    assert df.loc[0, "item_code"] == "102900005115168" and pd.isna(df.loc[0, "wholesale_price"])
    assert log.count("P1") == 1


def test_p3_one_price_per_date_and_item():
    df = prices([4.0, 4.0])
    df.loc[1, "date"] = df.loc[0, "date"]
    log = RuleLog()
    assert len(keep_one_price_per_day(df, log)) == 1 and log.count("P3") == 1


def test_p4_price_below_five_centimes_becomes_missing():
    log = RuleLog()
    out = mark_tiny_prices_missing(prices([4.0, 0.01, 4.0]), log)
    assert out["wholesale_price"].isna().tolist() == [False, True, False]
    assert log.count("P4") == 1 and out.loc[1, "is_wholesale_imputed"]


def test_p5_isolated_spike_and_dip_are_missing_but_season_is_kept():
    values = [4.0] * 7 + [40.0] + [4.0] * 7 + [1.0] + [4.0] * 7
    log = RuleLog()
    out = mark_isolated_spikes_missing(prices(values), log)
    assert out["wholesale_price"].isna().sum() == 2 and log.count("P5") == 2
    seasonal = prices([2.0 + 0.2 * i for i in range(30)])  # hausse progressive = vraie saison
    assert mark_isolated_spikes_missing(seasonal, RuleLog())["wholesale_price"].notna().all()


def test_p5_needs_at_least_five_observations():
    out = mark_isolated_spikes_missing(prices([4.0, 40.0, 4.0]), RuleLog())
    assert out["wholesale_price"].notna().all()


def test_p6_imputes_with_local_median_not_mean():
    values = [4.0, 4.0, 4.0, 4.0, 4.0, float("nan"), 100.0, 4.0, 4.0, 4.0, 4.0]
    log = RuleLog()
    out = impute_missing_prices(prices(values), log)
    assert out.loc[5, "wholesale_price"] == 4.0  # médiane, pas la moyenne (tirée par le 100)
    assert out.loc[5, "is_wholesale_imputed"] and log.count("P6") == 1


def test_p6_falls_back_to_item_median_when_window_too_small():
    out = impute_missing_prices(prices([3.0, float("nan"), 5.0]), RuleLog())
    assert out.loc[1, "wholesale_price"] == 4.0


def test_local_median_keeps_original_index_order():
    df = prices([1.0] * 6).sample(frac=1, random_state=1)
    assert local_median(df).index.equals(df.index)


def test_full_price_cleaning_has_no_missing_left():
    raw = pd.DataFrame(
        {
            "Date": pd.date_range("2022-01-01", periods=10).astype(str),
            "Item Code": "A",
            "Wholesale Price (RMB/kg)": [4, 4, 4, 4, 0.01, 4, 4, 4, 4, 4],
        }
    )
    out = clean_price(raw, RuleLog())
    assert out["wholesale_price"].notna().all() and out["is_wholesale_imputed"].sum() == 1
