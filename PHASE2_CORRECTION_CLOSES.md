# Phase 2 — Correction "clôtures, pas mèches" (résultat mixte, documenté honnêtement)

> ⚠️ **Document historique/supersédé** — voir `STATUS.md` et `PHASE2_V4_IMPLEMENTATION_COMPLETE.md` pour l'état actuel.

Suite à la question "y a-t-il d'autres enseignements du corpus qui pourraient servir aux Phases 1/2 ?", inventaire fait (voir liste dans la réponse associée). Le point le plus clair et le moins coûteux à corriger : **plusieurs sources indépendantes insistent pour que la validation de structure (Validation/Confirmation/Limite) se fasse sur les CLÔTURES de bougies, pas sur les mèches.**

> ⚠️ **CORRECTION DE CITATION (8e round de mobilisation, vérifiée par grep direct dans les 17 sources — même classe d'erreur que la citation UT+1/Validation corrigée au 7e round)** : la version initiale de ce paragraphe attribuait la règle à *"3 sources indépendantes (#9, #11, #14)"* avec la glose *"(considérées comme du bruit)"*. Deux erreurs :
> - **#9 (`TRADING_LESSONS_MTF_SUIVI_TENDANCE.md`) ne dit RIEN sur clôtures vs mèches** — 0 occurrence de "clôtur"/"mèche"/"wick"/"bougie" sur ce sujet dans tout le fichier. Attribution fausse.
> - **La glose *"considérées comme du bruit"* n'apparaît nulle part dans le corpus** appliquée aux mèches. La seule occurrence proche est `TRADING_LESSONS_TROISIEME_BORNE.md:18`, où *"bruit"* qualifie les bornes de l'UT de TENDANCE face à l'UT de contexte — pas les mèches.
>
> **Sources réelles de la règle, vérifiées mot pour mot** : #11 `TRADING_LESSONS_TROISIEME_BORNE.md:22-23` (*"validée par des clôtures de bougies au-delà du contexte (pas un simple dépassement intra-bougie)"*) ; #14 `TRADING_LESSONS_STRUCTURES_ALTERATIONS.md:28` (*"les mèches peuvent pénétrer l'ancien territoire, mais les clôtures de bougies doivent rester à l'extérieur pour valider la structure"*) ; #10 `TRADING_LESSONS_ZONE_ACCUMULATION.md:33/41/46` (*"Attendre impérativement la clôture de la bougie validant le signal"*) ; #13 `TRADING_LESSONS_PULLBACK_MATURITE.md:9` ; et surtout **#15 `TRADING_LESSONS_PYRAMIDALISATION.md:20`, jamais citée ici alors que c'est l'énoncé le plus littéral du corpus** : *"règle d'or : calculs sur clôtures, jamais sur les mèches"*. À l'inverse, **#16 `TRADING_LESSONS_CLUSTERS_PRIX.md:30` refuse explicitement de trancher** pour le repérage d'un creux structurel : *"remonté sous le dernier creux structurel (bas de clôture ou mèche)"* — la règle porte sur la VALIDATION, pas sur le repérage des structures. La correction appliquée ci-dessous (déclenchements sur clôture) reste donc bien fondée, mais sur #11/#14/#10/#13/#15, pas sur #9.
>
> **Limite de la correction, révélée par la même relecture** : elle n'a corrigé que les **déclenchements**. Les **amplitudes** projetées (`local_range`/`context_range` = `max(high) - min(low)`) sont restées purement en mèches, alors que #15 vise précisément ce calcul (*"report de l'amplitude du range en clôture"*, ligne 22). Item ouvert, chiffré, à trancher : cf. `COUVERTURE_ENSEIGNEMENTS.md` catégorie C, "règle d'or (#15) vs `local_range`/`context_range`".

## Correction appliquée
Les déclenchements de Validation/Confirmation/Limite dans le moteur de backtest utilisaient `high[i] >= seuil` (mèche). Remplacé par `close[i] >= seuil`. Le stop-loss reste déclenché sur mèche (`low[i] <= stop`) car c'est un ordre réel qui s'exécute intrabar, contrairement à une validation de structure.

## Résultat — contrairement à la correction du breakeven, PAS un gain net systématique

| Timeframe | Δ Retour moyen | Δ Drawdown moyen | Δ Nombre de trades |
|---|---|---|---|
| D1 | +39,2 pts | -0,6 pt | -13,2 |
| H4 | -11,9 pts | -2,8 pts | -52,8 |

Résultats individuels très bruités (ex. ETH H4 Agressif : -170 points de retour ; BNB D1 Très Agressif : +199 points). Aucune direction cohérente comme pour la correction du breakeven (`PHASE2_CORRECTION_BREAKEVEN.md`).

## Verdict honnête
- **Méthodologiquement fondée** (3 sources concordantes) → gardée dans le moteur.
- **Empiriquement non concluante** → le nombre de trades chute fortement partout (moins de fausses validations sur mèche, cohérent avec la méthodologie), ce qui réduit la taille d'échantillon et rend les résultats individuels plus sensibles au bruit statistique. Contrairement au breakeven, je ne peux pas affirmer que cette correction améliore systématiquement la performance — juste qu'elle est plus fidèle à la méthode décrite.

## Autres enseignements du corpus non encore exploités (inventaire, par effort croissant)
| Enseignement | Source | Effort |
|---|---|---|
| ~~Validation sur clôtures~~ | #9/#11/#14 | ✅ Fait (ce document) |
| Ratio 1:1 par projection d'amplitude réelle (pas ATR) | #12 | Moyen |
| Table "trade de tendance" (vs range) | RULES_EXTRACTION | Moyen |
| "Règle de Trois" (prudence après 3 zones exploitées) | #16 | Faible-moyen |
| "Extreme Channel" pour le stop (canal UT+1 réel) | #12/#16 | Moyen |
| Pyramidalisation (renforcement 3ème borne, ×5) | #15 | Élevé |
| Diversification 1%+1% (2 patterns non corrélés) | #16 | Élevé (nécessite 2ème signal) |
| Critères de maturité (min. 3-4 bornes) | #9-#14 | Élevé (détection de swing points) |
