# Classification de régime (Range vs Tendance vs Excès) — lacune comblée

**Question à l'origine de ce travail** : "est-ce que la distinction entre stratégie de range et de tendance se fait dans notre protocole ?" Réponse à ce moment-là : **non**. Aucun de nos moteurs (v4, v5) ne classait le régime de marché avant d'agir, alors que c'est la règle de base n°1 du manuel PDF officiel ("TOUJOURS TRADER DANS UN CONTEXTE", `RULES_EXTRACTION.md` section 1). Ce document corrige cette lacune (partiellement, cf. limites en fin de document).

## Classificateur construit (`code/regime_classifier.py`)
4 régimes, cohérents avec le manuel : RANGE_NEUTRE, RANGE_TENDANCIEL, TENDANCE, EXCES. Règle explicitement respectée : *"en cas de doute, toujours RANGE"* (défaut du classificateur).

**Calibration** : les seuils absolus du manuel (largeur de canal <1% = squeeze, >12% = excès) sont calibrés pour le vrai canal PRO Framework, pas pour notre approximation EMA±2×ATR (dont la largeur médiane sur crypto est ~17%, bien au-dessus de 12%). Remplacés par des **percentiles adaptatifs glissants et causaux** (fenêtre 250 bougies, sans lookahead) ciblant approximativement les mêmes fréquences relatives.

**Distribution obtenue (BTC D1)** : Range neutre 49,4% (cible manuel ~50%, très proche) / Tendance 30,5% (cible ~20%, un peu haut) / Excès 17,2% (cible ~5%, encore haut mais très amélioré vs 85% avant calibration) / Range tendanciel 2,8% (cible ~25%, trop bas — la frontière Range tendanciel/Tendance est probablement mal placée, la plupart des cas "un peu tendanciels" tombent directement en Tendance).

## Intégration dans le moteur (`code/backtest_phase2_v6.py`)
- **Aucune entrée en régime EXCES** — règle explicite du manuel, jamais respectée avant cette version
- **Pyramidalisation réservée aux régimes TENDANCE/RANGE_TENDANCIEL** — dans le manuel, le "Renforcement" n'apparaît que dans la table trade de tendance, jamais dans la table range

## Résultat (H4, comparaison avec/sans filtre de régime)

| Actif/Profil | Retour sans | Retour avec | DD sans | DD avec | Profit factor sans | Profit factor avec |
|---|---|---|---|---|---|---|
| ETH AGRESSIF | +2215,3% | +1400,9% | -22,4% | **-13,2%** | 2,25 | **2,77** |
| SOL TRÈS AGRESSIF | +23878,4% | +4431,3% | -40,4% | **-31,9%** | 2,71 | 2,84 |
| BTC MODÉRÉ | +588,1% | +333,3% | -16,7% | **-12,8%** | 2,07 | **2,20** |

Détail complet : `phase2_v6_regime_results.csv`.

**Constat cohérent sur H4** : moins de trades (exclusion des périodes d'Excès), retour cumulé plus faible (moins d'occasions de composer), mais **win rate et profit factor s'améliorent dans la quasi-totalité des cas** — signe que les trades exclus étaient réellement de moins bonne qualité, pas juste moins nombreux. Effet notable : les valeurs de retour extrêmes et suspectes (SOL +23878%) sont nettement tempérées, plus crédibles.

D1 : effet plus mitigé, échantillons très réduits (13-28 trades) — pas de conclusion fiable.

## Limites documentées (implémentation partielle, pas la solution complète)
- Seule la règle "ne pas trader en Excès" et le gate de pyramidalisation sont implémentés — **la vraie table "trade de tendance" à 5 étapes (Accumulation/Breakout/Divergence/Pull-Back/Excès final) avec son propre barème de renforcement par étape reste non implémentée**, distincte de la table range utilisée partout ailleurs dans le moteur.
- Le classificateur est une approximation (canal EMA±ATR, percentiles adaptatifs) — pas le vrai canal de contexte PRO Framework.
- La distinction Range Neutre / Range Tendanciel reste mal calibrée (2,8% au lieu de ~25% attendu) — la frontière entre les deux mériterait d'être revue.
- Résultats informatifs uniquement, conformément au principe déjà établi (`AUDIT_QUALITE_ET_CORRECTION_CYCLE.md`) : ne pas juger la validité d'une règle du corpus sur la seule base de la performance du proxy.
