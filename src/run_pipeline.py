"""Lancement unique : python -m src.run_pipeline

Couches du cours : Bronze (data/raw, CSV bruts) -> Silver (data/clean, nettoyé). Le journal des règles
(id, règle, action, lignes touchées) est écrit dans reports/data_quality_rules.csv.
"""

from __future__ import annotations

from src import config
from src.clean_loss_rate import clean_loss_rate
from src.clean_price import clean_price
from src.clean_product import clean_product
from src.clean_transaction import clean_transaction
from src.common import RuleLog, file_has_bom, read_csv


def main() -> None:
    config.CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    log = RuleLog()

    print("1/3 Lecture des CSV bruts (data/raw)")
    transaction_raw = read_csv(config.RAW_DIR / "transaction.csv")
    price_raw = read_csv(config.RAW_DIR / "price.csv")
    product_raw = read_csv(config.RAW_DIR / "product.csv")
    loss_path = config.RAW_DIR / "loss_rate.csv"
    loss_raw = read_csv(loss_path, dtype={"Loss Rate (%)": str})

    print("2/3 Nettoyage (règles T, P, R, L)")
    transaction = clean_transaction(transaction_raw, log)
    price = clean_price(price_raw, log)
    product = clean_product(product_raw, log)  # avant loss_rate : il fournit la catégorie de chaque article
    loss_rate = clean_loss_rate(loss_raw, product, log, had_bom=file_has_bom(loss_path))

    print("3/3 Écriture de data/clean et du journal des règles")
    tables = {"transaction": transaction, "price": price, "product": product, "loss_rate": loss_rate}
    for name, table in tables.items():
        table.to_csv(config.CLEAN_DIR / f"{name}.csv", index=False)
    rules = log.to_frame()
    rules.to_csv(config.REPORTS_DIR / "data_quality_rules.csv", index=False, encoding="utf-8")
    print(rules.to_string(index=False))
    print(f"OK : {len(transaction)} lignes de caisse nettoyées ({len(transaction_raw) - len(transaction)} supprimées).")


if __name__ == "__main__":
    main()
