"""Fonctions partagées : lecture des CSV, journal des règles, règle IQR."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import IQR_FACTOR


def read_csv(path: Path) -> pd.DataFrame:
    """Lit un CSV brut.

    - utf-8-sig : retire le BOM (caractère invisible) qui colle au nom de la 1re colonne ;
    - Item Code en texte : c'est une clé de 15 chiffres, pas un nombre (on ne l'additionne jamais).
    """
    return pd.read_csv(path, encoding="utf-8-sig", dtype={"Item Code": str})


def iqr_bounds(values: pd.Series, factor: float = IQR_FACTOR) -> tuple[float, float]:
    """Bornes de la règle IQR du cours : Q1 - k x IQR et Q3 + k x IQR."""
    q1, q3 = values.quantile(0.25), values.quantile(0.75)
    iqr = q3 - q1
    return q1 - factor * iqr, q3 + factor * iqr


class RuleLog:
    """Journal des règles : une ligne par règle (id, table, règle, action, lignes touchées)."""

    COLUMNS = ["rule_id", "table", "rule", "action", "rows_touched"]

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, rule_id: str, table: str, rule: str, action: str, rows_touched: int) -> None:
        self.rows.append(
            {"rule_id": rule_id, "table": table, "rule": rule, "action": action, "rows_touched": int(rows_touched)}
        )

    def count(self, rule_id: str) -> int:
        return sum(r["rows_touched"] for r in self.rows if r["rule_id"] == rule_id)

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows, columns=self.COLUMNS)
