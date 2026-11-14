# CLAUDE.md : mémoire du projet

Projet de rattrapage Data Analytics (M2 MSc AI Applied to Business, Eugenia School). Ventes de produits frais
(RMB, kg), juillet 2020 → juin 2023. L'auteure doit pouvoir expliquer chaque choix à l'oral.

## Règle d'or
**Chaque choix de nettoyage est justifié par une logique métier**, et documenté en 4 points :
(a) problème constaté + exemple chiffré, (b) règle exacte, (c) justification métier, (d) corrigé / signalé / supprimé.
Cette explication va dans la docstring, dans `docs/regles-de-nettoyage.md` et dans le journal des règles.
Aucun seuil « au feeling » : tout seuil est dans `src/config.py`, avec la mesure qui le justifie.

## Philosophie
Corriger l'impossible ; signaler et conserver l'inhabituel mais plausible (colonnes `is_*`) ; supprimer en dernier recours.
Imputation par la **médiane**, jamais la moyenne. Les codes article sont du **texte**.

## Commandes
- `pip install -r requirements.txt` (+ `requirements-hyper.txt` pour le .hyper, optionnel)
- `python -m src.run_pipeline` : tout le pipeline (data/raw → data/clean → data/gold → reports/ → tableau/)
- `ruff check .` (line-length 120) et `pytest`

## Conventions
Noms explicites, fonctions courtes, pas de magie. Un fichier de tests par module, une règle = au moins un test.
Git : `feature/<sujet>` depuis `dev`, `merge --no-ff`, messages en anglais à l'impératif. `data/` est ignoré.
Rien n'est poussé sur GitHub sans accord explicite.

## Honnêteté
Pas d'accès à Tableau Desktop : on prépare données + guide, on ne fabrique jamais de .twb et on ne dit jamais
« dashboard terminé ».
