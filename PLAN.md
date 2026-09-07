# Plan directeur — Système de trading formalisé à partir des outils PRO Indicators

**Cadre du projet** : usage strictement personnel des indicateurs de Philippe Roux (PRO Indicators), sur la base d'un abonnement souscrit et d'un accord verifié avec l'éditeur sur les CGU. Objectif : formaliser une stratégie de trading multi-timeframe testable, avec une gestion du risque explicite, avant toute mise en œuvre avec du capital réel.

**Statut du cadrage**
- Accord obtenu avec Philippe Roux + CGU vérifiées (usage personnel) : ✅ fait
- Pas d'automatisation de l'exécution des trades en phase initiale : ✅ acté
- Architecture cible : signal généré par le système + validation humaine avant toute transaction. L'automatisation de l'exécution n'est pas engagée aujourd'hui — elle sera réévaluée uniquement après validation complète de la Phase 4, avec des garde-fous à définir à ce moment.
- Objectif "revenu journalier" reformulé : aucune stratégie ne garantit un gain positif chaque jour (variance quotidienne irréductible). L'objectif retenu est une **espérance de gain positive sur une fenêtre plus longue (semaine/mois), avec un risque borné et mesuré**, validée statistiquement avant tout engagement de capital réel.

---

## Phase 0 — Extraction des règles déterministes
**Objectif** : transformer les indicateurs visuels (PRO Framework, PRO Momentum, PRO Sinewave, PRO Alerts) en règles booléennes testables (entrée / sortie / stop / sizing), sans avoir accès au code source protégé.

| Étape | Méthode | Statut |
|---|---|---|
| Lecture manuel PDF | Extraire la logique documentée pour chaque indicateur | ⏳ en attente du fichier |
| Alertes natives TradingView | Lister les `alertcondition()` exposées (boîte "Ajouter une alerte") | ⏳ en attente |
| Data Window / export CSV | Extraire les valeurs numériques réelles à chaque bougie | ⏳ en attente |
| Étiquetage manuel + test de fidélité | Vérifier que la règle reconstruite reproduit fidèlement les signaux historiques | ⏳ en attente |
| Confirmation Phil (sizing/stop recommandés) | Obtenue et documentée par l'utilisateur | ✅ fait |

**Critère GO/NO-GO** : la règle formalisée doit reproduire fidèlement (idéalement 100 %) les signaux réels de l'indicateur sur un échantillon historique — sinon itérer avant de passer en Phase 1.

**Bloquant actuel** : fourniture du manuel PDF + captures/valeurs d'alertes par l'utilisateur.

---

## Phase 1 — Backtest multi-timeframe (sous-agents en parallèle)

| Agent | Timeframe(s) | Tâche | Échantillon minimum |
|---|---|---|---|
| Agent BT-1 | M15 | Walk-forward, sensibilité paramétrique | ≥300 trades/actif |
| Agent BT-2 | H1 | Idem | ≥200 trades/actif |
| Agent BT-3 | H4 | Idem | ≥100 trades/actif |
| Agent BT-4 | D1 | Idem, sert de filtre de tendance croisé | ≥50 trades/actif |

Chaque agent réutilise/étend le moteur de backtest déjà construit (données Binance réelles OHLCV, métriques Sharpe/Sortino/max drawdown/win rate/profit factor, frais de transaction inclus) sur BTC, ETH, BNB, SOL, XRP.

**Critère GO/NO-GO** : Sharpe out-of-sample > 0 de façon stable sur au moins 3 fenêtres consécutives, ET cohérence de signe des résultats entre timeframes voisins (pas de contradiction type H1 profitable / H4 catastrophique sur le même actif).

**Statut réel (voir `PHASE1_CLOSEOUT.md`) : substantiellement complète pour H4/D1 (GO), H1/M15 en NO-GO. PAS entièrement close — 4 items restent ouverts : absence de données XRP, signal encore un proxy générique jamais validé contre le vrai PRO Framework, règle de sélection de timeframe "trimestre→journalier" non vérifiée (en attente des transcriptions Trading Lessons). Décision explicite : ces items n'empêchent pas d'avancer sur la Phase 2 en parallèle, mais restent à traiter.**

---

## Phase 2 — Gestion du risque (dérivée des règles extraites, pas inventée)

À dériver en priorité des règles obtenues en Phase 0 ; à défaut, cadre conservateur par défaut appliqué :
- Risque par trade : 0,5–1 % du capital
- Stop-loss systématique sur chaque position (méthode issue de Phase 0 : ATR / niveau structurel / % fixe)
- Limite de perte journalière → coupe-circuit (arrêt du système pour la journée)
- Kill-switch global à -15 % de drawdown depuis le pic de capital
- Plafond d'exposition corrélée (les cryptos étant fortement corrélées entre elles, éviter que plusieurs positions simultanées ne soient en réalité un seul pari directionnel déguisé)

---

## Phase 3 — Paper trading (validation temps réel, sans argent réel)
- Durée minimale : 4 à 8 semaines, signaux générés en temps réel sur compte démo
- Mesure de l'écart entre hypothèses du backtest (slippage, latence, spread) et exécution réelle simulée

**Critère GO/NO-GO** : la performance en paper trading doit rester dans l'intervalle de confiance du backtest. Un écart majeur (ex. Sharpe backtest ~0,8 vs paper trading négatif) impose une investigation avant de poursuivre.

---

## Phase 4 — Pilote capital réel, exécution 100 % manuelle
- Capital engagé : 10–15 % du capital cible
- Wallet connecté, mais **aucune transaction automatique** : le système génère le signal + la taille de position calculée selon les règles de risque (Phase 2) ; l'utilisateur valide et exécute chaque transaction manuellement
- Minimum 30 à 50 trades réels documentés (raison d'entrée, raison de sortie, respect ou non des règles) avant toute discussion sur une éventuelle automatisation de l'exécution

---

## Phase 5 — Décision sur l'automatisation de l'exécution *(non engagée à ce stade)*
Discussion à ouvrir uniquement après validation complète de la Phase 4. Garde-fous à définir à ce moment (plafonds stricts, confirmation par trade ou par session, kill-switch actif en permanence). Aucun calendrier fixé — dépend entièrement des résultats du pilote manuel.

---

## Prochaine action immédiate
Fourniture par l'utilisateur du manuel PDF PRO Indicators (et toute capture/valeur d'alerte déjà extraite) pour démarrer concrètement la Phase 0.
