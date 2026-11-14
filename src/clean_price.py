"""Nettoyage de price.csv (prix de gros journalier = coût d'achat, RMB/kg).

Ordre : P1 types -> P3 un prix par (date, article) -> P4 prix < 0,05 manquant -> P5 pics/creux isolés manquants
-> P6 imputation par la médiane locale (à défaut médiane de l'article).

Pourquoi PAS une IQR globale pour P5 ? Les prix de gros suivent des saisons et des événements réels (un légume
est cher en hiver, bon marché en été). Une IQR calculée sur 3 ans « aplatirait » ces variations en les
déclarant atypiques, et on remplacerait de vrais coûts par une moyenne : la marge serait fausse. On compare donc
chaque prix à SES voisins (médiane locale) : seul un point isolé est suspect.
"""
from __future__ import annotations

import pandas as pd

from src.common import RuleLog
from src.config import LOCAL_MIN_OBS, LOCAL_WINDOW, MIN_WHOLESALE_PRICE, SPIKE_FACTOR

TABLE = "price"
RENAMES = {"Date": "date", "Item Code": "item_code", "Wholesale Price (RMB/kg)": "wholesale_price"}


def apply_types(df: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """P1 : types. Date en date, code article en texte, prix en nombre.

    (a) Constaté : le code article (15 chiffres) deviendrait un nombre flottant imprécis s'il était lu en numérique.
    (b) Règle : date -> datetime, code -> texte sans espaces, prix -> float (illisible = manquant).
    (c) Métier : le code est une clé de jointure, jamais un nombre.
    (d) Corrigé (format) : nombre de prix illisibles transformés en manquants.
    """
    df = df.rename(columns=RENAMES).copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["item_code"] = df["item_code"].astype(str).str.strip()
    numeric = pd.to_numeric(df["wholesale_price"], errors="coerce")
    unreadable = int((numeric.isna() & df["wholesale_price"].notna()).sum())
    df["wholesale_price"] = numeric
    log.add("P1", TABLE, "Types : date, code article en texte, prix numérique", "corrigé (format)", unreadable)
    return df.dropna(subset=["date"]).copy()


def keep_one_price_per_day(df: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """P3 : un seul prix de gros par (date, article).

    (a) Constaté : 0 doublon de clé ici ; la règle protège la jointure avec les ventes.
    (b) Règle : si une clé (date, article) apparaît plusieurs fois, on garde la dernière ligne.
    (c) Métier : deux prix pour le même jour dupliqueraient les lignes de caisse lors de la jointure (CA gonflé).
    (d) Supprimé.
    """
    dup = df.duplicated(subset=["date", "item_code"], keep="last")
    log.add("P3", TABLE, "Doublon de clé (date, article)", "supprimé", int(dup.sum()))
    return df[~dup].copy()


def mark_tiny_prices_missing(df: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """P4 : prix de gros < 0,05 RMB/kg considéré manquant.

    (a) Constaté : 36 prix entre 0,01 et 0,05 RMB/kg alors que la médiane du fichier est 4,63 RMB/kg.
    (b) Règle : prix < 0,05 -> manquant (NaN), imputé ensuite par P6.
    (c) Métier : un légume ne s'achète pas 1 centime le kilo ; garder ce coût ferait une marge de ~100 %.
    (d) Corrigé (via manquant -> P6).
    """
    df = df.copy()
    tiny = df["wholesale_price"] < MIN_WHOLESALE_PRICE
    df["is_wholesale_imputed"] = tiny
    df.loc[tiny, "wholesale_price"] = float("nan")
    log.add("P4", TABLE, f"Prix de gros < {MIN_WHOLESALE_PRICE} RMB/kg", "manquant puis imputé (P6)", int(tiny.sum()))
    return df


def local_median(df: pd.DataFrame) -> pd.Series:
    """Médiane locale : fenêtre de 15 observations centrée sur le jour, au moins 5 valeurs connues, par article."""
    original_index = df.index
    ordered = df.sort_values(["item_code", "date"])
    medians = ordered.groupby("item_code")["wholesale_price"].transform(
        lambda s: s.rolling(LOCAL_WINDOW, center=True, min_periods=LOCAL_MIN_OBS).median()
    )
    return medians.reindex(original_index)


def mark_isolated_spikes_missing(df: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """P5 : pics et creux isolés.

    (a) Constaté : le 27/11/2022 l'article 102900005116943 est à 0,05 RMB/kg alors que ses voisins sont à
        ~9,11 (médiane locale) ; au total 299 points sortent de [médiane locale / 3 ; 3 x médiane locale]
        (264 creux, 35 pics). Un prix de 141 RMB/kg (11/01/2023) est conservé : ses voisins sont aussi élevés.
    (b) Règle : prix > 3 x médiane locale, ou < 1/3 de la médiane locale (fenêtre 15 obs., min. 5) -> manquant.
    (c) Métier : une vraie saison fait monter les prix progressivement (les voisins suivent) ; un point isolé
        qui saute x3 est une erreur de saisie. Pas d'IQR globale (voir en-tête du module).
    (d) Corrigé (via manquant -> P6).
    """
    df = df.copy()
    med = local_median(df)
    spike = (df["wholesale_price"] > SPIKE_FACTOR * med) | (df["wholesale_price"] < med / SPIKE_FACTOR)
    df.loc[spike.fillna(False), "wholesale_price"] = float("nan")
    df["is_wholesale_imputed"] = df["is_wholesale_imputed"] | spike.fillna(False)
    log.add("P5", TABLE, f"Pic/creux isolé (> {SPIKE_FACTOR} x ou < 1/{SPIKE_FACTOR} de la médiane locale)",
            "manquant puis imputé (P6)", int(spike.fillna(False).sum()))
    return df


def impute_missing_prices(df: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """P6 : prix manquants remplacés par la médiane locale de l'article, à défaut la médiane de l'article.

    (a) Constaté : 335 prix manquants après P4 et P5 (36 + 299).
    (b) Règle : médiane locale (15 obs. centrées) ; si trop peu de voisins, médiane de l'article. Jamais la moyenne.
    (c) Métier : la médiane n'est pas tirée par les valeurs extrêmes ; le prix local respecte la saison.
    (d) Corrigé + drapeau is_wholesale_imputed (le prix reste identifiable comme estimé).
    """
    df = df.copy()
    missing = df["wholesale_price"].isna()
    med_local = local_median(df)
    med_item = df.groupby("item_code")["wholesale_price"].transform("median")
    df.loc[missing, "wholesale_price"] = med_local[missing].fillna(med_item[missing])
    df["is_wholesale_imputed"] = df["is_wholesale_imputed"] | missing
    log.add("P6", TABLE, "Prix manquant -> médiane locale, sinon médiane de l'article", "corrigé (imputed_median)",
            int(missing.sum()))
    return df


def clean_price(raw: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """Enchaîne P1 à P6 et renvoie la table propre (1 ligne par date x article)."""
    df = apply_types(raw, log)
    df = keep_one_price_per_day(df, log)
    df = mark_tiny_prices_missing(df, log)
    df = mark_isolated_spikes_missing(df, log)
    df = impute_missing_prices(df, log)
    return df.sort_values(["date", "item_code"]).reset_index(drop=True)
