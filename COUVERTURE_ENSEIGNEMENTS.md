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
| Cycle (approximation Hilbert du Sine Wave), signe corrigé et validé hors-échantillon, **calcul rendu causal** (fenêtre glissante) **— edge global mitigé, edge isolé du cycle non confirmé sur données réelles, cf. ⚠️→◐ ci-dessous** | `code/proxy_v2.py::compute_cycle_phase_causal` |
| Creux ascendants (structure) | `code/proxy_v2.py` |
| Classification de régime (Range/Tendance/Excès), interdiction de trader en Excès | `code/regime_classifier.py`, v6, v7 |
| Pyramidalisation réservée au régime Tendance | v6, v7 |
| Validation croisée multi-timeframe (H4 exécution / D1 référence) | v7 |
| Extreme Channel pour le STOP = canal réel de l'UT supérieure (volet cross-timeframe seulement — voir note ci-dessous) | `code/backtest_phase2_v7.py` (`attach_higher_context` + `use_mtf_stop`), `MTF_CROSS_VALIDATION_H4_D1.md` |
| Garde-fous Phase 4 (checklist pré-trade, latence 10s, session max 60-90min) | Mentionnés dans `PLAN.md`, sources #5/#6 |

**Note sur "Extreme Channel pour le STOP" (P1 du backlog, traité ce cycle)** : le stop bénéficie désormais de la même jointure cross-timeframe sans lookahead que le signal (`ctx_support` D1 transmis au H4). Statut honnête, en deux volets à ne pas confondre :
- Volet cross-timeframe ("contexte de l'UT supérieure affiché sur l'UT de trading", #12/#16) : ✅ résolu et mesuré (`MTF_CROSS_VALIDATION_H4_D1.md`) — mais la mesure montre que ce stop D1 réel **dégrade** le ratio retour/drawdown dans 14/16 combinaisons actif×profil testées (le sizing à risque fixe réduit mécaniquement la taille de position quand le stop réel est plus loin, ~78% du temps) ; seul le stop H4 reste donc le réglage par défaut des campagnes de résultats (`use_mtf_stop=False`), la nouvelle option restant disponible pour comparaison (`use_mtf_stop=True`).
- Volet "channel" (une vraie construction géométrique de canal, pas une bande EMA±ATR) : toujours ❌, cf. l'item "Canal de tendance manuel (Supports→Apex→Tangente)" dans le tableau ci-dessous — hors périmètre de cette correction.
Conforme au principe de tête de ce document : la performance mesurée ne remet pas en cause le fait d'avoir implémenté l'élément — elle sert seulement à choisir le réglage par défaut des campagnes de résultats.

## ⚠️→◐ Réserve méthodologique P0 — TRAITÉE ce cycle de travail (mitigée, PAS résolue au sens plein — lire la nuance avant de conclure)

**Historique** : découverte pendant l'écriture des tests de régression de `proxy_v2.py` (cycle de travail précédent), déjà partiellement documentée dans `OOS_VALIDATION_CYCLE_SIGN.md` (section 5) mais jamais remontée jusqu'ici avant d'être formalisée en P0 (`PLAN.md`). **Ce cycle de travail traite ce P0** : implémentation d'un calcul causal, rejeu complet de v5/v6/v7 + validation XRP, conclusion chiffrée ci-dessous.

### Ce qui a été fait

1. **`compute_cycle_phase_causal(close, window=150)`** (`code/proxy_v2.py`) : fenêtre glissante de 150 barres (pas la série entière, pas une fenêtre expansive — trop lente sur plusieurs années), `hilbert()` recalculé sur chaque fenêtre, seule la phase du **dernier point** (= l'instant *t*, aucune barre future) est conservée. Vectorisé (`sliding_window_view` + `hilbert(axis=1)`). L'ancienne fonction `compute_cycle_phase` (batch) est **conservée telle quelle**, avec un avertissement explicite ⚠️ non-causal dans sa docstring — gardée pour comparaison/archive, plus jamais appelée en production.
2. **Choix de la fenêtre (150)** : comparé empiriquement 40/60/100/150 sur BTC/ETH/BNB/SOL réels (H4 + D1, tout l'historique), critère = **stabilité** (écart-type le plus faible) de la corrélation cycle/rendement-futur entre 3 tiers temporels de la série — pas la seule vitesse (voir `code/cycle_causal_window_selection.py` → `cycle_causal_window_selection.csv`). Résultat important à connaître avant d'interpréter ce choix : **aucune des 4 tailles testées ne montre d'edge causal significatif sur données réelles** (détail au point 3) — 150 est la plus stable parmi des candidats qui, de toute façon, ne montrent pas d'edge.
3. **Test de régression de la causalité elle-même** (`code/test_proxy_v2.py::test_cycle_phase_causal_matches_truncated_series`) : vérifie que la valeur en *t* est identique, à tolérance flottante près, qu'on calcule sur la série complète ou tronquée à *t* — et vérifie, en contrôle négatif, que ce même test détecte bien que l'ancienne fonction batch échoue à cette propriété. 4/4 tests passent.
4. **`add_proxy_v2_score` bascule sur la version causale** (seul point d'entrée utilisé par v5/v6/v7).
5. **Rejeu complet** : v5, v6, v7 (BTC/ETH/BNB/SOL, H4+D1, 4 profils) + validation OOS XRP (`OOS_VALIDATION_CYCLE_SIGN.md`), avec la version causale, comparé ligne à ligne aux résultats batch existants (déjà trackés : `phase2_v5_FIXED_results.csv`, `phase2_v6_regime_results.csv`, `phase2_v7_mtf_results.csv`). Nouveaux fichiers : `phase2_v5_causal_results.csv`, `phase2_v6_regime_causal_results.csv`, `phase2_v7_mtf_causal_results.csv`, `cycle_causal_vs_batch_comparison.csv` (jointure batch/causal, 144 lignes), `oos_xrp_cycle_validation_CAUSAL.csv`.

### Résultat chiffré — deux niveaux à ne pas confondre (c'est là que se joue la nuance "mitigé" vs "résolu")

**Niveau 1 — le composant cycle ISOLÉ (corrélation sinewave/rendement futur), sur données réelles (pas synthétiques) :**

| Actif/TF | Corrélation BATCH (ancienne, en place jusqu'ici) | Corrélation CAUSALE (nouvelle) |
|---|---|---|
| BTC H4/D1, ETH H4/D1, BNB H4/D1, SOL H4/D1 (8 séries) | +0.29 à +0.30, **toutes hautement significatives** | **-0.01 à -0.03, p entre 0.12 et 0.71 (AUCUNE significative)** |
| XRP D1 365j (OOS, actif indépendant) | +0.32, p < 10⁻⁹ (`OOS_VALIDATION_CYCLE_SIGN.md`) | **-0.055, p = 0.42, IC bootstrap [-0.18, +0.07] contient 0** |

Sur les **5 actifs testés** (BTC/ETH/BNB/SOL + XRP hors-échantillon), en H4 comme en D1, **le composant cycle isolé ne montre aucune corrélation significative avec le rendement futur une fois le calcul rendu réellement causal** — alors que le calcul batch (celui utilisé jusqu'ici pour TOUTE la performance rapportée) montrait une corrélation forte et hautement significative partout. Ce n'est pas une nuance de magnitude : sur ce plan précis, **l'edge mesuré en batch ne survit pas au calcul causal sur données réelles**, un résultat plus sévère que l'estimation faite sur sinusoïde synthétique pure (0,93→0,38, qui suggérait un edge affaibli mais réel). Sur sinusoïde synthétique, le résultat causal windowed s'est en outre révélé **très sensible au ratio fenêtre/période** (de -0.27 à +0.92 selon la fenêtre testée pour une série de période 40) — confirmant que la méthode windowed est fragile hors d'un cas de laboratoire à fréquence unique connue, cohérent avec l'absence d'edge trouvée sur des marchés réels qui n'ont pas une période dominante unique et stable.

**Niveau 2 — la performance GLOBALE des moteurs (v5/v6/v7), qui combinent momentum + cycle + structure (score ≥ 2) :**

| Moteur | Retour moyen BATCH | Retour moyen CAUSAL | Win rate moyen BATCH | Win rate moyen CAUSAL | Bascule de signe |
|---|---|---|---|---|---|
| v5 (32 configs, H4+D1) | +1324,7 % | +288,9 % (÷4,6) | 44,2 % | 35,6 % | 4 configs D1 (BNB +→−) / 4 configs D1 (SOL −→+) |
| v6 avec régime (64 configs, H4+D1) | +879,3 % | +222,0 % (÷4,0) | 45,6 % | 36,4 % | 8 configs D1 (BNB +→−) / 8 configs D1 (SOL −→+) |
| v7 MTF H4/D1 (48 configs, **H4 uniquement**) | +955,5 % | +243,1 % (÷3,9) | 51,8 % | 41,0 % | **0 bascule — 48/48 gardent le même signe** |

Lecture honnête : **sur H4 — le timeframe le plus testé et celui du résultat phare v7 — le SENS de l'edge global tient à 100 % (48/48 configurations restent positives)**, mais son **ampleur était surestimée d'un facteur ~4** par le calcul batch, et le win rate est surestimé de ~9 à 11 points. Sur D1 (déjà un échantillon très mince — 13 à 32 trades sur 6 ans, déjà signalé comme peu concluant dans les documents antérieurs), quelques configurations changent de signe dans un sens ou dans l'autre (BNB positif→négatif, SOL négatif→positif) — plus probablement du bruit de petit échantillon qu'un effet causal systématique, mais ce n'est pas exclu et personne ne doit lire les chiffres D1 comme fiables, avant comme après cette correction.

### Conclusion — "mitigé" ≠ "résolu", explicitement (mode ingénieur senior, `PLAN.md`)

- **Mitigé, PAS résolu** : la performance **globale** rapportée sur H4 (v5/v6/v7, y compris le résultat phare `MTF_CROSS_VALIDATION_H4_D1.md`) reste positive en direction après correction causale, mais son ampleur était surestimée d'environ 4× et son win rate de ~10 points — **c'est la nouvelle référence à citer désormais**, pas les anciens chiffres batch. Ceci s'applique au **panier momentum+cycle+structure pris ensemble**, pas au cycle isolément.
- **Toujours ouvert, plus sérieux qu'une simple question de magnitude** : rien dans les données réelles testées (5 actifs, H4+D1) ne confirme que le **composant cycle apporte, à lui seul, une information causale valide**. L'hypothèse la plus probable, cohérente avec le maintien du signe au niveau global, est que **la performance globale survit surtout grâce au momentum (TSI) et à la structure (creux ascendants)** — le cycle, en devenant causal, se comporte plutôt comme un filtre quasi aléatoire qui dilue la précision (d'où la baisse de win rate) sans annuler l'edge des deux autres composantes. Ce n'est **pas prouvé** (nécessiterait un test d'ablation dédié, non fait ici, cf. section suivante) mais c'est l'explication la plus cohérente avec l'ensemble des chiffres ci-dessus — présentée comme hypothèse, pas comme fait établi.
- **Recommandation directe pour la suite** : avant Phase 3, un test d'ablation (score sans le cycle, momentum+structure seuls, score ≥ 1 sur 2) permettrait de trancher si le cycle cause une vraie dilution ou reste neutre — non fait ici (hors scope initial de ce chantier), à ajouter au backlog (`PLAN.md`).

**Point connexe toujours non tranché** (inchangé, sans lien direct avec P0) : la condition composite `cycle_ascending` reste anti-corrélée au rendement futur sur sinusoïde synthétique pure, à l'inverse de la validation OOS réelle sur XRP — divergence documentée dans `code/test_proxy_v2.py` (docstring), toujours ouverte.

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
| **Capital par palier (<10k€/10-100k€/>100k€)** | RULES_EXTRACTION §5 | Jamais pris en compte dans aucun backtest — le sizing ignore la taille absolue du capital |
| Funding rate exact par timestamp (pas juste l'ordre de grandeur annuel) | Découverte de l'agent délégué | Recommandé explicitement par l'agent, pas encore fait |
| **Test d'ablation du composant cycle** (score momentum+structure seul, sans cycle, sur v5/v6/v7) | Découverte de ce cycle de travail (traitement P0) | Recommandé pour trancher si le cycle dilue ou reste neutre une fois causal (cf. ⚠️→◐ ci-dessus) — pas fait, hors scope initial du chantier causal |

## Mise à jour de PLAN.md
`PLAN.md` datait d'avant le refactoring, le classificateur de régime, la validation croisée MTF et la découverte des funding rates — il a été remis à jour (même commit que ce document) pour pointer vers ce document et refléter l'état réel. Remis à jour de nouveau ce cycle de travail pour le traitement du P0 (cycle causal).
