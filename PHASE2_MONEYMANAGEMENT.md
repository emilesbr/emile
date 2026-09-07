# Phase 2 — Money management réel (tables extraites du manuel)

**Statut : première itération faite sur H4/D1 (timeframes GO), table "trade spéculatif" (range) uniquement, 4 profils de risque. Voir gaps en fin de document — cette Phase n'est pas plus "close" que la Phase 1.**

## Méthodologie

Tables appliquées : celles de `RULES_EXTRACTION.md` section 3 (trade spéculatif/range), pas une règle inventée. Choix explicite documenté : le manuel indique qu'on est en range ~80% du temps et que c'est la table par défaut en cas de doute — notre proxy générique ne distingue pas fiablement range/tendance/accumulation, donc on utilise cette table plutôt que celle "trade de tendance".

**Approximation documentée** : les niveaux Validation/Confirmation/Limite/Invalidation (bornes de canaux réelles dans le PDF, dépendantes du vrai PRO Framework) sont approximés par des multiples d'ATR depuis l'entrée : Validation = +1,0×ATR, Confirmation = +2,0×ATR, Limite = +3,5×ATR, Invalidation = -2,0×ATR (stop initial). Sizing conforme au risque par profil (1%/2%/3%/5% du capital), stop financé/breakeven appliqué selon la table, pas de levier (exposition plafonnée à 100% du capital).

## Résultats (4 actifs × 2 timeframes × 4 profils = 32 lignes, détail dans `phase2_moneymanagement_results.csv`)

| Actif | TF | Profil | Retour | Max DD | Win rate | Profit factor |
|---|---|---|---|---|---|---|
| BTC | D1 | FAIBLE | +30,2% | -9,3% | 58,5% | 1,75 |
| BTC | D1 | MODÉRÉ | +80,5% | -17,5% | 58,5% | 1,85 |
| BTC | D1 | AGRESSIF | +166,3% | -26,1% | 37,2% | 1,96 |
| BTC | D1 | TRÈS AGRESSIF | +330,7% | -41,1% | 44,3% | 1,80 |
| BTC | H4 | FAIBLE | +17,7% | -20,7% | 54,0% | 1,18 |
| BTC | H4 | TRÈS AGRESSIF | +236,6% | -60,4% | 37,2% | 1,23 |
| SOL | H4 | FAIBLE | +34,4% | -18,0% | 52,4% | 1,19 |
| SOL | H4 | TRÈS AGRESSIF | +365,4% | **-71,8%** | 32,4% | 1,23 |

(Table complète : voir CSV — la relation retour croissant / drawdown croissant avec l'agressivité est vérifiée sur les 8 combinaisons actif×TF, sans exception.)

## Constat principal
La relation "plus agressif = plus de retour" annoncée par le manuel se vérifie empiriquement, systématiquement. Mais le drawdown croît généralement plus vite que le retour ne le laisse penser à première vue.

## ⚠️ Précision indispensable
La règle du manuel *"perte spéculative jamais >5% du capital"* est une règle **par trade**, pas un plafond de drawdown cumulé. Respecter cette règle sur chaque trade n'empêche absolument pas un drawdown global de -60% à -72% (observé ici en Très Agressif/H4) via une série de pertes consécutives. Ne pas confondre les deux — risque important de mésinterprétation sinon.

## Gaps documentés (non résolus, à ne pas oublier)
1. **Mécanisme "+Reverse" du profil Très Agressif non implémenté** (seule la clôture TP100% à la Limite est modélisée, pas le retournement de position). Les vrais chiffres de ce profil seraient probablement encore plus volatils.
2. **Table "trade de tendance" non testée** — seule la table range/spéculatif l'a été.
3. Hérite de tous les gaps de la Phase 1 (signal = proxy générique, pas le vrai PRO Framework ; XRP absent ; H1 non testé ici puisque déjà NO-GO).

## Conclusion actionnable
- **D1 + profil FAIBLE ou MODÉRÉ** est la combinaison la plus défendable pour un démarrage (DD -9% à -17,5%, cohérent avec la recommandation du manuel de démarrer prudent pendant 6 mois).
- **H4 amplifie tout** (retours et drawdowns) — à réserver à un profil plus expérimenté, pas pour débuter.
- **Très Agressif reste dangereux même sur D1** (-41% de DD dans le meilleur des cas testés) — à ne pas utiliser en usage personnel sans un capital et une tolérance au risque déjà avérés.
