# Phase 2 — Correction "clôtures, pas mèches" (résultat mixte, documenté honnêtement)

Suite à la question "y a-t-il d'autres enseignements du corpus qui pourraient servir aux Phases 1/2 ?", inventaire fait (voir liste dans la réponse associée). Le point le plus clair et le moins coûteux à corriger : **3 sources indépendantes (#9, #11, #14) insistent pour que la validation de structure (Validation/Confirmation/Limite) se fasse sur les CLÔTURES de bougies, pas sur les mèches** ("considérées comme du bruit").

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
