# Index des sources Trading Lessons traitées

Suivi de toutes les transcriptions/résumés fournis par l'utilisateur, pour ne rien perdre et éviter les doublons.

| # | Fichier | Sujet | Statut "trimestre→journalier" | Statut vs RULES_EXTRACTION.md |
|---|---|---|---|---|
| 1 | `TRADING_LESSONS_PSYCHOLOGY.md` | Psychologie, écart démo/réel (95%→30%), progression 2-3 ans, "3ème borne de range" | Non abordé — toujours en attente | Précise (3ème borne = setup prioritaire) |
| 2 | `TRADING_LESSONS_STRUCTURE_APPRENTISSAGE.md` | Parcours pédagogique (niveaux Blanc/Vert/Jaune/Orange), écosystème Discord, conseil pratique (ne pas démarrer le trial avant maîtrise du PDF) | Non abordé — toujours en attente | Confirme séquence range→tendance |
| 3 | `TRADING_LESSONS_ALTERNATIVE_MANUELLE.md` | Probable TL#4 : méthodes manuelles (canal Supports/Apex/Tangente, Fourchette d'Andrews, TSI 14/7/9), règle d'arrêt "structure en élargissement" | Non abordé — toujours en attente | Nouveau : règle d'arrêt élargissement + méthode canal codable |
| 4 | `TRADING_LESSONS_ANALYSE_SANS_INDICATEURS.md` | Régénération probable de la même vidéo que #3 — delta seulement : cadre High TF/Low TF explicite, "scénario Wall Street" (nom), SuperTrend | Cadre High/Low TF générique trouvé, mais **ne confirme pas** la règle spécifique X→X-2 | Renforce (ne contredit pas) #3 |
| 5 | `TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md` | Système de score 0-100, sizing stop=taille du canal, checklist pré-trade complète | **Règle MTF trouvée mais différente** : "ne jamais trader un range si un range TF supérieur est actif" (pas X→X-2) | Précise fortement (sizing, scoring) — possible tension à réconcilier sur la compensation Fibonacci par qualité de signal |
| 6 | `TRADING_LESSONS_NEUROBIOLOGIE.md` | Neurosciences (amygdale/hippocampe/cortex préfrontal), règles mécaniques (latence 10s, session max 60-90min), 4 profils de réponse primaire | Non abordé — toujours en attente | Complète la checklist pré-trade (source #5) avec des garde-fous neuro |
| 7 | `TRADING_LESSONS_CHAOS_DOPAMINE.md` | Théorie du chaos (Feigenbaum), circuit dopamine/anticipation, "method hopping" = erreur critique | Non abordé — toujours en attente | 4ᵉ confirmation de la "3ème borne de range" comme pilier central |
| 8 | `TRADING_LESSONS_DOPAMINE_SEROTONINE.md` | Duel dopamine/sérotonine, expérience du marshmallow, boucle toxique du "succès chanceux" | Non abordé — toujours en attente | Explique neurologiquement le rejet du scalping ET du très long terme |
| 9 | `TRADING_LESSONS_MTF_SUIVI_TENDANCE.md` | Source technique (pas psycho) : anatomie 3ème/4ème borne, breakout="reddition", règle du 80/20 | **🎯 PROBABLE RÉSOLUTION** : règle "UT+2" — tendance confirmée 2 niveaux au-dessus autorise à trader contre la structure locale (mécanisme identique en esprit, exemple à 3 niveaux vs 7 dans la description initiale) | Précise l'anatomie 3ème/4ème borne, confirme le ratio 80/20 |
| 10 | `TRADING_LESSONS_ZONE_ACCUMULATION.md` | Critères de maturité (4 bornes, Fibo 38-50%), R:R cible 1:5, sizing 1-1,5%, red flags d'invalidation | **2ᵉ confirmation indépendante** de la règle UT+2, cette fois spécifiquement pour les trades de renversement (1/3 des cas) | Ajoute le mécanisme d'emboîtement T/T-1 (observation sur TF inférieur, trade sur TF supérieur) |
| 11 | `TRADING_LESSONS_TROISIEME_BORNE.md` | Parcours pédagogique (niveau blanc→vert), définition stricte de la 3ème borne (3 critères séquentiels), codification visuelle, "Alertes Orange" | **3ᵉ confirmation** (famille de règles) : "Règle de Non-Existence" — une 3ème borne sur l'UT Contexte rend toute borne sur l'UT Tendance non-avenue tant que le prix ne sort pas du range supérieur | Précise la définition exacte d'une 3ème borne valide (mouvement/cassure/pullback à 61,8%) — reçue en double (2 envois identiques) |

| 12 | `TRADING_LESSONS_BREAKOUT_RATIO11.md` | Masterclass Breakout : protocole précis Validation/Confirmation (Ratio 1:1), stop=canal UT+1, breakeven interdit avant confirmation UT+2, "cluster technique" | **4ᵉ confirmation, la plus opérationnelle** : rôle distinct UT+1 (stop) vs UT+2 (confirmation/breakeven) | Révèle une erreur probable dans le money management de la Phase 2 (breakeven trop précoce) |

## 🎯 Statut de la question initiale (règle multi-timeframe) — mis à jour
**Quatre formulations convergentes trouvées** (sources #5, #9/#10, #11, #12), toutes de la même famille : la structure/tendance du TF supérieur prime systématiquement sur le TF inférieur, avec un mécanisme de validation à "2 niveaux au-dessus" pour les cas de transgression (trades à contre-courant), et un rôle distinct pour UT+1 (stop) vs UT+2 (confirmation) selon la source #12. Probable réponse à la question initiale, formulée différemment selon les vidéos mais convergente sur le fond. La séquence complète à 7 niveaux (trimestre→15min) évoquée initialement n'a pas été retrouvée telle quelle — probablement un exemple simplifié à 2-3 niveaux dans les sources disponibles.

| 13 | `TRADING_LESSONS_PULLBACK_MATURITE.md` | Séquence canonique du cycle (6 phases), critères Fibonacci précis (23/38/50%), table GO/WAIT directement implémentable | N/A | **2ᵉ confirmation quasi mot-pour-mot** de la "Règle d'Or du Break-even" (source #12) — très haute confiance |

## ⚠️ Révision à prévoir sur la Phase 2 (money management)
Les sources #12 ET #13 (2 confirmations indépendantes, quasi mot-pour-mot) indiquent que le passage au breakeven devrait intervenir à la Confirmation (UT+2 / clôture dans le contexte opposé), pas à la Validation comme approximé dans `PHASE2_MONEYMANAGEMENT.md`. Si le backtest est retravaillé, corriger ce point en priorité — c'est maintenant la correction la mieux étayée de tout le corpus.

## 🎯 Statut de la question initiale (règle multi-timeframe)
**Probablement résolue par la source #9** (voir `TRADING_LESSONS_MTF_SUIVI_TENDANCE.md`) : mécanisme "UT+2" — une tendance confirmée 2 niveaux de timeframe au-dessus autorise à trader/transgresser la structure du TF local. Correspond en esprit à la description initiale de l'utilisateur, avec un exemple simplifié (3 niveaux : Daily/Hebdo/Mensuel) plutôt que la séquence complète à 7 niveaux évoquée au départ (trimestre-mensuel-hebdo-journalier-4h-1h-15min). À confirmer si la vidéo source exacte de la description initiale est retrouvée.

## Items ouverts toujours en suspens (rappel, voir PLAN.md)
1. XRP absent du backtest multi-timeframe (données non trouvées)
2. Signal = proxy générique, jamais validé contre le vrai PRO Framework/Momentum
3. H1 confirmé NO-GO (encore renforcé en Phase 2)
4. **Règle "tendance repérée sur TF X → trader TF X-2" (trimestre→journalier) — NON VÉRIFIÉE, aucune source pour l'instant ne la confirme ni ne l'infirme**
