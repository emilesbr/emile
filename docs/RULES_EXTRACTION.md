# Extraction des règles — PRO Indicators (Phase 0)

Source : `PROIndicators_Manual_FR.pdf` (53 pages, manuel officiel Philippe Roux / PRO Indicators). Usage personnel, cadre vérifié avec l'éditeur (cf. PLAN.md).

**Non divulgué par l'éditeur** (donc non reproductible) : la formule exacte du momentum PRO (paramètre X, défaut 14) et l'algorithme de détection (>150 patterns momentum, >100 patterns cycles, ~10 conditions/pattern). Tout ce qui suit décrit la LOGIQUE DE DÉCISION appliquée une fois que ces outils ont émis un signal — pas le calcul interne du signal lui-même.

## 1. Classification du contexte (PRO Framework)

| Régime | Fréquence | Conditions d'entrée |
|---|---|---|
| Range neutre | ~50% | Retracement fibo ≥76,4% + débordement du contexte + signal & triangle de confirmation |
| Range tendanciel | ~25% | Retracement ≥61,8%, dans le sens de la tendance majeure (⚠ déconseillé <1 an d'expérience) |
| Tendance | ~20% | Retracement ≥23%, proche du canal de tendance, signal (couleur) + triangle |
| Bulle / Excès | ~5% | **NE PAS TRADER** (réservé experts + vérification Discord) |

Règles transverses :
- **Ne jamais vendre la partie basse du canal de tendance / acheter la partie haute** (règle de base #2)
- **Ne jamais passer de tendance haussière à baissière sans repasser par un range** (sauf cas de bulle)
- Range : max **3 bornes rejetées** avant "range mature" → arrêt
- Breakout : target invalidée après **30 bougies**

### Sous-étapes d'une tendance (séquence)
Accumulation (range mature + rejet canal + retracement 38-61%) → Breakout (cassure accumulation + volume + breakout Framework) → Divergence (standard) → Pull-Back (retracement min 23-38% + retour min 50% contexte) → Excès final (nouveau retour contexte + breakout Framework)

## 2. Types de signaux (par ordre de fiabilité croissante)

| Signal | Couleur | Fiabilité | Règle d'usage |
|---|---|---|---|
| TP (Take Profit) | Gris | Faible | Nécessite validation horizontale ou triangle. Stop large (excès possible) |
| Overload | Gris | Faible-moyenne | Idem validation, mais stop serré possible (réaction rapide) |
| DIV standard | Gris | Faible | Nécessite filtrage (comme TP) |
| DIV cachée | Rouge/Bleu | Forte | Pas de validation supplémentaire nécessaire |
| EXIT | Noir | Forte | Prise de profit **obligatoire ≥50%** si positionné à contre-sens |
| SurAchat/SurVente | Bleu/Rouge | Contextuelle | À ignorer en tendance mature ; excellent si "late trend signal" (chasse aux stops puis reversal) |
| BULL/BEAR | — | Renfort seulement | Uniquement au contact du canal de tendance + triangle obligatoire |
| SQUEEZE | Jaune/Orange (alerte) | — | Si en position : doubler le stop immédiatement + réduire la taille. Si hors position et débutant : ne pas trader |
| CONTEXT | Jaune/Orange (alerte) | — | Rappel de vérifier le timeframe supérieur avant toute décision |

## 3. Money management — Trade spéculatif (range)

4 étapes : **Validation** (borne opposée canal tendance) → **Confirmation** (médiane canal contexte, clôturée) → **Invalidation** (cassure forte canal tendance) → **Limite** (target atteinte)

| Profil | Validation | Confirmation | Invalidation | Limite |
|---|---|---|---|---|
| Faible risque | TP50%+SL payé | SL BE | TP50%+TP BE | TP100% |
| Modéré | TP25%+SL payé | TP25%+SL BE | TP BE | TP100% |
| Agressif | SL BE | TP50% | TP BE | TP100% |
| Très agressif | RIEN | — | RIEN | TP100%+Reverse |

## 3bis. Money management — Range TENDANCIEL (distinct du Range Neutre ci-dessus)

**Trouvé par re-lecture complète du manuel (organigramme p.48), absent jusqu'ici de ce document et du code** : le manuel donne un tableau SÉPARÉ pour le Range Tendanciel (retracement ≥61%, "entrer dans le contexte"), avec une étape "Target 1" (pas "Limite") et un mécanisme "SL gain" propre aux profils Agressif/Très Agressif — pas juste la même grille que le Range Neutre appliquée à un contexte différent.

4 étapes : **Validation** (borne opposée canal tendance) → **Confirmation** (borne opposée canal contexte, clôturée) → **Target 1** (zone objectif borne opposée du range) → **Invalidation** (cassure tendance, dernier support/résistance)

| Profil | Validation | Confirmation | Target 1 | Invalidation |
|---|---|---|---|---|
| Faible risque | TP25%+SL payé | TP50%+SL BE | TP100% | TP50%+TP BE |
| Modéré | TP25% | TP25%+SL BE | TP100% | -/TP BE |
| Agressif | — | TP50%+SL BE | TP25%+SL gain | TP BE |
| Très agressif | — | TP25%+SL BE | TP25%+SL gain | — |

**Vérifié dans le code (pas supposé)** : `PROFILES_V4` (`emile/backtests/backtest_phase2_v7.py`) applique une seule grille `val_close`/`conf_close` à tout trade de range, sans branchement sur `regime_classifier.py::RANGE_NEUTRE` vs `RANGE_TENDANCIEL` — ce tableau n'est donc PAS implémenté. Nouvel item de backlog, catégorie B (littéral, coût modéré) — implémentation non tranchée, à décider séparément.

**Décision prise (19e round de mobilisation multi-agents, cf. `docs/PLAN.md` section "19e application") : PAS implémenté ce cycle, item requalifié.** "SL gain" (Agressif/Très Agressif, étape Target 1) n'a AUCUNE occurrence ailleurs dans les 17 sources vidéo, `COUVERTURE_ENSEIGNEMENTS.md` ou le code (recherche exhaustive incluant "trailing") — ni niveau, ni formule de calcul n'est donné, et le seul mécanisme de remontée de stop déjà codé (`conf_to_be`) est explicitement plafonné à l'entrée (jamais au-delà). Coder "SL gain" exigerait donc d'inventer un paramètre, même motif de refus que le gate Fibonacci RANGE (`COUVERTURE_ENSEIGNEMENTS.md`). Les lignes Faible risque/Modéré, en revanche, sont composées uniquement de mécanismes déjà définis et codés (SL payé, SL BE, TP BE, TP100%) — codables sans invention, mais leur implémentation isolée (2 profils sur 4) exige un nouveau stage de clôture partielle dans `position_engine.py::process_tranche` (pas un simple swap de table) et la résolution préalable d'une ambiguïté déjà présente pour le tableau §3 existant (la colonne "Invalidation" contient des libellés `TP*`/`BE`, jamais lus par le code, qui traite l'Invalidation comme un stop dur à 100% pour tous les profils) — décision de conception non triviale, cf. `docs/PLAN.md` pour le détail complet.

## 4. Money management — Trade de tendance

5 étapes : **Accumulation** → **Breakout** → **Divergence** → **Pull-Back** → **Excès final**

| Profil | Accumulation | Breakout | Divergence | Pull-Back | Excès final |
|---|---|---|---|---|---|
| Faible risque | Attente | Entrée 100% | TP50%+SL BE | RIEN | TP100% |
| Modéré | Renfort +25% | Renfort +100% | TP25%+SL BE | RIEN | TP100% |
| Agressif | Renfort +50% | Renfort +150% | TP25% | Renfort +50% | TP100% |
| Très agressif | Renfort +100% | Renfort +200% | TP25% | Renfort +100% | TP100%+Reverse |

## 5. Gestion du risque globale (règles dures)

- Perte spéculative **jamais >5% du capital**, quel que soit le profil
- Recommandé **≤1% par trade pendant les 6 premiers mois minimum**
- Progression du levier/agressivité liée à l'expérience ET au profil psychologique (Dominant/Assertif/Soumis) — tableau à 4 niveaux (Débutant <1an / Apprenti <3ans / Expérimenté / Professionnel)
- Paliers de capital : <10 000€ (agressivité quasi obligatoire pour dépasser un SMIC), 10 000-100 000€ (arbitrage risque/sécurité), >100 000€ (agressivité maximale déconseillée par précaution)

## 6. Sélection du timeframe (selon disponibilité, pas selon "envie de gagner plus")

| Disponibilité | Timeframe recommandé |
|---|---|
| Job, pauses possibles | H1 – D1 |
| Job, aucune pause possible | Daily uniquement |
| Domicile / garde d'enfants | 15m – 4H |
| Temps plein trading | Toujours PAS de scalping <15m (5-10 trades/jour max, risque de stress/décision irrationnelle) |

**Le scalping est explicitement déconseillé par l'auteur lui-même**, y compris pour les traders à temps plein — point important vu l'objectif initial de "revenu journalier".

## 6bis. Compléments trouvés par re-lecture complète du manuel (mineurs, non prioritaires)

- **Table exacte TF Local → TF Supérieur** (alerte CONTEXT, p.36) :
  m1→m5, m2→m10, m3→m15, m5→m30, m15→H1, m30→H2, H1→H4, H2→H8, H4→D1, D1→W1, W1→M1, M1→M3.
  Confirme que le mécanisme est bien relatif (toujours +1 cran), et que M15 n'apparaît ici que
  comme un choix de TF Local possible parmi d'autres (cf. chapitre 6, "Choisir un timeframe
  adapté" selon disponibilité), jamais comme une UT imposée par un mécanisme.
- **Critères exacts de détection Bulle/Excès** (jusqu'ici seulement "NE PAS TRADER") :
  (1) les boîtes du canal de contexte deviennent disjointes (support ET résistance pour la bulle,
  support seul pour un excès simple) ; (2) contexte psychologique de spéculation exacerbée
  obligatoire ; (3) accélération parabolique des prix — condition supplémentaire, uniquement
  pour la bulle, pas nécessaire pour un excès. Reste hors périmètre (régime non tradé).

## Ce qu'il reste à obtenir pour un backtest fidèle
Le calcul exact du contexte (canal Framework) et des signaux (momentum/cycles) n'étant pas public, deux options pour la Phase 1 :
1. **Proxy générique** (déjà construit) + application stricte des règles de risque ci-dessus — solution disponible immédiatement.
2. **Export réel des signaux** via TradingView (Data Window / alertes, cf. méthode décrite précédemment) une fois l'abonnement actif, pour un backtest fidèle aux vrais signaux PRO Framework/Momentum.
