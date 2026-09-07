# Phase 2 — Matrice complète (tous timeframes x tous actifs disponibles)

> ⚠️ **Document historique/supersédé** — voir `STATUS.md` et `PHASE2_V4_IMPLEMENTATION_COMPLETE.md` pour l'état actuel.

Complète `PHASE2_MONEYMANAGEMENT.md` (qui ne couvrait que H4/D1) en ajoutant M15, H1, et XRP (D1 seul, données limitées). Détail complet : `phase2_full_matrix_results.csv`. Couverture réelle des données en fin de document.

## Résultat 1 — M15 (BTC uniquement) : catastrophique sur les 4 profils, sans exception
FAIBLE/MODÉRÉ/AGRESSIF/TRÈS AGRESSIF : tous à **-100%** de retour. Confirmation encore plus nette que dans `WALKFORWARD_ANALYSIS.md` de la règle anti-scalping du manuel — même le profil le plus prudent est détruit.

## Résultat 2 — Découverte : H1 devient catastrophique avec le VRAI money management (nouveau, important)

| Actif | H1 FAIBLE (retour / DD) | H1 TRÈS AGRESSIF (retour / DD) |
|---|---|---|
| BTC | -82,9% / -87,7% | -47,9% / -81,9% |
| ETH | -81,8% / -88,8% | -72,8% / -95,4% |
| BNB | -85,6% / -89,5% | -82,6% / -95,8% |
| SOL | -59,3% / -64,3% | -83,4% / -91,4% |

Avec le modèle simple de la Phase 1 (un seul stop, une seule sortie), H1 était "instable" (-38,6% à +91% selon l'actif). Avec les vraies tables de money management (Phase 2, sorties partielles + passage au breakeven), **H1 s'effondre partout**.

**Explication** : le nombre de trades a presque doublé (ex. BTC : 2455 → 4532). Le staging Validation/Confirmation avec stop ramené au breakeven fait sortir les positions plus tôt et plus souvent qu'un stop unique. Chaque sortie précoce = un aller-retour de frais supplémentaire. Sur 4500+ trades, même 0,04%/côté s'accumule par composition et détruit le capital, indépendamment de tout edge sous-jacent.

**Enseignement généralisable** : une gestion du risque plus sophistiquée (prises de profit partielles, breakeven) augmente mécaniquement la fréquence de trading — donc l'exposition aux frais. Ce n'était pas visible avec le modèle simplifié de la Phase 1 seule.

## Résultat 3 — H4/D1 : confirmés
Résultats positifs sur les 4 profils, cohérents avec `PHASE2_MONEYMANAGEMENT.md`.

## Résultat 4 — XRP (D1 seul, 365 jours, échantillon faible : 7 à 19 trades)
Négatif sur les 4 profils (-4,3% à -22,0%), profit factor 0,00 à 0,24. Échantillon trop petit pour conclure statistiquement (7 trades pour Très Agressif) — cohérent avec le fait déjà connu (`WALKFORWARD_ANALYSIS.md`) que cette fenêtre 2025-2026 était mauvaise spécifiquement pour XRP.

## Conclusion mise à jour (renforce, ne contredit pas, les Phases 1 et 2 précédentes)
**H1 est encore plus clairement disqualifié qu'estimé initialement** — pas seulement instable, mais structurellement détruit par les frais dès qu'une vraie gestion du risque par étapes est appliquée. **H4 et D1 restent les seuls choix défendables.**

## Couverture réelle des données (rappel des limites)
| Actif | Timeframes disponibles |
|---|---|
| BTC | M15, H1, H4, D1 (2020-2026) |
| ETH, BNB, SOL | H1, H4, D1 (2020-2026) |
| XRP | D1 uniquement (365 jours, 2025-2026) |
