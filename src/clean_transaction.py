"""Nettoyage de transaction.csv (une ligne = une ligne de caisse).

Chaque règle suit le même plan : (a) problème constaté, (b) règle exacte, (c) justification métier, (d) action.
Ordre d'application : T1 types -> T2 lignes sans vente -> T3 doublons -> T4 signe -> T5 plafond de quantité
-> T6 prix aberrants -> T7 quantités atypiques (signalement).
"""
from __future__ import annotations

import pandas as pd

from src.common import RuleLog
from src.config import IQR_FACTOR, MAX_QTY_KG_PER_LINE, PRICE_SPIKE_RATIO

TABLE = "transaction"
RENAMES = {
    "Date": "date",
    "Time": "time",
    "Item Code": "item_code",
    "Quantity Sold (kilo)": "quantity_kg",
    "Unit Selling Price (RMB/kg)": "unit_selling_price",
    "Sale or Return": "sale_or_return",
    "Discount (Yes/No)": "is_promo",
}


def normalize_time(times: pd.Series) -> pd.Series:
    """Heure au format fixe HH:MM:SS.mmm (3 décimales).

    (a) Constaté : 18 841 heures sur 878 503 n'ont pas 3 décimales (« 09:15:07.9 » ou « 09:15:07 »).
    (b) Règle : compléter les millisecondes à droite par des zéros (« .9 » -> « .900 »).
    (c) Métier : la milliseconde sert à repérer les vrais doublons (T3) ; un format homogène évite
        de croire que deux lignes sont différentes à cause de leur écriture.
    (d) Corrigé (format uniquement, aucune ligne perdue).
    """
    parts = times.astype(str).str.strip().str.split(".", n=1, expand=True)
    millis = parts[1].fillna("0").str.ljust(3, "0").str[:3] if parts.shape[1] > 1 else "000"
    return parts[0] + "." + millis


