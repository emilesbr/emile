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

## Ce qu'il reste à obtenir pour un backtest fidèle
Le calcul exact du contexte (canal Framework) et des signaux (momentum/cycles) n'étant pas public, deux options pour la Phase 1 :
1. **Proxy générique** (déjà construit) + application stricte des règles de risque ci-dessus — solution disponible immédiatement.
2. **Export réel des signaux** via TradingView (Data Window / alertes, cf. méthode décrite précédemment) une fois l'abonnement actif, pour un backtest fidèle aux vrais signaux PRO Framework/Momentum.
