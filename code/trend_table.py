"""
Table "trade de tendance" (5 étapes) — RULES_EXTRACTION.md section 4, jamais
implémentée jusqu'ici (COUVERTURE_ENSEIGNEMENTS.md, PLAN.md backlog item 1).
Depuis le début du projet, seule la table "trade spéculatif" (range, 4 étapes
Validation/Confirmation/Invalidation/Limite, `position_engine.py`) a été
testée, alors même que `regime_classifier.add_regime` distingue TENDANCE
depuis plusieurs cycles de travail. Ce module comble cette lacune : il
s'active UNIQUEMENT quand `regime_classifier.add_regime` classe la bougie en
régime TENDANCE, et tombe sur "pas de position" sinon (cf. hypothèse H11).

Rappel du manuel (RULES_EXTRACTION.md §4), reproduit ici pour référence :

    5 étapes : Accumulation → Breakout → Divergence → Pull-Back → Excès final

    | Profil         | Accumulation | Breakout      | Divergence    | Pull-Back    | Excès final    |
    |----------------|--------------|---------------|---------------|--------------|----------------|
    | Faible risque  | Attente      | Entrée 100%   | TP50%+SL BE   | RIEN         | TP100%         |
    | Modéré         | Renfort +25% | Renfort +100% | TP25%+SL BE   | RIEN         | TP100%         |
    | Agressif       | Renfort +50% | Renfort +150% | TP25%         | Renfort +50% | TP100%         |
    | Très agressif  | Renfort +100%| Renfort +200% | TP25%         | Renfort +100%| TP100%+Reverse |

Et la séquence de déclenchement des étapes (RULES_EXTRACTION.md §1) :

    Accumulation (range mature + rejet canal + retracement 38-61%)
    → Breakout (cassure accumulation + volume + breakout Framework)
    → Divergence (standard)
    → Pull-Back (retracement min 23-38% + retour min 50% contexte)
    → Excès final (nouveau retour contexte + breakout Framework)

================================================================================
POURQUOI UN MOTEUR SÉPARÉ DE position_engine.py (ne le dénature pas, ne le
réutilise pas non plus)
================================================================================
`position_engine.py::process_tranche` code EN DUR une machine à états à 4
étapes bien précises (Limite / Invalidation / flip / Confirmation-si-Validation
/ Validation), où chaque étape est un SEUIL DE PRIX figé calculé une fois à
l'entrée (val_px/conf_px/lim_px) et où la seule variabilité entre moteurs est
la VALEUR de ces seuils et les fractions de clôture. La table de tendance a
une structure fondamentalement différente sur trois points, chacun
incompatible avec cette machine à états sans la réécrire complètement (donc
la "dénaturer") :
  1. Les étapes sont des ÉVÉNEMENTS DE STRUCTURE DE MARCHÉ détectés (Breakout,
     Divergence, Pull-Back, Excès final), pas des niveaux de prix fixes issus
     de l'entrée — deux trades identiques en taille peuvent avoir des
     Pull-Back/Excès déclenchés à des prix très différents selon la forme
     réelle du mouvement.
  2. Le renforcement se produit AVANT même la première "vraie" entrée
     (Accumulation, avant Breakout) pour 3 profils sur 4 — `position_engine`
     n'ouvre jamais de tranche tant qu'il n'y a pas de signal, il n'a pas de
     notion de "renfort pré-entrée".
  3. Le profil Très Agressif exige un mécanisme "+Reverse" (ouverture d'une
     position SHORT après la clôture totale du long) — `position_engine` est
     structurellement long-only (tous les tests, tous les moteurs v4-v7 ne
     gèrent qu'une liste de tranches longues).
Conclusion : un moteur dédié (ce fichier) est nécessaire. Il reprend
néanmoins la MÊME PHILOSOPHIE de factorisation que `position_engine.py`
(cf. `test_position_engine.py`) : la logique d'un pas de temps est isolée
dans des fonctions pures (`step_campaign`, `step_reverse`, `try_open_campaign`,
`add_leg`) qui ne recalculent aucun indicateur — elles reçoivent des
événements déjà résolus (booléens) en paramètre, exactement comme
`process_tranche` reçoit `long_signal_prev` déjà résolu plutôt que de
recalculer un score. C'est ce qui rend ce module testable unitairement
(`test_trend_table.py`) avec des cas calculés à la main.

================================================================================
HYPOTHÈSES D'IMPLÉMENTATION (le manuel est sous-spécifié sur ces points —
documentées ici honnêtement, PAS inventées en silence)
================================================================================
H1. **"Renfort +X%"** : le manuel ne précise pas l'unité de référence. On
    définit une UNITÉ (U) = taille dimensionnée par le risque de la même
    façon que v4-v7 (`risk_pct` du profil / distance en % au stop), et
    "Renfort +X%" = ajouter X% de U à la position. "Entrée 100%" (Breakout,
    profil Faible) = la toute première jambe = 1.00 x U.
H2. **Coût moyen pondéré ("blended"), pas FIFO/LIFO par jambe** : quand
    plusieurs jambes sont ouvertes à des prix différents (Accumulation +
    Breakout + Pull-Back), le P&L réalisé à chaque clôture partielle (TP
    Divergence, TP100% Excès final) est calculé contre un prix d'entrée
    moyen pondéré recalculé à chaque ajout — pas contre le prix de chaque
    jambe individuelle. Simplification usuelle (coût moyen d'achat),
    documentée plutôt que la vraie comptabilité "par jambe" qu'utilise
    `position_engine` pour ses tranches à taille fixe (où la question ne se
    posait pas).
H3. **Plafond de risque de campagne à 5%** : la §5 du manuel ("perte
    spéculative jamais >5% du capital, quel que soit le profil") est une
    règle dure GLOBALE, pas spécifique à la table range. Or additionner les
    "Renfort" du profil Très Agressif (Accumulation +100% + Breakout +200% +
    Pull-Back +100% = 4 x U, chacune dimensionnée par défaut à risk_pct=5%)
    violerait mécaniquement cette règle si on ne plafonnait rien (jusqu'à
    ~20% de risque cumulé). On plafonne donc le risque total de la CAMPAGNE
    (distance au stop x taille restante cumulée) à 5% : toute jambe qui
    dépasserait ce plafond est réduite (ou ignorée si le plafond est déjà
    atteint). Cette règle n'est écrite nulle part dans le §4 du manuel — elle
    est déduite de la §5 pour rendre la table applicable sans la violer.
H4. **Pas de stop "Invalidation" nommé pour cette table** (contrairement à
    la table range) : on réutilise le même "Extreme Channel" que v4-v7
    (`ctx_support`, bande EMA lente - 2xATR) comme stop de protection
    initial, fixé à l'entrée en position et non recalculé ensuite (comme
    v4-v7, PAS comme le recalcul dynamique de `backtest_phase2.py`). Cohérent
    avec la règle transverse §1 "ne jamais vendre la partie basse du canal
    de tendance" : le stop protège juste sous cette borne basse.
H5. **Rejet canal (Accumulation)** = la mèche basse touche/dépasse
    `ctx_support` (bande basse du canal) ET la clôture referme au-dessus —
    un rejet haussier classique. Faute d'un vrai canal Framework (jamais
    reconstruit, cf. COUVERTURE_ENSEIGNEMENTS.md item "canal de tendance
    manuel"), on réutilise la même approximation EMA±ATR que tout le projet.
H6. **Retracement (Accumulation 38-61%, Pull-Back 23-38%)** : PAS le module
    Fibonacci dédié (`backtest_phase2_fib.py`, en cours par un autre agent en
    parallèle sur cette branche) — calcul de profondeur de retracement
    minimal et autonome, propre à ce fichier, car la table de tendance a
    besoin d'un nombre de profondeur quel que soit l'état d'avancement du
    module Fibonacci séparé. Accumulation : profondeur dans le canal de
    CONTEXTE (`ctx_high`/`ctx_low`, fenêtre CONTEXT_DURATION). Pull-Back :
    profondeur du retracement de l'IMPULSION post-Breakout (du prix d'entrée
    Breakout au plus haut atteint depuis). Si le module Fibonacci séparé
    aboutit, il pourra remplacer ce calcul ad hoc plus tard — non fait ici
    pour ne pas dépendre d'un fichier en cours d'écriture par un autre agent.
H7. **"Retour min 50% contexte" (Pull-Back)** : interprété comme "au moins
    50% du retracement observé doit être regagné" (recovery_frac >= 0.50
    depuis le point bas du retracement vers le plus haut de l'impulsion) —
    pas "50% du canal de contexte" au sens absolu (ambigu dans le manuel).
    TENSION NON RÉCONCILIÉE (trouvée par `code/fibonacci.py`, cycle suivant,
    puis vérifiée adversarialement) : `TRADING_LESSONS_PULLBACK_MATURITE.md`
    (#13) donne, pour très probablement la MÊME étape Pull-Back de la MÊME
    table compressée que RULES_EXTRACTION.md §1, une "Règle des 50%"
    explicite à 2 conditions cumulatives — retracement >= 23% ET
    pénétration dans les 50% inférieurs du CANAL DE CONTEXTE (PAS un
    recovery_frac) — table GO/WAIT à l'appui ("Entre 23% et 38%" = GO). Une
    fois cette source relue, la lecture "50% du canal de contexte au sens
    absolu" — explicitement écartée ci-dessus comme "ambigu dans le
    manuel" — apparaît en réalité la mieux étayée des deux, pas la moins
    probable. `code/fibonacci.py::classify_regle_50` implémente cette
    lecture "canal de contexte", en recalculant très exactement
    `accum_retracement_frac` ci-dessous (même formule, vérifié bit-à-bit) —
    sans l'importer, pour ne pas créer de dépendance nouvelle (cohérent
    avec le "pourquoi un moteur séparé" en tête de fichier). **H7 n'est PAS
    modifiée ici** (changement de comportement de cette table hors périmètre
    de ce chantier, jamais fait sans décision explicite) — cette note
    documente seulement la tension pour qu'un futur lecteur de H7 la voie,
    plutôt que de la laisser visible uniquement côté `fibonacci.py`.
H8. **Divergence "standard"** : aucun détecteur de divergence réel n'existe
    dans le projet (le vrai calcul PRO Momentum n'est pas public,
    RULES_EXTRACTION.md préambule). Approximé par le retournement de la
    composante cycle du proxy (`cycle_favorable` qui passe de True à False)
    pendant que la structure reste haussière (prix > EMA de tendance) —
    cohérent avec la définition du proxy (`proxy_v2.py`) mais explicitement
    une approximation, pas une vraie divergence de momentum/prix détectée
    par pics successifs.
H9. **Volume (Breakout)** : les CSV bruts contiennent une vraie colonne
    `volume` (non exposée par `backtest_phase2.load_h1`, qui ne charge que
    OHLC) — ce module lit le volume directement depuis les mêmes fichiers
    pour rester fidèle à "cassure + VOLUME" plutôt que d'utiliser un proxy
    ATR. Condition : volume de la bougie de cassure > 1.5x sa moyenne
    mobile 20 périodes (glissante, causale).
H10. **"+Reverse" (Très Agressif, Excès final)** : implémentation SIMPLIFIÉE
    d'une position short bornée (stop au-dessus de `ctx_resistance`, cible de
    retour à `ctx_support`) — PAS une table à 5 étapes symétrique côté short
    (le manuel n'en décrit pas). Ce point était identifié comme "jamais
    construit" dans COUVERTURE_ENSEIGNEMENTS.md ; il est maintenant construit,
    mais dans une version bornée et documentée comme telle, pas une réplique
    complète du mécanisme long.
H11. **Portée réglage marché** : contrairement à `backtest_phase2_v7.py`,
    ce moteur ne fait PAS de validation croisée multi-timeframe (H4 validé
    par D1) — décision de scope volontaire pour mesurer la table de tendance
    ISOLÉMENT (le backlog liste MTF cross-validation et table de tendance
    comme deux lacunes distinctes ; les combiner aurait rendu le résultat de
    CE chantier illisible). Timeframe unique en entrée (H4 dans le script de
    backtest associé), comme v6. Hors régime TENDANCE : aucune position
    ouverte (pas de repli sur la table range, pour mesurer cette table
    isolément plutôt que mélangée à une performance déjà connue).

    NOTE ajoutée au 10e round de mobilisation (DOCUMENTATION SEULE, aucun
    changement de comportement — même discipline que la note H7 ci-dessus).
    `COUVERTURE_ENSEIGNEMENTS.md`/`PLAN.md` listaient en catégorie C un item
    « mécanisme d'emboîtement T/T-1 » en s'appuyant sur H11 (« `trend_table.py`
    reconnaît DÉJÀ lui-même être mono-timeframe »). **H11 et cet item ne
    parlent pas de la même chose, et la confusion est dans l'item, pas ici** :
    H11 décline la validation par l'UT SUPÉRIEURE (« H4 validé par D1 »), qui
    est la direction que le corpus prescrit réellement ; l'item demandait la
    structure de l'UT INFÉRIEURE (T-1). Investigué et tranché : NE PAS
    IMPLÉMENTER. Trois raisons mesurées, pour qu'un futur lecteur de H11 ne
    rouvre pas le chantier à l'aveugle :
      (a) La citation d'origine (`TRADING_LESSONS_ZONE_ACCUMULATION.md:13`,
          *"le canal de tendance observé sur votre unité de temps de contexte
          (T) n'est rien d'autre que la structure interne de l'unité de temps
          inférieure (T-1)"*) énonce une IDENTITÉ de lecture graphique, pas
          une procédure de calcul. Sa seule traduction opérationnelle dans
          tout le corpus est la projection vers le BAS — *"Extreme Channel
          (contexte de l'UT supérieure affiché sur l'UT de trading)"* (#16
          `TRADING_LESSONS_CLUSTERS_PRIX.md:12`), stop sous ce canal (#16:28,
          #12 `TRADING_LESSONS_BREAKOUT_RATIO11.md:7`, #10:38) — déjà
          implémentée SANS CONDITION ailleurs dans le projet (`ctx_support_d1`,
          `backtest_phase2_faithful.py` ; option `use_mtf_stop` de
          `backtest_phase2_ut2.py::run_ut2`). Jamais la recomputation d'une
          structure de rang inférieur.
      (b) Mesuré : la seule grandeur numérique du gate Accumulation,
          `accum_retracement_frac`, ne porte AUCUNE information T-1.
          `ctx_high`/`ctx_low` calculés en H1 puis joints causalement au H4
          (même `merge_asof` que `attach_context_level`, closure_delay=1h)
          sont identiques aux valeurs H4 natives sur 94,6-95,5% des barres,
          et sur **100,00%** une fois neutralisé l'artefact de granularité du
          `shift(1)` de `add_trend_context` (1 barre = 1h vs 4h) : un max/min
          sur fenêtre CALENDAIRE est exactement invariant par agrégation de
          bougies. La clôture H1 jointe est celle de la bougie H4 précédente
          sur 100% des barres. Et le gate ADDITIF « structure T-1 mature »
          est inerte bit-à-bit : 7/7, 9/9, 16/16, 8/8 déclenchements
          Accumulation (BTC/ETH/BNB/SOL, historique complet), écart 0 —
          `n_borders` vaut 32-34 au MINIMUM en H1 sur les barres candidates
          contre un seuil `MIN_BORDERS=3` (même « gate inerte » qu'aux 6e et
          8e rounds).
      (c) La seule composante réellement dépendante du niveau est la bande
          EMA±ATR — et dans la direction que le corpus prescrit (vers le
          HAUT), elle est incompatible avec H3 dans CE moteur : un stop posé
          sur le canal D1 passe de 1,20-2,26% à 14,75-19,88% de distance
          (×8,6 à ×14,6), ce qui plafonne la campagne entière à 0,25-0,34 du
          capital au lieu de 2,2-4,2 — les 4 profils s'écrasent sur le MÊME
          plafond et la table §4 (Renfort +25/+50/+100/+150/+200%), seul objet
          que ce fichier existe pour mesurer, devient inexprimable.
          (`position_engine.py` n'a pas ce problème : il dimensionne chaque
          tranche indépendamment, `risk_pct / stop_pct`, sans plafond cumulé
          de campagne.) Et utiliser le canal D1 comme référence du REJET fait
          tomber les déclenchements Accumulation de 7/9/16/8 à 0/0/0/3.
    Détail complet, citations vérifiées mot pour mot et tensions de sources :
    `PLAN.md` section "10e application", `COUVERTURE_ENSEIGNEMENTS.md`.
H12. **Une seule campagne active à la fois** ("un seul tracker actif",
    principe du projet appliqué ici aussi à l'échelle d'une position) : pas
    de pyramidalisation de PLUSIEURS campagnes de tendance en parallèle,
    contrairement à v4-v7 (`MAX_TRANCHES=3` sur des ENTRÉES indépendantes).
    Ici, une seule campagne (avec ses propres jambes internes) peut être
    active ; une nouvelle campagne ne peut démarrer qu'une fois la
    précédente entièrement close (et le "+Reverse" éventuel dénoué, règle
    transverse "jamais passer de haussier à baissier sans repasser par un
    range").
H13. **Contrainte "espace libre" MTF avant le Breakout** (`use_breakout_space_gate`,
    défaut `False` — le comportement historique de ce moteur est préservé
    BIT-À-BIT quand le paramètre n'est pas passé). Citation de départ,
    vérifiée mot pour mot dans `TRADING_LESSONS_BREAKOUT_RATIO11.md` ligne
    17 (source #12) :

        *"Contrainte Multi-Timeframe (MTF) : il est impératif de vérifier
        l'absence d'obstacles sur les unités de temps supérieures (UT+1 et
        UT+2). Le breakout doit disposer d'un 'rendement escompté'
        suffisant, c'est-à-dire d'un espace libre de toute structure
        majeure pour permettre l'épanouissement de la tendance."*

    2e source INDÉPENDANTE du même mécanisme, `TRADING_LESSONS_PULLBACK_
    MATURITE.md` ligne 14 (source #13, hiérarchie à 3 niveaux) : *"UT
    Supérieure ('Le Potentiel') : vérifier qu'il reste assez de 'jus'
    (marge de progression) pour un nouvel objectif"*.

    **Pourquoi ce chantier est légitime ICI alors que l'amplitude
    Validation/Confirmation cross-timeframe a été refusée pour la table
    RANGE** (cf. `PLAN.md` section "7e application") : la raison de refus
    n°1 de ce round-là était que le corpus ne budgète que 2 UT à la table
    RANGE. La MÊME citation (`TRADING_LESSONS_MTF_SUIVI_TENDANCE.md` ligne
    13, revérifiée mot pour mot) dit l'INVERSE pour la table TENDANCE —
    celle de CE fichier : *"| Unités de temps | 2 UT (ex: Daily/H4)
    [Range] | **3 UT impératives** (ex: Mensuel/Hebdo/Daily) [Tendance] |"*,
    et ligne 15 : *"| Hiérarchie | Dépend de l'UT supérieure | Nécessite
    validation sur **2 UT supérieures** |"*. La table de tendance a donc
    explicitement DROIT à un UT+1 ET un UT+2 réels ; ce gate est le premier
    endroit du projet où cette ligne du corpus est appliquée à la table
    qu'elle vise.

    Règle distincte, vérifiée, de deux règles MTF déjà implémentées — ce
    n'est pas un doublon : (a) "Conflit MTF" (`TRADING_LESSONS_MAITRISE_
    GRADIENT_RISQUE.md` ligne 7, *"Ne jamais trader une borne de range si
    un range d'unité de temps supérieure est déjà actif"*) porte sur le
    RÉGIME d'un trade de RANGE, pas sur la place disponible ; (b) "Rigueur
    Multi-Timeframe" (même source #12, ligne 21, *"Si l'UT+1 est en fin de
    cycle, le breakout local est un piège"*) porte sur la PHASE DE CYCLE de
    l'UT+1, pas sur une distance.
H14. **Ce qu'est une "structure majeure" sur UT+1/UT+2** : la borne HAUTE du
    canal "Extreme Channel" de ce niveau (`ctx_resistance` = ema_slow +
    2xATR, la définition déjà utilisée par ce fichier depuis
    `add_trend_context`), calculée sur de VRAIES bougies D1 (UT+1) et
    Hebdomadaires (UT+2) et transmise sans lookahead. **Aucun détecteur de
    structure n'est inventé ici** (c'était le motif de refus du gate
    Fibonacci RANGE) : c'est le miroir exact du `ctx_support` que le corpus
    fait déjà servir de structure de référence pour le stop UT+1, et le
    corpus traite lui-même la borne opposée du canal comme la structure que
    le prix vient buter (`TRADING_LESSONS_ZONE_ACCUMULATION.md` ligne 40 :
    *"Validation : prix atteint la borne opposée du canal de tendance"*).
    **`ctx_high` (max glissant 15 jours) a été explicitement ÉCARTÉ** comme
    candidat : mesuré ici, c'est un quasi no-op entre UT (marge médiane
    jusqu'à l'obstacle 6,22% en H4 / 6,36% en D1 / 7,47% en Hebdo sur BTC),
    exactement l'invariance par agrégation déjà mesurée au round précédent
    pour `max(high)-min(low)`. `ctx_resistance`, path-dépendant (EMA+ATR),
    ne l'est PAS : marge médiane 2,52% en H4 / 5,99% en D1 / 8,50% en Hebdo
    (BTC), ratio médian D1/H4 = 2,1-2,4x et Hebdo/H4 = 2,8-5,5x selon
    l'actif. Le gate mesure donc bien quelque chose de propre aux UT
    supérieures, ce n'est pas le même nombre sous un autre nom.
H15. **Ce qu'est le "rendement escompté" du breakout** : l'amplitude du range
    d'accumulation local, c'est-à-dire l'objectif "Ratio 1:1 Tendance" que
    la MÊME source définit 9 lignes plus haut (`TRADING_LESSONS_BREAKOUT_
    RATIO11.md` ligne 8, vérifié : *"Phase de Validation (Ratio 1:1
    Tendance) : projeter l'amplitude du range d'accumulation local (UT)"* —
    UT LOCALE, point déjà vérifié au round précédent). Grandeur déjà
    calculée par `backtest_phase2_v7.prepare` (`local_range`, fenêtre
    LOCAL_DURATION sur l'UT d'exécution) et jusqu'ici simplement jamais lue
    par ce fichier. Le multiplicateur `space_mult` vaut 1.0 par défaut
    (= Ratio 1:1, la seule valeur citée par le corpus) et reste un
    paramètre pour permettre une mesure de sensibilité — PAS pour être
    calibré sur la performance.
H16. **Un niveau ne compte comme OBSTACLE que s'il est AU-DESSUS du prix.**
    S'il est déjà sous le prix au moment du breakout, il est franchi : il ne
    borne plus l'espace au-dessus, la marge disponible de ce côté est donc
    considérée comme non bornée (`+inf`). C'est la lecture littérale de
    *"absence d'obstacles"* — et ce n'est pas un détail : mesuré sur les
    bougies candidates au breakout, la borne haute du canal D1 n'est
    au-dessus du prix que dans 41-51% des cas et celle de l'Hebdo dans
    51-63% des cas selon l'actif. Un niveau INCONNU (NaN, warmup du niveau
    supérieur) fait au contraire ÉCHOUER le gate — *"il est impératif de
    VÉRIFIER"* ne peut pas être satisfait sans donnée, et c'est la
    convention déjà en place partout ailleurs (`valid_inputs` ici,
    `backtest_phase2_ut2._aligned`). En pratique inerte sur les données
    testées : 0,00% de NaN sur D1 comme sur Hebdo une fois le warmup H4
    passé (2117-2374 bougies D1, 303-340 bougies Hebdo selon l'actif).
H17. **Portée du gate : l'étape Breakout UNIQUEMENT** (*"avant un
    breakout"*), pas l'ouverture de campagne en Accumulation, pas le
    renfort de Pull-Back, pas l'Excès final — le corpus ne parle d'espace
    libre que pour le breakout. H11 (ce moteur est volontairement
    mono-timeframe) reste vrai par défaut : le gate est OPTIONNEL et
    désactivé par défaut, exactement comme `use_mtf_stop`/`use_fib_gate`
    ailleurs, pour que la mesure isolée de la table de tendance reste
    comparable à tout l'historique déjà publié.

-----------------------------------------------------------------------------
NOTE DOCUMENTAIRE — "Altérations de structure Vague 1 / Vague 5" (#14,
`TRADING_LESSONS_STRUCTURES_ALTERATIONS.md`) : INVESTIGUÉ à la 14e
application, PAS IMPLÉMENTÉ, item FERMÉ. **Zéro comportement** : ce bloc ne
fait que documenter une décision, aucune ligne exécutable n'est ajoutée.
-----------------------------------------------------------------------------
Item de catégorie C énoncé par `COUVERTURE_ENSEIGNEMENTS.md` comme *"Overlap,
stratégie 'Rivière', prises de profit partielles Vague 5 — cadre de type
Elliott non repris, ne correspond pas au modèle 5 étapes déjà en place"*.

**La 2e moitié de cet énoncé est FAUSSE, et c'est le point le plus important
de l'investigation.** La source #14 ne propose PAS un cadre concurrent du
modèle 5 étapes : elle DÉCRIT ce modèle, et le désigne comme la norme. Ses
lignes 5-11, vérifiées mot pour mot :

    l.5  "## « La Maison de la Tendance » — modèle canonique (Vague 3
          étendue = la norme)"
    l.6  "5 briques constitutives, cohérent avec le cycle à 6 phases de la
          source #13 :"
    l.7-11  Accumulation / Breakout / Divergence / Pullback / Excès Final

C'est, nom pour nom et dans le même ordre, la séquence de `RULES_EXTRACTION.md`
§4 (*"5 étapes : Accumulation → Breakout → Divergence → Pull-Back → Excès
final"*) et §1 l.23 — donc EXACTEMENT ce que ce fichier implémente. La
"Vague 3 étendue" du vocabulaire de #14 est le nom que cette source donne au
cas canonique DÉJÀ codé ici ; "Vague 1 étendue" et "Vague 5 étendue" sont
deux ALTÉRATIONS de ce même modèle, pas un formalisme rival. Le mot
"Elliott" n'apparaît d'ailleurs NULLE PART dans le corpus (grep exhaustif
des 17 sources + `RULES_EXTRACTION.md` : 0 occurrence) — c'est une glose du
projet, pas le vocabulaire de Philippe, et elle ne peut donc pas servir de
motif d'écartement.

Les autres contenus de #14 hors altérations sont eux aussi DÉJÀ couverts :
l.13 (*"maturité du range (min. 3 bornes testées)"*) = `MIN_BORDERS = 3`,
source déjà citée comme telle par `min_borders_sensitivity.py` ; l.17 (*"Loi
de l'Unité de Temps Supérieure"*) = 5e confirmation de la famille MTF, déjà
implémentée (gates UT+1/UT+2) ; l.21-23 (maturation du Bitcoin) est une note
de calibration documentaire, pas une règle.

Restent les 3 éléments réellement non couverts, tranchés un par un.

(1) **Règle de l'Overlap (l.28) — DÉJÀ IMPLÉMENTÉE, sous un autre nom, et
    mesurément ACTIVE** (motif (d) de la règle inviolable). Citation :

        "Règle de l'Overlap : l'ancienne résistance devient support. C'est
         une zone de tolérance, pas une ligne mathématique — les mèches
         peuvent pénétrer l'ancien territoire, mais les clôtures de bougies
         doivent rester à l'extérieur pour valider la structure."

    Son contenu opératoire est exactement la convention de `breakout_raw`
    (`c[i-1] > local_high_v[i-1]`) et d'`excess_raw` (`c[i] > ctx_high_v[i-1]`)
    : le NIVEAU est un extrême (`local_high`/`ctx_high` = max glissant des
    HAUTS, `add_trend_context`), la CLÔTURE est le test, la mèche ne
    déclenche rien. Ce n'est pas une conformité de façade : mesuré sur
    BTC/ETH/BNB/SOL H4 (historique complet), valider sur la mèche au lieu de
    la clôture ferait passer les cassures de 307/287/296/253 à
    453/438/465/374 — la clause "clôtures" REJETTE **32,2% à 36,3%** des
    candidates au Breakout et **43,5% à 46,7%** de celles de l'Excès final.
    Verrouillé par `test_trend_table.py::
    test_overlap_convention_already_in_breakout_raw` (contrôles positif ET
    négatif ; le test échoue bien si l'on bascule le moteur sur la mèche).
    C'est aussi, déjà, la lecture que les 8e et 12e rounds avaient tirée de
    cette même ligne 28 pour un sujet différent (clôtures vs mèches).

    La seule lecture NON couverte est la validité CONTINUE ("après la
    cassure, les clôtures doivent RESTER au-dessus du niveau"). Écartée pour
    deux raisons, la seconde mesurée :
      (a) la source ne dit PAS quoi faire quand la condition cesse d'être
          vraie — "pour valider la structure" qualifie une lecture
          graphique, jamais un ordre de sortie ni de réduction. En faire un
          mécanisme de clôture exigerait d'inventer l'action (motif (b)).
      (b) l'action la plus naturelle (sortir) reviendrait à REMPLACER le
          stop littéral du corpus par un stop bien plus serré. Mesuré : le
          niveau cassé se situe à **−0,11 à −0,13 R** de l'entrée (médiane,
          R = distance entrée→stop) — donc SOUS l'entrée, à ~12% seulement
          du chemin vers le stop, et **jamais** au-dessus du break-even
          (0,0% des cas sur les 4 actifs). Il serait touché AVANT le stop
          réel dans **85,8% à 90,9%** des cassures, en 4 à 7,5 bougies
          (médiane). Autrement dit : un stop ~8× plus serré que celui que
          le corpus prescrit littéralement (*"Stop-loss = clôture la plus
          basse du canal de tendance de l'UT+1"*, #12:7, confirmé #16:28,
          #10:38) — sacrifier un élément MIEUX établi au profit d'une
          lecture plus ambiguë, soit exactement le motif (c).

(2) **Stratégie de la "Rivière" (l.30) — objet réellement distinct, mais
    action non fournie par le corpus** (motif (b)). Citation :

        "Pour les plus expérimentés, le point de retournement (« River ») se
         cherche au contact de la ligne de tendance reliant les deux sommets
         précédents, pas sur le contexte horizontal."

    Vérifié : cette ligne n'a AUCUN équivalent ailleurs dans le corpus
    (grep "Rivière"/"River" sur les 17 sources + le manuel : 1 occurrence,
    celle-ci). L'objet géométrique, lui, est constructible sans rien
    inventer, en réutilisant les primitives existantes
    (`proxy_v2.compute_swing_high_confirmed`, `SWING_ORDER`, exactement ce
    que `manual_trend_channel.py` H1 fait pour les creux) : mesuré,
    couverture **99,8-99,9%** des bougies, et c'est bien un objet NOUVEAU
    (écart médian **2,9-5,4%** vs `ctx_resistance`, **3,7-7,2%** vs la
    résistance du canal manuel Supports→Apex→Tangente, **4,5-9,3%** vs
    `ctx_high` ; distinct aussi de `andrews_pitchfork.py`, qui part de
    pivots ALTERNÉS creux/sommet, pas de deux sommets consécutifs).

    Ce qui bloque n'est donc pas la faisabilité, c'est le DÉCLENCHEUR : le
    corpus dit où *"se cherche"* le point de retournement, jamais ce qui le
    confirme ni ce qu'on en fait. Et le "contact" seul ne peut pas tenir
    lieu de signal — mesuré, le haut de la bougie atteint cette ligne sur
    **30,1% à 32,1%** des bougies, soit près d'une sur trois. Toute règle
    utilisable exigerait d'inventer un critère de confirmation absent du
    corpus. S'y ajoutent deux restrictions explicites de la source
    elle-même : *"Pour les plus expérimentés"*, et une portée limitée à la
    Vague 1 étendue en phase de "double excès" (cf. (3) sur l'impossibilité
    d'identifier ces états). Le reste de la l.30 est du conseil
    comportemental déjà couvert : *"attendre le pullback technique"* est
    l'étape PULLBACK_WATCH de ce fichier, et *"ne pas courir après le prix"*
    est structurel (ce moteur n'entre que sur déclencheurs définis).

(3) **Prises de profit partielles "Vague 5" (l.37) — mécanisme déjà en
    place, jeu d'objectifs non définissable** (motifs (d) puis (b)).
    Citation :

        "Il faut déclencher des prises de profit partielles systématiques
         sur objectifs prédéfinis : niveaux de résistance équivalents,
         extensions de Fibonacci, chiffres ronds (niveaux psychologiques)."

    Le MÉCANISME (sortir par fractions plutôt qu'en une fois) est déjà
    implémenté et l'est d'après une autorité plus haute que #14 : la table
    §4 du manuel (`div_close_frac` = TP50%/TP25% à la Divergence, TP100% à
    l'Excès final ; côté RANGE, `val_close_frac`/`conf_close_frac` pour §3).
    Ce qui diffère est le DÉCLENCHEUR : #14 propose des OBJECTIFS DE PRIX
    là où le manuel prescrit des ÉTAPES DE STRUCTURE. Or aucun des trois
    objectifs cités n'est définissable à partir du corpus :
      - *"extensions de Fibonacci"* : **aucun ratio d'extension n'existe
        dans tout le corpus** (grep 127 / 138 / 161 / 261 sur les 17 sources
        + `RULES_EXTRACTION.md` : 0 occurrence). Tous les nombres Fibonacci
        du corpus sont des RETRACEMENTS (23/38/50/61/76), déjà traités par
        `fibonacci.py` — qui signale d'ailleurs depuis sa création que #14
        parle d'extensions "pour la PRISE DE PROFIT en Vague 5", sans
        pouvoir les chiffrer.
      - *"niveaux de résistance équivalents"* : expression unique dans tout
        le corpus, jamais définie.
      - *"chiffres ronds (niveaux psychologiques)"* : aucune granularité
        donnée (1 000 $ ? 10 000 $ ? un ordre de grandeur relatif ?).
      - et la FRACTION à sortir sur chaque objectif n'est jamais donnée non
        plus.
    Quatre paramètres à inventer pour une règle dont le mécanisme est déjà
    couvert : c'est le motif (b) sous sa forme la plus nette, et le même
    refus que celui déjà opposé au gate Fibonacci RANGE (2 définitions
    manquantes) depuis plusieurs rounds.

    **Point mesuré à ne pas cacher, car il va CONTRE la thèse commode** :
    on aurait pu croire la question sans objet, la Vague 5 (euphorie) étant
    déjà exclue par le régime EXCES que `RULES_EXTRACTION.md` §1 interdit de
    trader. C'est FAUX. Mesuré sur les bougies du centile supérieur de
    rendement sur 30 bougies H4 (diagnostic d'accélération parabolique, pas
    une règle) : seulement **40,6% à 55,0%** sont étiquetées EXCES, tandis
    que **35,7% à 51,0%** sont en TENDANCE, donc tradables (base de
    comparaison : 17,1-19,6% d'EXCES toutes bougies confondues). La
    population existe bel et bien ; ce n'est donc PAS la redondance qui
    tranche ici, c'est uniquement l'absence de définitions.

    S'y ajoute un blocage amont, indépendant : la source subordonne
    explicitement tout cela à une identification préalable — l.54, *"Identifiez
    d'abord la structure, déterminez le type d'extension, et seulement
    ensuite, appliquez vos outils de gestion du risque"* — et exige de
    distinguer Vague 5 étendue et Bulle (l.39 : *"une Vague 5 étendue déplace
    la valeur d'un point A vers un point B et stabilise un nouveau range ;
    une bulle est un écart irrationnel à la valeur réelle"*), distinction que
    `regime_classifier.add_regime` ne porte pas (EXCES = canal trop large OU
    trop étroit, rien qui sépare les deux) et que le corpus ne rend nulle
    part calculable.

**Direction de l'effet, dite honnêtement** : non mesurée, parce qu'aucune des
3 variantes n'est implémentable sans inventer au moins un paramètre — il n'y
a donc pas de "variante fidèle" dont on pourrait mesurer le rendement. Le
seul chiffre de performance qui aurait pu être produit (l'Overlap comme
sortie) est écarté par (1)(b) sur un motif de corpus, pas de performance.
Aucun CSV n'est régénéré : rien ne change numériquement.

================================================================================
NOTE (15e application) — "Cluster technique" de la MÊME source #12
(l.29) : EXAMINÉ, DÉLIBÉRÉMENT PAS IMPLÉMENTÉ. Zéro comportement, aucune
ligne exécutable ajoutée par cette note.
================================================================================
Cette note existe pour qu'un futur lecteur de `breakout_raw` voie que la
règle a été examinée et pourquoi elle n'est pas ici — pas pour qu'il croie
à un oubli. Même discipline que la note Red Flags de `position_engine.py`
et la note H7 ci-dessus.

CITATION, vérifiée mot pour mot (`TRADING_LESSONS_BREAKOUT_RATIO11.md`
ligne 29, section *"Critères de maturité avant breakout"*) :

    - **Cluster technique** : le breakout ne se traite pas sur un niveau
      isolé, mais sur la convergence de plusieurs informations (trendlines
      majeures, bornes de canaux de contexte, limites de range) en une
      même zone

PRÉMISSE DE L'ITEM : EXACTE, contrairement aux 7e/8e/9e/11e rounds.
`breakout_raw` (ci-dessous) teste bien UN SEUL niveau de prix —
`c[i-1] > local_high_v[i-1]` — accompagné de deux conditions qui ne sont
pas des structures de prix (expansion de volume H9, `score >= 2`). Le gate
H13-H17 ajouté au 10e round vient de la même source mais mesure l'espace
LIBRE AU-DESSUS (obstacles UT+1/UT+2), pas une convergence AU niveau cassé :
ce n'est pas un doublon, et le manque signalé est réel.

À NE PAS CONFONDRE — le corpus emploie "cluster" pour TROIS choses
distinctes, dont deux sont déjà codées sous d'autres noms (piège
terminologique de la même famille que les trois "MA20" documentées au
9e round) :
  (1) ICI (#12:29) : convergence de STRUCTURES DE PRIX en une zone, AVANT
      le breakout. Non implémenté (cette note).
  (2) #16 (`TRADING_LESSONS_CLUSTERS_PRIX.md:19`) : le "Cluster Technique"
      MA20 + Zone de Demande, APRÈS le breakout, comme signal d'ENTRÉE en
      mean-reversion — implémenté dans `cluster_technique.py`, consommé
      par `diversification.py` (Pattern B). Sa propre docstring (H2)
      nomme déjà sa conjonction *"confluence de deux techniques au même
      endroit"* : le PRINCIPE de confluence existe donc dans le projet,
      mais pour les composants de #16, à son moment à elle.
  (3) #10:25 (*"Retracement dans un cluster 38-50%"*) et #13:48
      (*"Cluster Fibonacci | Entre 23% et 38%"*) : "cluster" y désigne une
      BANDE de retracement, pas une convergence — déjà implémenté
      (`ACCUM_RETRACEMENT_LOW/HIGH` ici, `fibonacci.py`).
Voisin utile, dans le sens de (1) : #5:66 (*"Zone spéculative : prix dans
le cluster (Fibonacci + zone graphique) ?"*) — cette convergence-là est
déjà, de fait, ce que `try_open_campaign` exige à l'Accumulation
(retracement 38-61% ET rejet du canal sur la même bougie).

POURQUOI PAS IMPLÉMENTÉ — 4 raisons, chacune vérifiée ou mesurée :

1. DEUX PARAMÈTRES SERAIENT À INVENTER, et le corpus n'en donne aucun.
   *"plusieurs informations"* ne dit pas COMBIEN ; *"en une même zone"* ne
   dit pas à quelle DISTANCE. Grep exhaustif des 17 sources +
   `RULES_EXTRACTION.md` sur `convergen`/`confluen`/`cluster`/`trendline`/
   `tolérance`/`proximité`/`distance` : aucun chiffre nulle part pour cette
   règle, et le manuel officiel — l'autorité la plus haute du projet — ne
   contient **aucune occurrence** de convergence/confluence/cluster/
   trendline. Le seul énoncé voisin du corpus sur la largeur d'une zone
   refuse explicitement de la chiffrer (#14:28, *"zone de tolérance, pas
   une ligne mathématique"*). C'est le motif de refus déjà retenu pour le
   gate Fibonacci RANGE §1 ("débordement"/"triangle") et pour le Red
   Flag 2 ("maintenue" non chiffré).

2. MESURÉ : CE SONT CES DEUX PARAMÈTRES INVENTÉS, PAS LA RÈGLE, QUI
   DÉCIDERAIENT DU RÉSULTAT — même schéma décisif que le niveau de
   contexte de Conflit MTF (89% vs 12-19%) et que le 13e round. Sur les
   264-312 bougies candidates au breakout de BTC/ETH/BNB/SOL H4, en
   prenant les 3 familles CITÉES par la source, chacune déjà calculée par
   le projet (limites de range = `ctx_high` ; bornes de canaux de contexte
   = `ctx_resistance`, H14 ; trendlines majeures = `channel_resistance` de
   `manual_trend_channel.py`), la part de candidates ACCEPTÉES par un gate
   de convergence balaie **tout l'espace des résultats possibles** :

       tolérance      N>=1        N>=2        N>=3
       0,25 %      59,8-65,1 %  3,0-4,7 %   0,0-0,7 %
       1 %         80,3-90,4 %  14,0-32,4 % 1,5-6,1 %
       5 %         98,9-100 %   75,0-90,7 % 33,7-65,4 %

   En exprimant plutôt la tolérance dans la seule unité de "zone" que le
   projet possède déjà (la demi-largeur du canal, k x ATR) : de 1,0-4,2 %
   d'acceptation (N>=3, 0,5xATR) à 99,6-100 % (N>=1, 2xATR). Aucun
   argument textuel ne permet de choisir un point dans cet intervalle.

3. UNE DES TROIS FAMILLES CITÉES N'EST PAS INDÉPENDANTE DU NIVEAU CASSÉ,
   dans les approximations de ce projet. `local_high` (le niveau que
   `breakout_raw` franchit) et `ctx_high` (les "limites de range") sont
   deux maxima de LA MÊME série de HAUTS sur des fenêtres EMBOÎTÉES
   (LOCAL_DURATION 5D ⊂ CONTEXT_DURATION 15D) : mesuré, `ctx_high >=
   local_high` sur **100,0 %** des candidates et **exactement égal sur
   51,9-56,9 %** d'entre elles. Compter `ctx_high` comme une information
   qui "converge" reviendrait donc, une fois sur deux, à compter le niveau
   de référence avec lui-même. Propriété verrouillée par
   `test_trend_table.py::test_range_limit_is_not_independent_of_the_broken_level`
   (vérité terrain synthétique, contrôle positif ; non-vacuité vérifiée par
   contrôle négatif). Le 10e round avait déjà écarté `ctx_high` comme
   candidat pour H14, pour une raison voisine (quasi no-op entre UT).

4. IMPLÉMENTER SACRIFIERAIT UN ÉLÉMENT DU CORPUS MIEUX ÉTABLI — même
   arbitrage qu'au 7e round. Mesuré en branchant le gate sur le hook
   existant `use_breakout_space_gate` (mesure en scratchpad, aucun fichier
   de production modifié) : le temps passé en POST_BREAKOUT par BTC/FAIBLE
   — la SEULE instanciation empirique substantielle des étapes 2 à 5 de
   `RULES_EXTRACTION.md` §4, le manuel officiel — tombe de **48,9 % à
   0,0 %** pour tous les réglages testés SAUF les deux plus permissifs
   (N>=1 et N>=2 à 2xATR, où il reste à 48,9 %). Autrement dit : c'est la
   tolérance inventée, seule, qui décide si la table de tendance du manuel
   continue d'exister empiriquement ou non. Sacrifier §4 (manuel, autorité
   la plus haute) pour une puce de note vidéo sans chiffre n'est pas un
   gain de fidélité. Honnêteté sur cette mesure : l'échantillon est très
   mince (8 breakouts au total, profil FAIBLE seul, cf.
   `COUVERTURE_ENSEIGNEMENTS.md`), donc le chiffre exact est fragile — la
   raison 4 renforce les raisons 1-3, elle ne les remplace pas.

NUANCE HONNÊTE, DANS L'AUTRE SENS (pour ne pas surcharger le refus) : la
ligne 29 est une PUCE DE SYNTHÈSE rédigée par le preneur de notes, pas une
phrase entre guillemets attribuée à Philippe — contrairement aux l.11/17/
21/24/38 de la même source, dont l.17 que le 10e round a implémentée. Ce
n'est PAS un motif de refus (le projet implémente ce que le corpus
documente, quelle qu'en soit la forme) et ça n'a joué aucun rôle dans la
décision ci-dessus ; c'est noté parce que la précision moindre de la
formulation explique en partie l'absence de tout paramètre.

CE QU'IL FAUDRAIT POUR ROUVRIR L'ITEM (pas "jamais", mais pas "à l'aveugle")
: une citation du corpus donnant SOIT un nombre de structures, SOIT une
tolérance de distance — ou une reformulation de la règle en un prédicat
qui n'en exige aucun des deux.

Correction faite EN COURS D'ÉCRITURE (pas après coup) : la première version
de ce fichier n'accumulait pas le P&L des clôtures partielles (Divergence)
dans une valeur unique avant de l'ajouter à la liste des trades -- un
scénario où la Divergence prend un profit puis le stop est touché sur le
reliquat aurait été comptabilisé comme une PERTE dans win_rate/profit_factor
même si le solde net de la campagne était positif. Corrigé en introduisant
`pnl_accum` (même convention que `position_engine.process_tranche`), qui
cumule chaque clôture partielle et n'est ajouté à `trades` qu'à la clôture
FINALE de la campagne (comme `tr["pnl_accum"]` dans position_engine.py).
"""
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, ".")
sys.path.insert(0, "/home/user/emile/code")
from backtest_phase2 import FEE, EMA_SLOW  # lecture seule, aucune modification
from backtest_phase2_v7 import prepare, LOCAL_DURATION, CONTEXT_DURATION, MIN_BORDERS  # idem
# UNE seule définition du délai de clôture réelle d'une bougie de niveau
# supérieur dans tout le projet (1 jour pour D1 ET pour l'Hebdomadaire avec la
# convention `resample()` de ce projet -- démonstration et vérification
# bit-à-bit dans `backtest_phase2_ut2.py`/`test_ut2.py`) : réutilisée telle
# quelle ici plutôt que redécidée, cf. H13/H16.
from backtest_phase2_ut2 import CLOSURE_DELAY  # lecture seule, aucune modification

