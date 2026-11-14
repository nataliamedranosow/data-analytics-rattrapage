"""Nettoyage de loss_rate.csv (un taux de perte par article, sans date).

Règles : L1 types (BOM, espaces) -> L2 taux hors [0 ; 100] manquant -> L3 valeur « par défaut » signalée
-> L4 taux à 0 % / manquants remplacés par la médiane de la catégorie -> L5 taux atypiques (IQR par catégorie) signalés.
Statuts (loss_rate_status) : reported (valeur du fichier), default_value (9,43 %, conservée), imputed_median.
"""

from __future__ import annotations

import pandas as pd

from src.common import RuleLog, iqr_bounds
from src.config import LOSS_RATE_DEFAULT, LOSS_RATE_MAX, LOSS_RATE_MIN, UNKNOWN_CATEGORY

TABLE = "loss_rate"
RENAMES = {"Item Code": "item_code", "Item Name": "item_name", "Loss Rate (%)": "loss_rate_pct"}


def apply_types(df: pd.DataFrame, log: RuleLog, had_bom: bool = False) -> pd.DataFrame:
    """L1 : caractère invisible (BOM) devant « Item Code » et espace final dans le taux (« 4.39 »).

    (a) Constaté : sans lecture utf-8-sig, la colonne s'appelle « \\ufeffItem Code » et la jointure échoue ;
        un taux « 4.39 » avec espace n'est pas un nombre pour certains outils.
    (b) Règle : lecture utf-8-sig, taux nettoyé (strip) puis converti en nombre (illisible -> manquant).
    (c) Métier : sans cela, les 251 taux de perte ne se rattacheraient à aucun article.
    (d) Corrigé (format) : le BOM compte pour 1 (fichier), plus chaque taux avec espace parasite.
    """
    df = df.rename(columns=RENAMES).copy()
    raw_rate = df["loss_rate_pct"].astype(str)
    stripped = raw_rate.str.strip()
    df["loss_rate_pct"] = pd.to_numeric(stripped, errors="coerce")
    df["item_code"] = df["item_code"].astype(str).str.strip()
    log.add(
        "L1",
        TABLE,
        "BOM devant Item Code et espaces dans le taux",
        "corrigé (format)",
        int(had_bom) + int((raw_rate != stripped).sum()),
    )
    return df


def mark_out_of_range_missing(df: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """L2 : taux hors [0 ; 100] -> manquant.

    (a) Constaté : 0 taux hors bornes ici (min 0,00 ; max 29,25).
    (b) Règle : taux < 0 ou > 100 -> manquant, ensuite imputé par L4.
    (c) Métier : un pourcentage de perte ne peut être ni négatif ni supérieur à 100 %.
    (d) Corrigé (via manquant -> L4).
    """
    df = df.copy()
    bad = (df["loss_rate_pct"] < LOSS_RATE_MIN) | (df["loss_rate_pct"] > LOSS_RATE_MAX)
    df.loc[bad, "loss_rate_pct"] = float("nan")
    log.add(
        "L2",
        TABLE,
        f"Taux hors [{LOSS_RATE_MIN:.0f} ; {LOSS_RATE_MAX:.0f}]",
        "manquant puis imputé (L4)",
        int(bad.sum()),
    )
    return df


def flag_default_value(df: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """L3 : la valeur 9,43 % est un remplissage automatique du fournisseur.

    (a) Constaté : 85 articles sur 251 (34 %) ont exactement 9,43 %, soit la MOYENNE du fichier (9,43) : peu
        plausible que 1 article sur 3 ait la même perte à 0,01 près.
    (b) Règle : taux == 9,43 -> loss_rate_status = default_value (valeur conservée).
    (c) Métier : on ne sait pas si c'est la vraie perte ; supprimer ou remplacer ferait perdre l'information
        du fournisseur. On la garde mais on prévient le lecteur (limite à dire à l'oral).
    (d) Signalé, conservé.
    """
    df = df.copy()
    df["loss_rate_status"] = "reported"
    is_default = (df["loss_rate_pct"] - LOSS_RATE_DEFAULT).abs() < 0.005
    df.loc[is_default, "loss_rate_status"] = "default_value"
    log.add(
        "L3",
        TABLE,
        f"Taux = {LOSS_RATE_DEFAULT} % (moyenne du fichier, remplissage fournisseur)",
        "signalé (default_value)",
        int(is_default.sum()),
    )
    return df


def impute_zero_and_missing(df: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """L4 : taux à 0 % (et manquants) -> médiane des taux > 0 de la catégorie.

    (a) Constaté : 22 articles ont un taux de 0,00 %.
    (b) Règle : taux == 0 ou manquant -> médiane des taux > 0 de la catégorie (jamais la moyenne),
        loss_rate_status = imputed_median.
    (c) Métier : un produit frais a toujours de la casse (flétrissement, déchets) ; 0 % signifie « non renseigné »
        et rendrait les pertes nulles, donc la marge après pertes trop belle.
    (d) Corrigé.
    """
    df = df.copy()
    to_fix = df["loss_rate_pct"].isna() | (df["loss_rate_pct"] == 0)
    positive = df["loss_rate_pct"].where(df["loss_rate_pct"] > 0)
    category_median = positive.groupby(df["category_name"]).transform("median")
    df.loc[to_fix, "loss_rate_pct"] = category_median[to_fix].fillna(positive.median())
    df.loc[to_fix, "loss_rate_status"] = "imputed_median"
    log.add(
        "L4",
        TABLE,
        "Taux à 0 % ou manquant -> médiane des taux > 0 de la catégorie",
        "corrigé (imputed_median)",
        int(to_fix.sum()),
    )
    return df


def flag_category_outliers(df: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """L5 : taux atypiques par la règle IQR calculée par catégorie.

    (a) Constaté : la casse d'un champignon n'est pas celle d'un chou : on compare chaque taux à sa catégorie.
    (b) Règle : taux hors [Q1 - 1,5 x IQR ; Q3 + 1,5 x IQR] de sa catégorie -> is_loss_outlier = True.
    (c) Métier : un article très fragile est plausible ; on n'efface pas l'information.
    (d) Signalé, conservé.
    """
    df = df.copy()
    df["is_loss_outlier"] = False
    for _, group in df.groupby("category_name"):
        low, high = iqr_bounds(group["loss_rate_pct"])
        df.loc[group.index, "is_loss_outlier"] = (group["loss_rate_pct"] < low) | (group["loss_rate_pct"] > high)
    log.add(
        "L5", TABLE, "Taux atypique (IQR par catégorie)", "signalé (is_loss_outlier)", int(df["is_loss_outlier"].sum())
    )
    return df


def clean_loss_rate(raw: pd.DataFrame, product: pd.DataFrame, log: RuleLog, had_bom: bool = False) -> pd.DataFrame:
    """Enchaîne L1 à L5. `product` (déjà nettoyé) fournit la catégorie de chaque article."""
    df = apply_types(raw, log, had_bom)
    categories = product.set_index("item_code")["category_name"]
    df["category_name"] = df["item_code"].map(categories).fillna(UNKNOWN_CATEGORY)
    df = mark_out_of_range_missing(df, log)
    df = flag_default_value(df, log)
    df = impute_zero_and_missing(df, log)
    df = flag_category_outliers(df, log)
    return df.reset_index(drop=True)
