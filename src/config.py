"""Chemins et seuils du projet.

Tous les seuils ont un nom explicite et sont justifiés dans docs/regles-de-nettoyage.md.
Un seuil n'est jamais écrit « en dur » dans le code de nettoyage.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
CLEAN_DIR = ROOT / "data" / "clean"
GOLD_DIR = ROOT / "data" / "gold"
REPORTS_DIR = ROOT / "reports"
TABLEAU_DIR = ROOT / "tableau"
IMG_DIR = ROOT / "docs" / "img"

# --- Transactions -----------------------------------------------------------------------------
MAX_QTY_KG_PER_LINE = 50  # T5 : une ligne de caisse de produit frais pèse ~1 kg (médiane 0,44 kg)
PRICE_SPIKE_RATIO = 10  # T6 : prix de vente > 10 x médiane de l'article = faute de frappe
IQR_FACTOR = 1.5  # règle IQR du cours : [Q1 - 1,5 x IQR ; Q3 + 1,5 x IQR]

# --- Prix de gros -----------------------------------------------------------------------------
MIN_WHOLESALE_PRICE = 0.05  # P4 : sous 0,05 RMB/kg le prix est considéré manquant
LOCAL_WINDOW = 15  # P5 : fenêtre (en observations) centrée sur le jour
LOCAL_MIN_OBS = 5  # P5 : minimum d'observations pour calculer une médiane locale
SPIKE_FACTOR = 3  # P5 : > 3 x ou < 1/3 de la médiane locale = pic / creux isolé

# --- Taux de perte ----------------------------------------------------------------------------
LOSS_RATE_DEFAULT = 9.43  # moyenne du fichier = remplissage automatique du fournisseur
LOSS_RATE_MIN, LOSS_RATE_MAX = 0.0, 100.0

# --- Périodes d'analyse -----------------------------------------------------------------------
PERIOD_N = (pd.Timestamp("2022-07-01"), pd.Timestamp("2023-06-30"))
PERIOD_N1 = (pd.Timestamp("2021-07-01"), pd.Timestamp("2022-06-30"))
DATE_START, DATE_END = pd.Timestamp("2020-07-01"), pd.Timestamp("2023-06-30")
UNKNOWN_CATEGORY = "Unknown"