# --- Constantes de détection des étapes (cf. hypothèses H5-H9 ci-dessus) ---
ACCUM_RETRACEMENT_LOW, ACCUM_RETRACEMENT_HIGH = 0.38, 0.61        # RULES_EXTRACTION §1
PULLBACK_RETRACEMENT_LOW, PULLBACK_RETRACEMENT_HIGH = 0.23, 0.38  # RULES_EXTRACTION §1
PULLBACK_RECOVERY_FRAC = 0.50                                     # H7
VOLUME_MA_WINDOW = 20
VOLUME_EXPANSION_MULT = 1.5                                       # H9
MAX_CAMPAIGN_RISK_PCT = 0.05                                      # H3, RULES_EXTRACTION §5
BREAKOUT_SPACE_MULT = 1.0                                         # H15, "Ratio 1:1"

# --- Table de money management "trade de tendance" (RULES_EXTRACTION §4) ---
# accum_frac / breakout_frac / pullback_frac : fractions de l'unité U ajoutées
# à chaque étape (H1). div_close_frac / div_to_be : action à la Divergence.
#
# NOTE DOCUMENTAIRE (17e application, AUCUN comportement) -- la colonne
# `accum_frac` ci-dessous EST le sizing de l'étape Accumulation prescrit par le
# manuel, `RULES_EXTRACTION.md:54-59` ("Attente" / "Renfort +25%" / "+50%" /
# "+100%" -> 0.00 / 0.25 / 0.50 / 1.00, correspondance exacte des 4 lignes).
# C'est à ce titre qu'elle a servi de motif (c) au refus d'implémenter l'item
# "sizing 1-1,5% spécifique aux trades d'accumulation" (#10:37) : un 1-1,5%
# fixe écraserait cette ligne du manuel et rendrait les 4 profils identiques à
# l'accumulation (perte de l'"Attente" de FAIBLE et du "+100%" de
# TRES_AGRESSIF). Décision complète, citations vérifiées et mesures : bloc
# dédié en tête de `position_engine.py`, `PLAN.md` section "17e
# application", `COUVERTURE_ENSEIGNEMENTS.md`, `STATUS.md`.
PROFILES_TREND = {
    "FAIBLE":        {"risk_pct": 0.01, "accum_frac": 0.00, "breakout_frac": 1.00,
                       "div_close_frac": 0.50, "div_to_be": True,  "pullback_frac": 0.00, "reverse": False},
    "MODERE":        {"risk_pct": 0.02, "accum_frac": 0.25, "breakout_frac": 1.00,
                       "div_close_frac": 0.25, "div_to_be": True,  "pullback_frac": 0.00, "reverse": False},
    "AGRESSIF":      {"risk_pct": 0.03, "accum_frac": 0.50, "breakout_frac": 1.50,
                       "div_close_frac": 0.25, "div_to_be": False, "pullback_frac": 0.50, "reverse": False},
    "TRES_AGRESSIF": {"risk_pct": 0.05, "accum_frac": 1.00, "breakout_frac": 2.00,
                       "div_close_frac": 0.25, "div_to_be": False, "pullback_frac": 1.00, "reverse": True},
}


