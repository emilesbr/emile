# Audit qualité — gaps identifiés, contrôle aléatoire, bug du cycle trouvé et corrigé

Suite à la question directe "un ingénieur senior serait-il satisfait de ce travail ?". Réponse honnête : non, pas avant ce cycle de travail. Ce document trace l'audit et les corrections qui en découlent.

## Lacunes identifiées (audit)
1. Aucun test unitaire / validation sur cas synthétique
2. Logique de gestion de position dupliquée dans 3 fichiers (`backtest_phase2.py`, `_v4.py`, `_v5.py`) — copiée-collée manuellement à chaque évolution
3. **Aucun test de contrôle "entrées aléatoires"** pour isoler l'effet du signal de celui de la seule gestion du risque
4. Pas de re-vérification walk-forward (année par année) des versions corrigées (v4/v5)
5. Risque de surapprentissage non traité (plusieurs variantes testées sur le même jeu de données, aucune période réservée)
6. Données de funding rate (Binance Futures) disponibles mais jamais utilisées
7. Documentation éclatée en ~25 fichiers sans état actuel unique
8. `CASCADE3_H1_EXECUTION_TEST.md` calculé avec une version du moteur antérieure à la correction "clôtures vs mèches" — conclusion potentiellement obsolète, pas encore reproduite

## Contrôle aléatoire (point 3) — a immédiatement trouvé un vrai bug

Signal remplacé par des entrées aléatoires à la même fréquence, même moteur de risque (v5 complet). Résultat initial : **le hasard battait notre signal TSI+cycle+structure dans presque tous les cas** (ex. SOL H4 : signal -47,2% vs hasard +94,0%). Diagnostic par décomposition composante par composante : Momentum et Structure étaient correctement corrélés au rendement du lendemain ; **la composante Cycle (transformée de Hilbert) était systématiquement anti-corrélée** — signe de convention de phase inversé, bug classique de ce type d'indicateur.

## Correction appliquée
`proxy_v2.py` : `sinewave = np.sin(phase)` → `sinewave = -np.sin(phase)`. Vérifié empiriquement sur BTC/ETH/SOL (corrélation avec le rendement du lendemain devient positive dans les 3 cas après inversion).

## Résultat après correction (H4, profil MODÉRÉ)

| Actif | Avant correction | Après correction | Contrôle aléatoire |
|---|---|---|---|
| BTC H4 | -46,5% | **+588,1%** | -31,2% |
| ETH H4 | -61,4% | **+850,8%** | +3,6% |
| SOL H4 | -47,2% | **+1652,0%** | +94,0% |

Détail complet : `phase2_v5_FIXED_results.csv`.

## Vérification walk-forward (BTC H4 MODÉRÉ, par année) — bien plus stable que tout ce qui précède

| Année | Retour | Max DD | Profit factor |
|---|---|---|---|
| 2020 | +86,2% | -8,4% | 3,22 |
| 2021 | +20,7% | -13,0% | 1,52 |
| 2022 | -1,2% | -11,9% | 1,12 |
| 2023 | +41,3% | -9,3% | 2,62 |
| 2024 | +31,8% | -13,4% | 2,12 |
| 2025 | +5,6% | -11,9% | 1,31 |
| 2026 | +0,5% | -4,8% | 1,29 |

Aucune année catastrophique (même 2022, effondrement Luna/FTX, reste quasi neutre) — contraste net avec l'ancien proxy EMA (`WALKFORWARD_ANALYSIS.md`), qui s'effondrait certaines années.

## ⚠️ Réserve méthodologique majeure à ne pas minimiser
Le sens de la correction (`ascending`→`descending`) a été validé **en observant la corrélation avec le rendement futur sur le même échantillon (BTC/ETH/SOL, mêmes données)** utilisé ensuite pour évaluer la performance. C'est un vrai bug corrigé (l'hypothèse initiale "ascendant = haussier" était une supposition arbitraire, non dérivée des données), mais le choix du sens correct s'appuie sur les mêmes données que le résultat rapporté — risque de biais rétrospectif. **Une validation sur une période ou un actif totalement indépendant de ce processus de correction serait nécessaire avant de faire confiance pleinement à ces chiffres.**

## Statut et lacunes toujours ouvertes
- ✅ Contrôle aléatoire : fait, a trouvé un vrai bug
- ✅ Walk-forward de la version corrigée : fait pour BTC H4, stable
- ❌ Revalidation du signe du cycle sur donnée réellement indépendante : pas fait
- ❌ D1 reste peu fiable (16-46 trades)
- ❌ Refactoring de la logique dupliquée en fonction unique testée : pas fait
- ❌ Tests unitaires : toujours absents
- ❌ `CASCADE3_H1_EXECUTION_TEST.md` : conclusion basée sur un moteur périmé, pas refait
- ❌ Funding rates : toujours ignorées
- ❌ Consolidation de la documentation en un état actuel unique : pas fait
