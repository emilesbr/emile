# Tentative v3 — Règle de Trois + amplitude réelle + Extreme Channel (REJETÉE, régression sur H4)

**Ne PAS utiliser comme référence.** `PHASE2_CORRECTION_CLOSES.md` reste la version de référence actuelle.

## Ce qui a été tenté
Implémentation combinée de 3 enseignements du corpus jamais testés :
1. **Règle de Trois** (source #16) : risque divisé par 2 après 3 zones consécutives gagnantes
2. **Projections d'amplitude réelle** (source #12) : Validation = amplitude du range local (fenêtre glissante 20 bougies), Confirmation = amplitude du contexte (fenêtre 60 bougies) — remplace les multiples d'ATR arbitraires
3. **"Extreme Channel"** (source #12/#16) : stop = support du canal de contexte (EMA lente - 2×ATR), plutôt qu'un multiple d'ATR local

## Résultat : régression nette sur H4, mitigé sur D1

| Timeframe | Constat |
|---|---|
| H4 | BTC et ETH passent en territoire négatif (ex. ETH Agressif : +142,6% → **-36,3%**) |
| D1 | Généralement fort (BTC Très Agressif +266%, SOL Très Agressif +444%) mais échantillons parfois trop faibles (BNB D1 Agressif : 21 trades seulement — pas fiable) |

## Diagnostic (erreur de calibration, pas d'invalidation du concept)
Les fenêtres glissantes (20/60 bougies) sont **fixes en nombre de bougies, pas en durée réelle**. 20 bougies = ~3,3 jours en H4 mais ~20 jours en D1 — les deux ne représentent pas la même échelle de structure de marché. Les objectifs de Validation deviennent trop exigeants sur H4, la position reste exposée sans sécuriser de profit partiel, et se fait sortir plus souvent sur stop complet.

**Ce n'est pas une invalidation des enseignements du corpus** (le mécanisme d'amplitude réelle est bien documenté et cohérent) — **c'est une erreur de calibration de cette implémentation précise**. Corriger nécessiterait de calibrer les fenêtres proportionnellement à chaque timeframe (en durée réelle plutôt qu'en nombre de bougies fixe), ce qui est un chantier à part entière, pas une correction rapide.

## Décision
Rejetée comme référence. `phase2_v3_ATTEMPT_results.csv` conservé pour trace/référence future si quelqu'un veut reprendre ce chantier avec une calibration correcte par timeframe.

## Hors périmètre (nécessitent une réécriture, pas juste un ajustement)
- **Pyramidalisation** (source #15) : nécessite de suivre plusieurs tranches de position simultanément — structure de données différente de la boucle actuelle à position unique
- **Critères de maturité par détection de bornes réelles** (sources #9-#14) : nécessite un algorithme de détection de swing points (sommets/creux locaux), pas construit actuellement
- **Diversification 1%+1%** (source #16) : testée séparément, voir `PHASE2_DIVERSIFICATION_TEST.md` si disponible
