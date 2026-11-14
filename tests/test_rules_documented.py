"""Chaque règle doit expliquer (a) problème, (b) règle, (c) justification métier, (d) action dans sa docstring."""

import inspect

import pytest

from src import clean_loss_rate, clean_price, clean_product, clean_transaction

RULES = [
    clean_transaction.apply_types,
    clean_transaction.drop_lines_without_sale,
    clean_transaction.drop_exact_duplicates,
    clean_transaction.fix_quantity_sign,
    clean_transaction.cap_quantity_per_line,
    clean_transaction.fix_price_typos,
    clean_transaction.flag_quantity_outliers,
    clean_price.apply_types,
    clean_price.keep_one_price_per_day,
    clean_price.mark_tiny_prices_missing,
    clean_price.mark_isolated_spikes_missing,
    clean_price.impute_missing_prices,
    clean_product.apply_types,
    clean_product.normalize_category_names,
    clean_product.drop_duplicate_keys,
    clean_product.fill_missing_category,
    clean_product.flag_duplicated_names,
    clean_loss_rate.apply_types,
    clean_loss_rate.mark_out_of_range_missing,
    clean_loss_rate.flag_default_value,
    clean_loss_rate.impute_zero_and_missing,
    clean_loss_rate.flag_category_outliers,
]


@pytest.mark.parametrize("function", RULES, ids=lambda f: f"{f.__module__.split('.')[-1]}.{f.__name__}")
def test_rule_docstring_has_four_points(function):
    doc = inspect.getdoc(function)
    assert doc is not None
    for marker in ["(a)", "(b)", "(c)", "(d)"]:
        assert marker in doc, f"{function.__name__} : {marker} manquant"
