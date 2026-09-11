# Proxy v2 — signal reconstruit à partir du corpus (TSI + cycle + structure)

**Objectif** : jusqu'ici, toutes nos corrections (Phase 2 v4) portaient sur la gestion du risque *autour* du signal d'entrée, qui restait une confluence EMA(8/21/55) générique n'ayant aucun lien avec la méthode décrite. Ce document construit un signal d'entrée directement inspiré du corpus, remplaçant l'EMA par des éléments publics et précisément définis.

## Composition du signal (formule des "4 nuances de gris")

| Composante | Méthode | Source |
|---|---|---|
| Momentum | **TSI(14,7,9)** — True Strength Index (Blau), formule publique exacte | #3/#4 |
| Cycle | Phase extraite par **transformée de Hilbert** sur le prix détrendé — approximation documentée du "Sine Wave" d'Ehlers (pas l'algorithme adaptatif exact à période dominante variable, mais le même principe d'analyse de phase cyclique) | corpus général |
| Structure | **Creux ascendants** (swing lows croissants, détectés par `scipy.signal.argrelextrema`) + prix au-dessus de l'EMA(55) | #9-#14 |

Score = somme des 3 composantes (0-3), signal long si score ≥ 2. Vérification de non-dégénérescence : momentum favorable 50,4% du temps, cycle 26,3%, structure 39,5% (échantillon BTC D1) — aucune composante n'est jamais/toujours vraie.

## Résultats (branché sur le moteur de risque complet Phase 2 v4)

Détail complet : `phase2_v5_proxyv2_results.csv`.

## Deux observations factuelles (pas un jugement de valeur — cf. principe établi)

**1. Nombre de trades très réduit sur D1 (18 à 46 sur 2020-2026).** Exiger Momentum ET Cycle ET Structure simultanément favorables, plus la maturité (≥3 bornes), est délibérément restrictif — cohérent avec la philosophie du corpus ("Signal Noir"/abstention la majorité du temps). Mais avec un si petit échantillon, **aucune conclusion statistique fiable ne peut être tirée** de ces chiffres — ni positive ni négative.

**2. H4 montre des résultats majoritairement négatifs** (BTC/ETH/BNB négatifs sur tous profils ; SOL Très Agressif +31,1% seul cas positif). Rapporté tel quel, sans qualification — ça ne valide ni n'invalide la méthode TSI/cycle/structure, ça décrit seulement le comportement de cette implémentation précise sur ce proxy et cette période.

## Limites documentées (transparence)
- Le "Sine Wave" est une approximation par transformée de Hilbert, pas l'algorithme adaptatif exact d'Ehlers décrit dans le corpus (période dominante variable via discriminateur homodyne) — non répliqué faute de spécification suffisante pour un test fiable
- Les swing points sont détectés par un extrema local générique, pas par l'algorithme propriétaire du PRO Framework
- Le seuil "cycle mature si |sinewave| > 0.8" est une transposition directe de l'échelle -100/+100 du corpus vers l'échelle -1/+1 de sin(phase), non vérifiée empiriquement

## Statut
Première tentative de signal fidèle au corpus (au-delà de la seule gestion du risque). Résultats informatifs seulement — la validation réelle attend toujours le vrai signal PRO Framework/Momentum (export TradingView).
