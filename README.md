# Nettoyage des 4 fichiers de ventes de produits frais

Rattrapage Data Analytics (M2 MSc AI Applied to Business, Eugenia School). Code qui nettoie les 4 CSV d'un supermarché
(ventes de légumes au kilo, RMB, juillet 2020 → juin 2023) : `transaction.csv`, `price.csv`, `product.csv`, `loss_rate.csv`.
Les fichiers sont reliés par le code article (`Item Code`, **texte** de 15 chiffres).

## Lancer

Les CSV bruts vont dans `data/raw/` (ils ne sont pas dans git).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m src.run_pipeline
ruff format --check . && ruff check . && pytest
```

Le pipeline suit les couches du cours : **Bronze** `data/raw/` (bruts) → **Silver** `data/clean/` (nettoyés). Il écrit aussi le
journal des règles `reports/data_quality_rules.csv` (id, règle, action, lignes touchées).

## Philosophie

**Corriger** une valeur impossible ; **signaler et conserver** une valeur inhabituelle mais plausible (colonnes `is_*`) ;
**supprimer** en dernier recours (supprimer des ventes réelles fausserait le CA). Imputation par la **médiane**, jamais la
moyenne. La règle IQR (Q1 − 1,5 × IQR ; Q3 + 1,5 × IQR) sert à détecter ; la décision de corriger dépend du sens métier.

**Chaque règle est justifiée par une logique métier** dans la docstring de sa fonction : (a) problème constaté, (b) règle
exacte, (c) justification métier, (d) corrigé / signalé / supprimé. Chaque règle a au moins un test.

## Règles par fichier

| Fichier | Module | Règles | Lignes touchées |
|---|---|---|---|
| `transaction.csv` | `src/clean_transaction.py` | T1 types · T2 lignes sans vente · T3 doublons exacts (à la milliseconde) · T4 signe des retours · T5 plafond 50 kg · T6 prix > 10 × médiane · T7 quantités atypiques (IQR par article) | 18 841 · 0 · 0 · 0 · 1 · 2 · 26 370 |
| `price.csv` | `src/clean_price.py` | P1 types · P3 un prix par (date, article) · P4 prix < 0,05 · P5 pics/creux isolés (médiane locale, fenêtre 15) · P6 imputation médiane locale | 0 · 0 · 36 · 299 · 335 |
| `product.csv` | `src/clean_product.py` | R1 codes en texte · R2 noms de catégorie (espaces insécables) · R3 doublons de clé · R4 catégorie manquante · R5 noms dupliqués | 0 · 100 · 0 · 0 · 8 |
| `loss_rate.csv` | `src/clean_loss_rate.py` | L1 BOM et espaces · L2 taux hors [0 ; 100] · L3 valeur par défaut 9,43 % (signalée) · L4 taux à 0 % (médiane de la catégorie) · L5 atypiques (IQR par catégorie) | 252 · 0 · 85 · 22 · 40 |

Tous les seuils sont dans `src/config.py`. Aucune ligne de caisse n'est supprimée (878 503 lignes en entrée et en sortie).

## Structure

```text
src/    config.py (chemins, seuils nommés), common.py, clean_transaction.py, clean_price.py,
        clean_product.py, clean_loss_rate.py, run_pipeline.py
tests/  un fichier de tests par module (pytest) : petits DataFrames construits à la main
data/   raw/ (bronze) · clean/ (silver), ignorés par git
.github/workflows/ci.yml   ruff (format + lint) et pytest
```

## Stratégie Git

- `main` : version livrable (tag `v1.0.0`) ; `dev` : intégration ; `feature/<sujet>` : un sujet par branche, créée depuis `dev`
  (`clean-transaction`, `clean-price`, `clean-product`, `clean-loss-rate`, `pipeline`, `readme`).
- Petits commits (code, tests), messages en anglais à l'impératif ; fusions `git merge --no-ff` pour garder la trace des
  branches (`git log --graph --oneline --all`). `dev` est fusionnée dans `main` quand ruff, pytest et le pipeline sont verts.
