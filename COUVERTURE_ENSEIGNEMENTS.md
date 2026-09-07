# Couverture des enseignements — audit complet, implémenté vs manquant

Réponse à "est-ce que tous les enseignements sont pris en compte dans le plan à venir ?" : **non**. Voici l'audit précis, élément par élément, croisant `RULES_EXTRACTION.md` (manuel PDF) et `TRADING_LESSONS_INDEX.md` (17 sources vidéo) contre le code actuel (`code/`).

## ✅ Implémenté

| Élément | Où |
|---|---|
| Money management "trade spéculatif" (range), 4 profils | `code/backtest_phase2.py` et suivants |
| Breakeven différé à la Confirmation (7 sources) | Tous moteurs depuis la correction |
| Validation sur clôtures, pas mèches (3 sources) | Tous moteurs depuis la correction |
| Règle de Trois (risque /2 après 3 zones gagnantes) | v4, v5, v6, v7 |
| Amplitude réelle calibrée en durée (pas en bougies) | v4, v5, v6, v7 |
| Maturité par détection de swing points (≥3 bornes) | v4, v5, v6, v7 |
| Pyramidalisation multi-tranches | v4, v5, v6, v7 |
| TSI(14,7,9), momentum | `code/proxy_v2.py` |
| Cycle (approximation Hilbert du Sine Wave), signe corrigé et validé hors-échantillon | `code/proxy_v2.py` |
| Creux ascendants (structure) | `code/proxy_v2.py` |
| Classification de régime (Range/Tendance/Excès), interdiction de trader en Excès | `code/regime_classifier.py`, v6, v7 |
| Pyramidalisation réservée au régime Tendance | v6, v7 |
| Validation croisée multi-timeframe (H4 exécution / D1 référence) | v7 |
| Garde-fous Phase 4 (checklist pré-trade, latence 10s, session max 60-90min) | Mentionnés dans `PLAN.md`, sources #5/#6 |

## ❌ Jamais implémenté (liste exhaustive, pas de trou silencieux)

| Élément | Source | Pourquoi ça manque |
|---|---|---|
| **Table "trade de tendance" (5 étapes : Accumulation/Breakout/Divergence/Pull-Back/Excès final)** | RULES_EXTRACTION §4 | Seule la table range a été testée depuis le début — jamais corrigé malgré des mentions répétées |
| **Fibonacci retracement (23%/38%/50%/61,8%/76,4%) comme critère d'entrée** | #9, #10, #13, #14, #11 (répété dans presque toutes les sources techniques) | Notre proxy n'a jamais vérifié la profondeur de retracement — entrée décidée uniquement par TSI/cycle/structure, jamais par la position dans une zone Fibonacci |
| **Règle "Wall Street" (structure en élargissement = abstention totale)** | #3, #4 | Aucun détecteur de ce pattern n'a jamais été construit — signal d'alerte du corpus totalement absent du code |
| **Canal de tendance manuel (Supports→Apex→Tangente)** | #3 | On a toujours utilisé EMA±ATR comme substitut, jamais la construction géométrique décrite |
| **Fourchette d'Andrews ("Inside Pitchfork")** | #3, #4 | Jamais implémentée |
| **Diversification 1%+1% (2 patterns indépendants) + "Cluster Technique" (MA20+support) comme second pattern** | #16 | Scopé hors périmètre dès le départ, jamais repris depuis |
| **Mécanisme "+Reverse" du profil Très Agressif à la Limite** | Extraction manuel, §3 | Identifié dès la première Phase 2, jamais construit (nécessite de gérer une position short après reverse) |
| **Règle "UT+2" exacte (2 niveaux au-dessus, pas le niveau immédiat)** | #9, #10, #12, #14, #15, #16 (6 sources) | v7 ne valide qu'avec le niveau immédiatement supérieur (H4→D1), pas le vrai "2 niveaux au-dessus" (ex. H4→Hebdo) |
| **Extreme Channel pour le STOP = canal réel de l'UT supérieure** | #12, #16 | Incohérence interne trouvée à l'instant : v7 valide le SIGNAL par le D1, mais le STOP (`ctx_support`) reste calculé sur le même timeframe que celui tradé, pas sur un vrai canal D1 — le nom "Extreme Channel" reste encore trompeur même après la correction MTF |
| **Capital par palier (<10k€/10-100k€/>100k€)** | RULES_EXTRACTION §5 | Jamais pris en compte dans aucun backtest — le sizing ignore la taille absolue du capital |
| Funding rate exact par timestamp (pas juste l'ordre de grandeur annuel) | Découverte de l'agent délégué | Recommandé explicitement par l'agent, pas encore fait |

## Mise à jour de PLAN.md
`PLAN.md` datait d'avant le refactoring, le classificateur de régime, la validation croisée MTF et la découverte des funding rates — il a été remis à jour (même commit que ce document) pour pointer vers ce document et refléter l'état réel.
