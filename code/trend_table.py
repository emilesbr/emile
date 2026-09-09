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
H12. **Une seule campagne active à la fois** ("un seul tracker actif",
    principe du projet appliqué ici aussi à l'échelle d'une position) : pas
    de pyramidalisation de PLUSIEURS campagnes de tendance en parallèle,
    contrairement à v4-v7 (`MAX_TRANCHES=3` sur des ENTRÉES indépendantes).
    Ici, une seule campagne (avec ses propres jambes internes) peut être
    active ; une nouvelle campagne ne peut démarrer qu'une fois la
    précédente entièrement close (et le "+Reverse" éventuel dénoué, règle
    transverse "jamais passer de haussier à baissier sans repasser par un
    range").

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

# --- Constantes de détection des étapes (cf. hypothèses H5-H9 ci-dessus) ---
ACCUM_RETRACEMENT_LOW, ACCUM_RETRACEMENT_HIGH = 0.38, 0.61        # RULES_EXTRACTION §1
PULLBACK_RETRACEMENT_LOW, PULLBACK_RETRACEMENT_HIGH = 0.23, 0.38  # RULES_EXTRACTION §1
PULLBACK_RECOVERY_FRAC = 0.50                                     # H7
VOLUME_MA_WINDOW = 20
VOLUME_EXPANSION_MULT = 1.5                                       # H9
MAX_CAMPAIGN_RISK_PCT = 0.05                                      # H3, RULES_EXTRACTION §5

# --- Table de money management "trade de tendance" (RULES_EXTRACTION §4) ---
# accum_frac / breakout_frac / pullback_frac : fractions de l'unité U ajoutées
# à chaque étape (H1). div_close_frac / div_to_be : action à la Divergence.
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
        if ev["breakout_raw"]:
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
def run_trend_table(df: pd.DataFrame, vol: pd.DataFrame, profile_name: str) -> dict:
    """Rejoue la table de tendance à 5 étapes sur `df` (H4 ou toute UT unique,
    colonnes date/open/high/low/close), avec `vol` (DataFrame aligné, même
    longueur, colonne "volume" de la même UT — cf. `load_volume`/
    `resample_volume`).

    N'ouvre une campagne QUE si `regime` (calculé par `regime_classifier.
    add_regime`, réutilisé tel quel via `prepare`) vaut TENDANCE au moment de
    la détection Accumulation. Hors régime TENDANCE : aucune position ouverte
    (H11)."""
    p = PROFILES_TREND[profile_name]
    df = prepare(df)
    df = add_trend_context(df)
    n = len(df)
    assert len(vol) == n, "volume désaligné avec df (même resample requis)"

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