def apply_types(df: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """T1 : types. Date en date, Discount Yes/No en booléen, heure à 3 décimales, sale/return en minuscules."""
    df = df.rename(columns=RENAMES).copy()
    raw_time = df["time"].astype(str)
    df["time"] = normalize_time(df["time"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    raw_flag = df["is_promo"].astype(str).str.strip().str.lower()
    df["is_promo"] = raw_flag.map({"yes": True, "no": False})
    sale_type = df["sale_or_return"].astype(str).str.strip().str.lower()
    changed_type = int((sale_type != df["sale_or_return"].astype(str)).sum())
    df["sale_or_return"] = sale_type
    df["item_code"] = df["item_code"].astype(str).str.strip()
    df["quantity_kg"] = pd.to_numeric(df["quantity_kg"], errors="coerce")
    df["unit_selling_price"] = pd.to_numeric(df["unit_selling_price"], errors="coerce")
    log.add("T1", TABLE, "Types : date, booléen promo, heure à 3 décimales, sale/return en minuscules",
            "corrigé (format)", int((raw_time != df["time"]).sum()) + changed_type)
    return df


def drop_lines_without_sale(df: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """T2 : supprime les lignes qui ne sont pas une vente.

    (a) Constaté : valeurs manquantes, prix <= 0 ou quantité = 0 (ici 0 cas, mais la règle protège le pipeline).
    (b) Règle : supprimer si une colonne clé est vide, ou prix <= 0, ou quantité == 0.
    (c) Métier : une ligne sans quantité ou sans prix ne représente aucune vente : la supprimer ne change pas le CA.
    (d) Supprimé (dernier recours : seul cas où il n'y a rien à corriger).
    """
    key_cols = ["date", "time", "item_code", "quantity_kg", "unit_selling_price", "sale_or_return", "is_promo"]
    bad = df[key_cols].isna().any(axis=1) | (df["unit_selling_price"] <= 0) | (df["quantity_kg"] == 0)
    log.add("T2", TABLE, "Valeur manquante, prix <= 0 ou quantité = 0", "supprimé", int(bad.sum()))
    return df[~bad].copy()


def drop_exact_duplicates(df: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """T3 : supprime les doublons exacts (heure à la milliseconde incluse).

    (a) Constaté : un même article peut être scanné plusieurs fois le même jour : c'est normal.
    (b) Règle : toutes les colonnes identiques (date, heure ms, article, quantité, prix, type, promo).
    (c) Métier : deux scans à la même milliseconde avec les mêmes valeurs = double enregistrement du système ;
        deux scans à des heures différentes = deux clients, on garde.
    (d) Supprimé (on garde la première occurrence).
    """
    dup = df.duplicated(keep="first")
    log.add("T3", TABLE, "Doublon exact (heure à la milliseconde incluse)", "supprimé", int(dup.sum()))
    return df[~dup].copy()


def fix_quantity_sign(df: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """T4 : un retour est négatif, une vente est positive.

    (a) Constaté : le type (sale/return) et le signe de la quantité doivent être cohérents (ex. return +2,0 kg).
    (b) Règle : quantité = -|q| si return, +|q| si sale.
    (c) Métier : un retour doit réduire le CA et le volume ; un retour positif les augmenterait à tort.
    (d) Corrigé (le signe uniquement).
    """
    expected = df["quantity_kg"].abs() * df["sale_or_return"].map({"sale": 1, "return": -1})
    wrong = expected.notna() & (expected != df["quantity_kg"])
    df = df.copy()
    df.loc[expected.notna(), "quantity_kg"] = expected[expected.notna()]
    log.add("T4", TABLE, "Signe de la quantité incohérent avec sale/return", "corrigé", int(wrong.sum()))
    return df


def cap_quantity_per_line(df: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """T5 : plafond métier de 50 kg par ligne de caisse.

    (a) Constaté : médiane 0,44 kg, 99,99 % des lignes <= 7,7 kg, mais une ligne à 160 kg (9/6/2022, article
        102900011034354, prix 5,9 : impossible en caisse de supermarché).
    (b) Règle : |quantité| > 50 kg -> remplacée par la médiane de |quantité| de l'article (lignes <= 50 kg), signe conservé.
    (c) Métier : une ligne ~1 kg ne peut pas peser 160 kg (faute de saisie, ex. 1,60 -> 160) : garder ce chiffre
        gonflerait le volume. On corrige au lieu de supprimer pour ne pas perdre la vente.
    (d) Corrigé + drapeau is_qty_corrected.
    """
    df = df.copy()
    abs_qty = df["quantity_kg"].abs()
    too_big = abs_qty > MAX_QTY_KG_PER_LINE
    item_median = abs_qty.where(~too_big).groupby(df["item_code"]).transform("median")
    sign = df["quantity_kg"].map(lambda q: -1 if q < 0 else 1)
    df["is_qty_corrected"] = too_big
    df.loc[too_big, "quantity_kg"] = (item_median * sign)[too_big]
    log.add("T5", TABLE, f"|Quantité| > {MAX_QTY_KG_PER_LINE} kg par ligne", "corrigé (médiane de l'article)",
            int(too_big.sum()))
    return df


def fix_price_typos(df: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """T6 : prix de vente > 10 x la médiane de l'article.

    (a) Constaté : un prix à 100 RMB/kg pour un article dont la médiane est ~10 (virgule décalée).
        Les hausses modestes (x2, x3) existent vraiment (saisons) : sur 5 722 lignes > 3 x médiane, seules 2 dépassent 10 x.
    (b) Règle : prix > 10 x médiane de prix de l'article -> médiane de l'article.
    (c) Métier : un prix x10 est une faute de frappe, pas une vraie hausse ; il fausserait CA et marge.
        On NE corrige PAS les prix bas : une promotion est faite pour baisser le prix.
    (d) Corrigé + drapeau is_price_corrected.
    """
    df = df.copy()
    item_median = df.groupby("item_code")["unit_selling_price"].transform("median")
    typo = df["unit_selling_price"] > PRICE_SPIKE_RATIO * item_median
    df["is_price_corrected"] = typo
    df.loc[typo, "unit_selling_price"] = item_median[typo]
    log.add("T6", TABLE, f"Prix de vente > {PRICE_SPIKE_RATIO} x médiane de l'article", "corrigé (médiane de l'article)",
            int(typo.sum()))
    return df


def flag_quantity_outliers(df: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """T7 : quantités élevées par la règle IQR calculée article par article.

    (a) Constaté : un kilo de champignons n'est pas un kilo de chou ; une IQR globale mélangerait les paniers types.
    (b) Règle : par article, |q| > Q3 + 1,5 x (Q3 - Q1) -> is_qty_outlier = True.
    (c) Métier : un gros achat (restaurant, famille nombreuse) est inhabituel mais plausible : c'est du vrai CA.
    (d) Signalé, conservé (la décision de corriger relève du sens métier, ici non).
    """
    df = df.copy()
    abs_qty = df["quantity_kg"].abs()
    grouped = abs_qty.groupby(df["item_code"])
    q1, q3 = grouped.transform(lambda s: s.quantile(0.25)), grouped.transform(lambda s: s.quantile(0.75))
    upper = q3 + IQR_FACTOR * (q3 - q1)
    df["is_qty_outlier"] = abs_qty > upper
    log.add("T7", TABLE, "Quantité atypique (IQR par article, borne haute)", "signalé (is_qty_outlier)",
            int(df["is_qty_outlier"].sum()))
    return df


def clean_transaction(raw: pd.DataFrame, log: RuleLog) -> pd.DataFrame:
    """Enchaîne T1 à T7 et renvoie la table propre."""
    df = apply_types(raw, log)
    df = drop_lines_without_sale(df, log)
    df = drop_exact_duplicates(df, log)
    df = fix_quantity_sign(df, log)
    df = cap_quantity_per_line(df, log)
    df = fix_price_typos(df, log)
    df = flag_quantity_outliers(df, log)
    return df.reset_index(drop=True)
