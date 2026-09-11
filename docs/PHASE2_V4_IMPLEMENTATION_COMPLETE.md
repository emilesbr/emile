# Phase 2 v4 — Implémentation fidèle et complète du corpus Trading Lessons

**Principe directeur (correction de méthodologie actée)** : les éléments issus de la propriété intellectuelle de Philippe Roux (le corpus Trading Lessons) sont **implémentés parce qu'ils sont documentés dans la méthode**, pas parce qu'ils améliorent le résultat sur notre proxy générique. Le proxy (confluence EMA) n'est PAS la vraie stratégie — un résultat faible ou fort sur le proxy ne valide ni n'invalide la règle elle-même. Les chiffres ci-dessous sont **informatifs uniquement**, en attendant le vrai signal (export TradingView) pour une validation réelle. Cette version **remplace** le cadre "accepté/rejeté" utilisé précédemment (`PHASE2_V3_ATTEMPT_REGRESSION.md`), qui reposait sur un critère méthodologiquement incorrect.

## Ce qui est maintenant implémenté (tous les éléments demandés)

| Élément | Source | Détail de l'implémentation |
|---|---|---|
| Breakeven différé à la Confirmation | #12/#13/#15/#16 | Le stop ne passe au point mort qu'à la Confirmation, jamais à la Validation |
| Validation sur clôtures, pas mèches | #9/#11/#14 | Limite/Confirmation/Validation déclenchées sur `close`, stop-loss reste sur mèche (ordre réel) |
| **Amplitude réelle calibrée en durée** | #12 | Corrige le bug de la v3 (fenêtres en nombre de bougies) : fenêtres désormais en **jours réels** (5J local, 15J contexte), comparables entre H4 et D1 |
| **Règle de Trois** | #16 | Risque divisé par 2 après 3 zones consécutives gagnantes, jusqu'à une perte |
| **Extreme Channel** | #12/#16 | Stop = support du canal de contexte (EMA lente - 2×ATR), pas un multiple d'ATR local |
| **Critères de maturité (bornes réelles)** | #9-#14 | Détection de swing points réels (creux locaux, `scipy.signal.argrelextrema`), minimum 3 bornes comptées dans la fenêtre contexte avant d'autoriser une entrée |
| **Pyramidalisation** | #15 | Suivi multi-tranches (jusqu'à 3 simultanées), renfort autorisé uniquement sur un nouveau plus haut validé pendant qu'une position est déjà ouverte, chaque tranche gérée indépendamment (stop/validation/confirmation propres) |

## Résultats sur le proxy (informatifs, non discriminants)

| Actif | TF | Profil | Retour | Max DD | Trades |
|---|---|---|---|---|---|
| BTC | H4 | FAIBLE | +10,0% | -46,5% | 793 |
| ETH | H4 | TRÈS AGRESSIF | +985,1% | -67,3% | 943 |
| BNB | H4 | TRÈS AGRESSIF | +1619,4% | -55,3% | 732 |
| SOL | H4 | TRÈS AGRESSIF | +3017,9% | -65,7% | 732 |
| BTC | D1 | (tous profils) | négatif (-4,9% à -18,6%) | -5,9% à -30,8% | 37 |
| SOL | D1 | FAIBLE/MODÉRÉ/AGRESSIF | ~0% | -6% à -19% | 40 |

Détail complet : `phase2_v4_results.csv`.

**Aucune tentative d'interprétation "bon/mauvais" n'est faite ici** — conformément au principe directeur ci-dessus. On note simplement que le filtre de maturité (min. 3 bornes) réduit fortement le nombre de trades sur D1 (37-81 sur toute la période 2020-2026), ce qui est attendu : une exigence de maturité stricte est par nature sélective.

## Simplifications documentées (transparence, pas dissimulation)
- Le signal d'entrée reste le proxy EMA générique — pas le vrai PRO Framework/Momentum
- Les bornes swing sont détectées par extrema locaux génériques (`scipy`), pas par l'algorithme exact de l'indicateur PRO Framework (non public)
- Le canal de contexte (Extreme Channel) est approximé par EMA±ATR, pas le vrai canal de contexte propriétaire
- La pyramidalisation limite à 3 tranches par choix d'implémentation (le corpus ne fixe pas de limite stricte, mais une borne est nécessaire pour la simulation)

## Statut
Cette version constitue l'implémentation de référence à jour, intégrant l'intégralité des enseignements techniques identifiés dans le corpus Trading Lessons à ce stade (17 sources). Reste hors périmètre : la diversification 1%+1% (nécessite un second signal réellement indépendant du proxy EMA, à concevoir séparément).
