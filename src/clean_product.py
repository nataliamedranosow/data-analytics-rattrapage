"""Nettoyage de product.csv (référentiel : 1 ligne par article).

Règles : R1 codes en texte -> R2 noms de catégorie normalisés -> R3 doublons de clé -> R4 catégorie manquante
-> R5 même nom pour deux codes (signalé). La clé est TOUJOURS le code article, jamais le nom.
"""
from __future__ import annotations

import pandas as pd

from src.common import RuleLog
from src.config import UNKNOWN_CATEGORY

TABLE = "product"
RENAMES = {
    "Item Code": "item_code",
    "Item Name": "item_name",
    "Category Code": "category_code",
    "Category Name": "category_name",
}


def apply_types(df: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """R1 : codes en texte.

    (a) Constaté : un code article a 15 chiffres (102900005115168) ; lu en nombre, il perd de la précision et
        ne se joint plus avec transaction.csv.
    (b) Règle : item_code et category_code en texte sans espaces autour.
    (c) Métier : un code est un identifiant, on ne l'additionne jamais.
    (d) Corrigé (format) : nombre de codes qui avaient des espaces parasites.
    """
    df = df.rename(columns=RENAMES).copy()
    touched = 0
    for col in ["item_code", "category_code"]:
        as_text = df[col].astype(str)
        touched += int((as_text != as_text.str.strip()).sum())
        df[col] = as_text.str.strip()
    log.add("R1", TABLE, "Codes article et catégorie en texte, sans espaces", "corrigé (format)", touched)
    return df


def normalize_category_names(df: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """R2 : espaces insécables et espaces de fin dans les noms de catégories.

    (a) Constaté : « Flower/Leaf\\xa0Vegetables » (espace insécable) sur 100 des 251 articles : 100 lignes touchées
        (la référence en annonçait 102, voir docs : nous n'en trouvons pas plus). Dans un filtre Tableau, la même
        catégorie apparaîtrait DEUX fois.
    (b) Règle : \\xa0 -> espace normal, espaces multiples réduits, espaces de début/fin retirés.
    (c) Métier : un filtre ou un tableau par catégorie doit montrer 6 lignes, pas 7.
    (d) Corrigé.
    """
    df = df.copy()
    raw = df["category_name"].astype("string")
    clean = raw.str.replace(" ", " ", regex=False).str.replace(r"\s+", " ", regex=True).str.strip()
    changed = int((raw != clean).fillna(False).sum())
    df["category_name"] = clean.astype(object)
    log.add("R2", TABLE, "Espaces insécables / de fin dans category_name", "corrigé", changed)
    return df


def drop_duplicate_keys(df: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """R3 : un seul article par code.

    (a) Constaté : 0 code en double ici ; la règle protège les jointures (un doublon multiplierait les ventes).
    (b) Règle : on garde la première ligne de chaque item_code.
    (c) Métier : la clé du référentiel doit être unique.
    (d) Supprimé.
    """
    dup = df.duplicated(subset="item_code", keep="first")
    log.add("R3", TABLE, "Doublon de clé item_code", "supprimé", int(dup.sum()))
    return df[~dup].copy()


def fill_missing_category(df: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """R4 : catégorie manquante -> « Unknown ».

    (a) Constaté : 0 catégorie vide ici.
    (b) Règle : vide ou manquante -> « Unknown » (on n'invente pas la catégorie).
    (c) Métier : l'article reste compté dans le total ; il apparaît à part au lieu d'être perdu dans un filtre.
    (d) Corrigé.
    """
    df = df.copy()
    missing = df["category_name"].isna() | (df["category_name"].str.strip() == "")
    df.loc[missing, "category_name"] = UNKNOWN_CATEGORY
    log.add("R4", TABLE, "Catégorie manquante", f"corrigé ({UNKNOWN_CATEGORY})", int(missing.sum()))
    return df


def flag_duplicated_names(df: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """R5 : même nom pour deux codes différents -> is_name_duplicated.

    (a) Constaté : 8 lignes partagent un nom avec un autre code (ex. deux codes « Chinese Cabbage » et deux
        codes « Broccoli »).
    (b) Règle : nom présent plus d'une fois -> True (on ne fusionne pas, on ne supprime pas).
    (c) Métier : deux codes sont deux produits différents (conditionnement, origine) ; seul le code les distingue.
        Joindre par le nom mélangerait leurs ventes.
    (d) Signalé, conservé.
    """
    df = df.copy()
    df["is_name_duplicated"] = df["item_name"].duplicated(keep=False)
    log.add("R5", TABLE, "Même nom pour plusieurs codes", "signalé (is_name_duplicated)",
            int(df["is_name_duplicated"].sum()))
    return df


def clean_product(raw: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """Enchaîne R1 à R5 et renvoie le référentiel propre."""
    df = apply_types(raw, log)
    df = normalize_category_names(df, log)
    df = drop_duplicate_keys(df, log)
    df = fill_missing_category(df, log)
    df = flag_duplicated_names(df, log)
    return df.reset_index(drop=True)