# ---------------------------------------------------------------------------
# Préparation des données (indicateurs, réutilisant proxy_v2/regime_classifier
# via backtest_phase2_v7.prepare, + colonnes propres à la table de tendance)
# ---------------------------------------------------------------------------
def add_trend_context(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute les colonnes propres à la détection des 5 étapes, en plus de
    celles déjà posées par `backtest_phase2_v7.prepare` (score, atr, regime,
    ctx_support, local_range, context_range, n_borders). Toutes les colonnes
    ajoutées ici sont calculées de façon causale (rolling, jamais de
    lookahead)."""
    df = df.copy()
    ema_slow = df["ctx_support"] + 2 * df["atr"]        # inverse de v7::prepare (ctx_support = ema_slow - 2*atr)
    df["ctx_resistance"] = ema_slow + 2 * df["atr"]      # bande haute du canal (jamais calculée par v7, qui ne stoppe que long)

    # shift(1) : même convention que regime_classifier.add_regime (percentiles
    # adaptatifs) -- exclut la bougie courante du rolling max/min, sinon
    # "close > high_glissant" serait tautologiquement impossible (le high
    # glissant inclurait toujours la bougie qu'on teste, qui majore forcément
    # sa propre clôture).
    ts = df.set_index("date")
    df["ctx_high"] = ts["high"].rolling(CONTEXT_DURATION).max().shift(1).values
    df["ctx_low"] = ts["low"].rolling(CONTEXT_DURATION).min().shift(1).values
    df["local_high"] = ts["high"].rolling(LOCAL_DURATION).max().shift(1).values  # base immédiate ("accumulation"), plus proche que ctx_high

    ctx_span = (df["ctx_high"] - df["ctx_low"]).replace(0, np.nan)
    df["accum_retracement_frac"] = ((df["ctx_high"] - df["close"]) / ctx_span).values

    return df


def load_volume(symbol: str) -> pd.DataFrame:
    """Charge la colonne `volume` (présente dans les CSV bruts mais jamais
    exposée par `backtest_phase2.load_h1`, qui ne garde que OHLC) — cf. H9.
    Même DATA_DIR/format que `backtest_phase2.load_h1`, lecture seule."""
    from backtest_phase2 import DATA_DIR
    df = pd.read_csv(DATA_DIR / f"{symbol}_1h_processed.csv", usecols=["datetime", "volume"])
    df["date"] = pd.to_datetime(df["datetime"])
    return df.sort_values("date")[["date", "volume"]].reset_index(drop=True)


def resample_volume(vol_h1: pd.DataFrame, rule: str) -> pd.DataFrame:
    r = vol_h1.set_index("date").resample(rule).agg({"volume": "sum"}).dropna()
    return r.reset_index()


# ---------------------------------------------------------------------------
# Fonctions pures, testables unitairement (test_trend_table.py) : ne
# recalculent AUCUN indicateur, reçoivent des événements déjà résolus.
# ---------------------------------------------------------------------------
def add_leg(campaign: dict, add_frac: float, price: float) -> float:
    """Ajoute une jambe de taille `add_frac` (fraction du capital) au prix
    `price`, en respectant le plafond de risque de campagne (H3). Recalcule
    le prix d'entrée moyen pondéré (H2). Mute `campaign` en place. Retourne
    `actual_add` (la fraction RÉELLEMENT ajoutée, après plafonnement — à
    utiliser par l'appelant pour les frais : `fee_frac += actual_add`)."""
    if add_frac <= 0:
        return 0.0
    stop = campaign["stop"]
    ref_entry = campaign["entry"] if campaign["remaining"] > 0 else price
    if ref_entry <= 0:
        return 0.0
    stop_dist_pct = (ref_entry - stop) / ref_entry
    if stop_dist_pct <= 0:
        return 0.0
    max_total_remaining = MAX_CAMPAIGN_RISK_PCT / stop_dist_pct
    room = max_total_remaining - campaign["remaining"]
    actual_add = max(0.0, min(add_frac, room))
    if actual_add <= 1e-9:
        return 0.0
    new_remaining = campaign["remaining"] + actual_add
    campaign["entry"] = (campaign["entry"] * campaign["remaining"] + price * actual_add) / new_remaining
    campaign["remaining"] = new_remaining
    return actual_add


def free_room_frac(level: float, price: float) -> float:
    """Marge disponible (en fraction du prix) jusqu'à `level`, vu d'en dessous
    (H16). Un niveau DÉJÀ SOUS le prix n'est plus un obstacle : la marge de ce
    côté est non bornée (`+inf`). Un niveau INCONNU (NaN) rend la marge NaN --
    l'appelant doit le traiter comme un échec de vérification, pas comme un
    espace libre."""
    if price <= 0 or level != level:      # prix invalide, ou level NaN
        return float("nan")
    if level <= price:
        return float("inf")
    return (level - price) / price


def breakout_space_ok(price: float, expected_return_frac: float, obstacle_levels,
                       mult: float = BREAKOUT_SPACE_MULT) -> bool:
    """Contrainte "espace libre" MTF avant breakout (H13-H16), fonction PURE :
    le breakout dispose-t-il, sur CHACUN des niveaux supérieurs fournis, d'un
    espace libre d'au moins `mult` x son "rendement escompté" ?

    `price` : clôture de la bougie de cassure (même bougie que celle qui
    résout `breakout_raw`, cf. convention causale de `run_trend_table`).
    `expected_return_frac` : "rendement escompté" du breakout en fraction du
    prix = amplitude du range d'accumulation local / prix (H15).
    `obstacle_levels` : niveaux de prix ABSOLUS des structures majeures des UT
    supérieures ([UT+1, UT+2] en pratique, cf. H14) -- l'ordre et le nombre
    n'importent pas, la condition est un ET sur tous.

    Renvoie False si un niveau est inconnu (NaN) ou si le rendement escompté
    n'est pas exploitable (NaN/<=0) : *"il est impératif de VÉRIFIER l'absence
    d'obstacles"* ne peut pas être satisfait sans donnée (H16)."""
    if expected_return_frac != expected_return_frac or expected_return_frac <= 0:
        return False
    needed = mult * expected_return_frac
    for level in obstacle_levels:
        room = free_room_frac(level, price)
        if room != room:                 # NaN -> vérification impossible
            return False
        if room < needed:
            return False
    return True


def attach_obstacle_level(df_low: pd.DataFrame, df_high: pd.DataFrame,
                           closure_delay: pd.Timedelta = CLOSURE_DELAY) -> np.ndarray:
    """Pour chaque bougie de `df_low` (UT d'exécution), le `ctx_resistance`
    (borne HAUTE du canal Extreme Channel, H14) de la DERNIÈRE bougie de
    `df_high` ENTIÈREMENT CLÔTURÉE à cet instant -- aucun lookahead.

    Même jointure `merge_asof` et même `closure_delay` que
    `backtest_phase2_ut2.attach_context_level` ; une fonction distincte
    seulement parce que celle-ci joint `ctx_resistance` (borne haute, jamais
    produite par `prepare`, calculée par `add_trend_context` de CE fichier) et
    que `backtest_phase2_ut2.py` est un fichier partagé qu'on ne modifie pas.
    `df_high` doit donc déjà être passé par `prepare` PUIS
    `add_trend_context`."""
    high = df_high[["date", "ctx_resistance"]].copy()
    high["available_at"] = high["date"] + closure_delay
    high = high.sort_values("available_at")
    merged = pd.merge_asof(
        df_low[["date"]].sort_values("date"), high,
        left_on="date", right_on="available_at", direction="backward",
    )
    return merged["ctx_resistance"].values


def make_campaign(entry: float, stop: float) -> dict:
    return {"stage": "ACCUMULATION", "entry": entry, "stop": stop, "remaining": 0.0, "pnl_accum": 0.0}


def step_campaign(campaign: dict, i: int, o, high, low, c, ev: dict, profile: dict) -> tuple:
    """Fait progresser une campagne de tendance active d'un pas de temps `i`.
    Mute `campaign` en place. `ev` (déjà résolu par l'appelant, cf. principe
    ci-dessus) doit exposer les clés booléennes : `regime_excess`,
    `breakout_raw` (cassure locale + volume + score Framework, RULES_EXTRACTION
    §1), `divergence_raw` (retournement du cycle pendant que la structure
    reste haussière, H8), `excess_raw` (nouveau retour contexte + score,
    RULES_EXTRACTION §1) ; et si le profil prévoit "+Reverse", les niveaux
    `reverse_stop`/`reverse_target` à utiliser si la campagne se clôture ce
    pas-ci en Excès final. Le Pull-Back (path-dependent : dépend du plus haut
    et du creux propres à CETTE campagne) est calculé ICI, pas dans `ev`.

    Retourne (closed: bool, fee_frac: float, realized_pnl: float|None,
    reverse_request: dict|None). `reverse_request` n'est renseigné que si la
    campagne se clôture en Excès final ET que le profil prévoit +Reverse."""
    # 1) Stop de protection (Extreme Channel, H4) -- sur MÈCHE, priorité absolue
    if campaign["remaining"] > 0 and low[i] <= campaign["stop"]:
        pnl = (campaign["stop"] - campaign["entry"]) / campaign["entry"]
        campaign["pnl_accum"] += pnl * campaign["remaining"]
        fee_frac = campaign["remaining"]
        realized = campaign["pnl_accum"]
        campaign["remaining"] = 0.0
        return True, fee_frac, realized, None

    if campaign["stage"] != "ACCUMULATION":
        campaign["swing_high"] = max(campaign["swing_high"], high[i])

    if campaign["stage"] == "ACCUMULATION":
        if ev["regime_excess"]:
            # Abandon si le régime bascule en EXCES avant la cassure (règle
            # transverse "ne pas trader en excès", RULES_EXTRACTION §1).
            if campaign["remaining"] > 0:
                pnl = (c[i] - campaign["entry"]) / campaign["entry"]
                campaign["pnl_accum"] += pnl * campaign["remaining"]
                fee_frac = campaign["remaining"]
                realized = campaign["pnl_accum"]
                campaign["remaining"] = 0.0
                return True, fee_frac, realized, None
            return True, 0.0, None, None  # rien n'était engagé -- abandon silencieux, pas un "trade"
        # `ev.get(..., True)` : contrainte "espace libre" MTF (H13-H17).
        # Défaut True = ABSENCE de contrainte -> tout appelant qui ne fournit
        # pas la clé (dont `unified_protocol.py::_campaign_ev`, qui réplique
        # ce dict) garde un comportement BIT-À-BIT identique.
        if ev["breakout_raw"] and ev.get("breakout_space_ok", True):
            actual_add = add_leg(campaign, profile["breakout_frac"], o[i])
            campaign["stage"] = "POST_BREAKOUT"
            campaign["swing_high"] = high[i]
            return False, actual_add, None, None
        return False, 0.0, None, None

    if campaign["stage"] == "POST_BREAKOUT":
        if ev["divergence_raw"] and campaign["remaining"] > 0:
            close_amt = campaign["remaining"] * profile["div_close_frac"]
            fee_frac = 0.0
            if close_amt > 0:
                pnl = (c[i] - campaign["entry"]) / campaign["entry"]
                campaign["pnl_accum"] += pnl * close_amt
                fee_frac += close_amt
                campaign["remaining"] -= close_amt
            if profile["div_to_be"]:
                campaign["stop"] = max(campaign["stop"], campaign["entry"])
            campaign["stage"] = "PULLBACK_WATCH"
            campaign["pullback_ref_price"] = c[i]
            campaign["pullback_low_seen"] = False
            return False, fee_frac, None, None
        return False, 0.0, None, None

    if campaign["stage"] == "PULLBACK_WATCH":
        impulse = campaign["swing_high"] - campaign["entry"]
        if impulse > 0:
            campaign["pullback_ref_price"] = min(campaign["pullback_ref_price"], c[i])
            retracement_now = (campaign["swing_high"] - c[i]) / impulse
            if PULLBACK_RETRACEMENT_LOW <= retracement_now <= PULLBACK_RETRACEMENT_HIGH:
                campaign["pullback_low_seen"] = True
            recovery_span = campaign["swing_high"] - campaign["pullback_ref_price"]
            recovery_frac = ((c[i] - campaign["pullback_ref_price"]) / recovery_span) if recovery_span > 0 else 0.0
            if campaign["pullback_low_seen"] and recovery_frac >= PULLBACK_RECOVERY_FRAC:
                actual_add = add_leg(campaign, profile["pullback_frac"], o[i])
                campaign["stage"] = "EXCESS_WATCH"
                return False, actual_add, None, None
        return False, 0.0, None, None

    if campaign["stage"] == "EXCESS_WATCH":
        if ev["excess_raw"] and campaign["remaining"] > 0:
            pnl = (c[i] - campaign["entry"]) / campaign["entry"]
            campaign["pnl_accum"] += pnl * campaign["remaining"]
            fee_frac = campaign["remaining"]
            realized = campaign["pnl_accum"]
            campaign["remaining"] = 0.0
            reverse_request = None
            if profile["reverse"]:
                r_entry = c[i]
                r_stop = ev.get("reverse_stop", r_entry * 1.03)
                r_target = ev.get("reverse_target", r_entry * 0.97)
                r_stop_dist = (r_stop - r_entry) / r_entry
                r_frac = min(1.0, profile["risk_pct"] / r_stop_dist) if r_stop_dist > 0 else 0.0
                if r_frac > 0:
                    reverse_request = {"entry": r_entry, "stop": r_stop, "target": r_target, "frac": r_frac}
                    fee_frac += r_frac
            return True, fee_frac, realized, reverse_request
        return False, 0.0, None, None

    return False, 0.0, None, None


def try_open_campaign(i: int, o, ctx_support_prev: float, accumulation_active: bool, profile: dict) -> tuple:
    """Tente d'ouvrir une nouvelle campagne au pas `i` (entrée à l'open,
    convention constante du projet). `accumulation_active` est déjà résolu
    par l'appelant (régime TENDANCE + range mature + rejet canal +
    retracement 38-61%, cf. hypothèses H5/H6). Retourne (campaign: dict|None,
    fee_frac: float)."""
    if not accumulation_active:
        return None, 0.0
    entry_price = o[i]
    stop_price = min(ctx_support_prev, entry_price * 0.999)
    campaign = make_campaign(entry_price, stop_price)
    actual_add = add_leg(campaign, profile["accum_frac"], entry_price)
    return campaign, actual_add


def step_reverse(reverse_pos: dict, i: int, high, low, c) -> tuple:
    """Fait progresser la position "+Reverse" (short, H10) d'un pas de temps.
    Retourne (closed: bool, fee_frac: float, realized_pnl: float|None)."""
    if high[i] >= reverse_pos["stop"]:
        pnl = (reverse_pos["entry"] - reverse_pos["stop"]) / reverse_pos["entry"]
        return True, reverse_pos["frac"], pnl
    if c[i] <= reverse_pos["target"]:
        pnl = (reverse_pos["entry"] - c[i]) / reverse_pos["entry"]
        return True, reverse_pos["frac"], pnl
    return False, 0.0, None


# ---------------------------------------------------------------------------
# Moteur complet : calcule les indicateurs/événements sur données réelles,
# puis pilote step_campaign/step_reverse/try_open_campaign pas à pas.
# ---------------------------------------------------------------------------
def run_trend_table(df: pd.DataFrame, vol: pd.DataFrame, profile_name: str,
                     use_breakout_space_gate: bool = False,
                     df_ut1: pd.DataFrame = None, df_ut2: pd.DataFrame = None,
                     space_mult: float = BREAKOUT_SPACE_MULT) -> dict:
    """Rejoue la table de tendance à 5 étapes sur `df` (H4 ou toute UT unique,
    colonnes date/open/high/low/close), avec `vol` (DataFrame aligné, même
    longueur, colonne "volume" de la même UT — cf. `load_volume`/
    `resample_volume`).

    N'ouvre une campagne QUE si `regime` (calculé par `regime_classifier.
    add_regime`, réutilisé tel quel via `prepare`) vaut TENDANCE au moment de
    la détection Accumulation. Hors régime TENDANCE : aucune position ouverte
    (H11).

    `use_breakout_space_gate` (défaut `False`, préserve BIT-À-BIT le
    comportement historique de ce moteur — même convention que
    `use_mtf_stop`/`use_fib_gate` ailleurs) : active la contrainte "espace
    libre" MTF avant le Breakout (H13-H17). Exige alors `df_ut1` ET `df_ut2`,
    les OHLC BRUTS des deux unités de temps supérieures (typiquement
    `resample(h1, "1D")` et `resample(h1, "W")` pour une exécution H4) — ils
    sont passés par `prepare` + `add_trend_context` ici, puis joints sans
    lookahead par `attach_obstacle_level`. `space_mult` : multiplicateur du
    rendement escompté, 1.0 = Ratio 1:1 (la seule valeur citée par le corpus,
    H15) ; paramétrable pour la mesure de sensibilité uniquement."""
    p = PROFILES_TREND[profile_name]
    df = prepare(df)
    df = add_trend_context(df)
    n = len(df)
    assert len(vol) == n, "volume désaligné avec df (même resample requis)"

    obstacle_ut1 = obstacle_ut2 = None
    if use_breakout_space_gate:
        if df_ut1 is None or df_ut2 is None:
            raise ValueError(
                "use_breakout_space_gate=True exige df_ut1 (UT+1) et df_ut2 (UT+2) — "
                "la contrainte 'espace libre' porte explicitement sur les DEUX niveaux "
                "(TRADING_LESSONS_BREAKOUT_RATIO11.md l.17, cf. H13)")
        obstacle_ut1 = attach_obstacle_level(df, add_trend_context(prepare(df_ut1)))
        obstacle_ut2 = attach_obstacle_level(df, add_trend_context(prepare(df_ut2)))

    o, high, low, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    atr_v = df["atr"].values
    ctx_support_v = df["ctx_support"].values
    ctx_resistance_v = df["ctx_resistance"].values
    ctx_high_v = df["ctx_high"].values
    local_high_v = df["local_high"].values
    n_borders_v = df["n_borders"].values
    regime_v = df["regime"].values
    score_v = df["score"].values
    cycle_favorable_v = df["cycle_favorable"].values
    ema_trend_v = (df["close"].ewm(span=EMA_SLOW, adjust=False).mean()).values  # même filtre de fond que proxy_v2
    retr_v = df["accum_retracement_frac"].values
    # "Rendement escompté" du breakout = amplitude du range d'accumulation
    # local, déjà calculée par `prepare` (H15) et jusqu'ici jamais lue ici.
    local_range_v = df["local_range"].values

    vol_v = vol["volume"].values
    vol_ma = pd.Series(vol_v).rolling(VOLUME_MA_WINDOW).mean().values
    volume_expansion = vol_v > VOLUME_EXPANSION_MULT * np.roll(vol_ma, 1)
    volume_expansion[0] = False

    warmup = EMA_SLOW + 20
    fee = FEE

    def valid_inputs(i):
        return (
            not np.isnan(atr_v[i]) and not np.isnan(ctx_support_v[i]) and not np.isnan(ctx_resistance_v[i])
            and not np.isnan(ctx_high_v[i]) and not np.isnan(local_high_v[i])
            and not np.isnan(n_borders_v[i]) and not np.isnan(retr_v[i])
        )

    equity = 1.0
    equity_curve = np.empty(n)
    equity_curve[0] = equity
    campaign = None
    reverse_pos = None
    trades = []
    stage_time = {"ACCUMULATION": 0, "POST_BREAKOUT": 0, "PULLBACK_WATCH": 0, "EXCESS_WATCH": 0}

    for i in range(1, n):
        # ---- 0) Position "+Reverse" en cours (H10) ----
        if reverse_pos is not None:
            closed, fee_frac, pnl = step_reverse(reverse_pos, i, high, low, c)
            if closed:
                equity *= (1 + pnl * fee_frac)
                equity *= (1 - fee * fee_frac)
                trades.append(pnl)
                reverse_pos = None

        # ---- 1) Campagne de tendance en cours ----
        if campaign is not None:
            stage_time[campaign["stage"]] = stage_time.get(campaign["stage"], 0) + 1
            ev = {
                "regime_excess": regime_v[i - 1] == "EXCES",
                # Déclencheur évalué entièrement à la bougie i-1 (close,
                # volume, score déjà connus à sa clôture), exécuté à l'open de
                # la bougie i (o[i], dans try_open_campaign/add_leg) -- même
                # convention causale que v7 (long_signal_prev = score[i-1]).
                # CORRIGÉ pendant l'écriture : la 1re version comparait c[i] et
                # volume[i] (bougie PAS ENCORE connue au moment de l'entrée à
                # o[i]) -- lookahead, repéré à la relecture, corrigé avant tout
                # rejeu sur données réelles.
                "breakout_raw": (
                    valid_inputs(i - 1) and c[i - 1] > local_high_v[i - 1]
                    and volume_expansion[i - 1] and score_v[i - 1] >= 2
                ),
                "divergence_raw": (
                    i >= 2 and bool(cycle_favorable_v[i - 2]) and not bool(cycle_favorable_v[i - 1])
                    and c[i - 1] > ema_trend_v[i - 1]
                ),
                "excess_raw": valid_inputs(i - 1) and c[i] > ctx_high_v[i - 1] and score_v[i - 1] >= 2,
                "reverse_stop": max(ctx_resistance_v[i - 1], c[i] * 1.001) if valid_inputs(i - 1) else c[i] * 1.03,
                "reverse_target": ctx_support_v[i - 1] if valid_inputs(i - 1) else c[i] * 0.97,
            }
            if use_breakout_space_gate:
                # Évalué sur la MÊME bougie i-1 que `breakout_raw` ci-dessus
                # (clôture de la bougie de cassure et niveaux supérieurs
                # disponibles à cet instant) -- pas de lookahead ajouté.
                ev["breakout_space_ok"] = breakout_space_ok(
                    c[i - 1], local_range_v[i - 1] / c[i - 1] if c[i - 1] > 0 else float("nan"),
                    (obstacle_ut1[i - 1], obstacle_ut2[i - 1]), space_mult)
            closed, fee_frac, realized, reverse_request = step_campaign(campaign, i, o, high, low, c, ev, p)
            if fee_frac > 0:
                equity *= (1 - fee * fee_frac)
            if realized is not None:
                equity *= (1 + realized)
                trades.append(realized)
            if closed:
                if reverse_request is not None:
                    reverse_pos = reverse_request
                campaign = None

        # ---- 2) Tenter d'ouvrir une nouvelle campagne (Accumulation) ----
        # `reverse_pos is None` : on ne démarre pas un nouveau long tant que le
        # short "+Reverse" n'est pas dénoué -- cohérent avec la règle
        # transverse "jamais passer de tendance haussière à baissière sans
        # repasser par un range" (RULES_EXTRACTION §1).
        if campaign is None and reverse_pos is None and i > warmup and valid_inputs(i - 1):
            # Tout évalué sur la bougie i-1 (déjà entièrement connue),
            # entrée exécutée à l'open de i -- CORRIGÉ pendant l'écriture :
            # la 1re version comparait low[i]/c[i] (bougie pas encore connue
            # au moment de l'entrée à o[i]) -- même bug de lookahead que
            # breakout_raw ci-dessus, repéré et corrigé avant tout rejeu.
            mature = n_borders_v[i - 1] >= MIN_BORDERS
            channel_rejection = low[i - 1] <= ctx_support_v[i - 1] and c[i - 1] > ctx_support_v[i - 1]
            retracement_ok = ACCUM_RETRACEMENT_LOW <= retr_v[i - 1] <= ACCUM_RETRACEMENT_HIGH
            accumulation_active = regime_v[i - 1] == "TENDANCE" and mature and channel_rejection and retracement_ok
            new_campaign, fee_frac = try_open_campaign(i, o, ctx_support_v[i - 1], accumulation_active, p)
            if new_campaign is not None:
                campaign = new_campaign
                if fee_frac > 0:
                    equity *= (1 - fee * fee_frac)

        mtm = 0.0
        if campaign is not None and campaign["remaining"] > 0:
            mtm += (c[i] - campaign["entry"]) / campaign["entry"] * campaign["remaining"]
        if reverse_pos is not None:
            mtm += (reverse_pos["entry"] - c[i]) / reverse_pos["entry"] * reverse_pos["frac"]
        equity_curve[i] = equity * (1 + mtm)

    trades_arr = np.array(trades) if trades else np.array([])
    eq_series = pd.Series(equity_curve)
    max_dd = (eq_series / eq_series.cummax() - 1).min()
    return {
        "n_trades": len(trades_arr),
        "final_equity": equity,
        "max_dd_%": round(max_dd * 100, 1),
        "total_return_%": round((equity - 1) * 100, 1),
        "win_rate_%": round((trades_arr > 0).mean() * 100, 1) if len(trades_arr) else None,
        "profit_factor": round(trades_arr[trades_arr > 0].sum() / abs(trades_arr[trades_arr < 0].sum()), 2)
        if len(trades_arr) and (trades_arr < 0).any() else None,
        "avg_trade_%": round(trades_arr.mean() * 100, 3) if len(trades_arr) else None,
        "stage_time_%": {k: round(v / n * 100, 1) for k, v in stage_time.items()},
    }


# ---------------------------------------------------------------------------
# Diagnostic du POUVOIR DISCRIMINANT du gate "espace libre", indépendant de la
# performance
# ---------------------------------------------------------------------------
# Nécessaire pour une raison précise et déjà documentée : sur ce jeu de
# données, 100% des campagnes de tendance se referment à l'étape Accumulation
# et AUCUNE n'atteint jamais le Breakout (PLAN.md / COUVERTURE_ENSEIGNEMENTS.md
# / `unified_protocol.py` main()). Le chiffre de performance du gate est donc
# STRUCTURELLEMENT condamné à être un écart de 0,0 — ce qui ne dit rien de la
# règle elle-même. Ce diagnostic mesure séparément, sur TOUTES les bougies, si
# la condition mord ou si elle est INERTE — exactement la distinction que la
# sensibilité MIN_BORDERS avait dû faire au round précédent (0,0 pt d'écart
# mesuré, mais gate inerte, ce qui n'était PAS une preuve de robustesse).
def raw_breakout_candidates(df: pd.DataFrame, vol: pd.DataFrame) -> np.ndarray:
    """Réplique VECTORISÉE de l'expression `ev["breakout_raw"]` de
    `run_trend_table` (clôture > plus haut local + expansion de volume +
    score >= 2, tout évalué à la bougie i-1), pour TOUTES les bougies au lieu
    des seules bougies où une campagne est active. `df` doit déjà être passé
    par `prepare` + `add_trend_context`.

    Réplique donc vérifiée, pas supposée : `test_trend_table.py::
    test_raw_breakout_candidates_matches_engine_expression` compare cette
    version bougie par bougie à l'expression scalaire du moteur sur données
    réelles."""
    n = len(df)
    c = df["close"].values
    local_high_v = df["local_high"].values
    score_v = df["score"].values
    vol_v = vol["volume"].values
    vol_ma = pd.Series(vol_v).rolling(VOLUME_MA_WINDOW).mean().values
    volume_expansion = vol_v > VOLUME_EXPANSION_MULT * np.roll(vol_ma, 1)
    volume_expansion[0] = False
    prev = np.arange(-1, n - 1)
    cand = np.zeros(n, dtype=bool)
    ok = prev >= 0
    cand[ok] = (
        (c[prev[ok]] > local_high_v[prev[ok]])
        & volume_expansion[prev[ok]]
        & (score_v[prev[ok]] >= 2)
    )
    return cand


def breakout_space_binding_stats(df: pd.DataFrame, vol: pd.DataFrame,
                                  df_ut1: pd.DataFrame, df_ut2: pd.DataFrame,
                                  space_mult: float = BREAKOUT_SPACE_MULT) -> dict:
    """Sur combien des bougies candidates au breakout le gate "espace libre"
    passe-t-il / bloque-t-il, et pour quelle raison (obstacle UT+1, UT+2, ou
    donnée manquante) ? `df`/`df_ut1`/`df_ut2` : OHLC BRUTS (passés par
    `prepare` + `add_trend_context` ici)."""
    df = add_trend_context(prepare(df))
    obstacle_ut1 = attach_obstacle_level(df, add_trend_context(prepare(df_ut1)))
    obstacle_ut2 = attach_obstacle_level(df, add_trend_context(prepare(df_ut2)))
    cand = raw_breakout_candidates(df, vol)
    c = df["close"].values
    local_range_v = df["local_range"].values
    n = len(df)
    warmup = EMA_SLOW + 20

    n_cand = n_pass = n_block_ut1 = n_block_ut2 = n_block_nan = 0
    n_ut1_not_obstacle = n_ut2_not_obstacle = 0
    for i in range(1, n):
        if not cand[i] or i <= warmup:
            continue
        j = i - 1
        n_cand += 1
        price = c[j]
        exp_ret = local_range_v[j] / price if price > 0 else float("nan")
        r1 = free_room_frac(obstacle_ut1[j], price)
        r2 = free_room_frac(obstacle_ut2[j], price)
        if np.isinf(r1):
            n_ut1_not_obstacle += 1
        if np.isinf(r2):
            n_ut2_not_obstacle += 1
        if breakout_space_ok(price, exp_ret, (obstacle_ut1[j], obstacle_ut2[j]), space_mult):
            n_pass += 1
            continue
        if r1 != r1 or r2 != r2 or exp_ret != exp_ret:
            n_block_nan += 1
            continue
        needed = space_mult * exp_ret
        if r1 < needed:
            n_block_ut1 += 1
        if r2 < needed:
            n_block_ut2 += 1
    return {
        "space_mult": space_mult,
        "n_breakout_candidates": n_cand,
        "n_pass": n_pass,
        "pass_%": round(100 * n_pass / n_cand, 1) if n_cand else None,
        "n_blocked_by_ut1": n_block_ut1,
        "n_blocked_by_ut2": n_block_ut2,
        "n_blocked_missing_data": n_block_nan,
        "ut1_level_not_an_obstacle_%": round(100 * n_ut1_not_obstacle / n_cand, 1) if n_cand else None,
        "ut2_level_not_an_obstacle_%": round(100 * n_ut2_not_obstacle / n_cand, 1) if n_cand else None,
    }
