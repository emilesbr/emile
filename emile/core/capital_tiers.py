"""
Sizing par palier de capital — RULES_EXTRACTION.md §5 ("Gestion du risque
globale (règles dures)"), phrase exacte reprise ici pour traçabilité :

    "Paliers de capital : <10 000€ (agressivité quasi obligatoire pour
    dépasser un SMIC), 10 000-100 000€ (arbitrage risque/sécurité),
    >100 000€ (agressivité maximale déconseillée par précaution)"

et, dans le même §5 :

    "Perte spéculative jamais >5% du capital, quel que soit le profil"

CE QUE LA SOURCE DIT RÉELLEMENT (pas plus, pas moins)
------------------------------------------------------
Le manuel ne donne AUCUN chiffre de `risk_pct` par palier, AUCUNE limite de
nombre de positions simultanées par palier, et n'impose AUCUNE règle de
diversification liée spécifiquement à la taille du capital (la
"diversification 1%+1%" du corpus #16 est un sujet distinct, non lié à un
palier de capital précis — cf. `COUVERTURE_ENSEIGNEMENTS.md` / item 7 du
backlog `PLAN.md`, laissé hors de ce module). La règle de palier est une
recommandation qualitative sur le degré d'agressivité *souhaitable* selon
la taille absolue du capital, pas une formule.

HYPOTHÈSE D'IMPLÉMENTATION (explicite, pas une déduction silencieuse)
----------------------------------------------------------------------
Pour transformer cette recommandation qualitative en un sizing testable,
sans modifier le choix de profil de risque fait par l'utilisateur (FAIBLE/
MODERE/AGRESSIF/TRES_AGRESSIF, cf. PROFILES_V4 de `backtest_phase2_v7.py`),
on module le `risk_pct` du profil choisi par un facteur dépendant du palier :

  - PALIER 1 (<10 000€)      : multiplicateur 1.25 — "agressivité quasi
    obligatoire" est traduit par une autorisation de sizing légèrement PLUS
    agressif que la table de base, plafonnée par la règle dure des 5%.
  - PALIER 2 (10 000-100 000€) : multiplicateur 1.0 — "arbitrage
    risque/sécurité" est traduit par AUCUNE modulation : la table de base
    (choix du profil par l'utilisateur) est déjà cet arbitrage, on ne
    surcharge pas.
  - PALIER 3 (>=100 000€)    : plafond dur de risk_pct à 2%, quel que soit
    le profil choisi — "agressivité maximale déconseillée par précaution"
    est traduit par un plafond qui neutralise concrètement AGRESSIF (3%) et
    TRES_AGRESSIF (5%) pour les gros capitaux, sans changer FAIBLE/MODERE
    (déjà <=2%).

Les valeurs numériques (1.25, plafond 2%) sont un choix d'implémentation
raisonnable mais ARBITRAIRE, pas une valeur donnée par le manuel — à
signaler explicitement si un jour comparé à un vrai retour d'expérience de
l'éditeur. Ce qui n'est PAS une hypothèse (c'est écrit noir sur blanc dans
la source) : la direction (plus agressif toléré en bas de l'échelle, plafond
de précaution en haut) et le plafond dur absolu de 5% qui s'applique à tous
les paliers et profils sans exception.

Nombre de tranches simultanées (`MAX_TRANCHES`) : **non modulé par palier**
dans ce module — la source ne relie jamais explicitement le nombre de
positions simultanées à la taille du capital. Le laisser inchangé (valeur du
moteur v7, 3) est documenté ici comme un choix de scope, pas un oubli.

Conversion €→$ : ce projet ne dispose d'AUCUN module de conversion de
devises (les données sont cotées en USDT, cf. `code/backtest_phase2.py`).
Faute de convention existante, ce module applique une parité 1:1 (1€ = 1$),
documentée ici comme hypothèse simplificatrice explicite — PAS une opinion
sur le taux de change réel. `EUR_TO_USD_RATE` est le seul point à modifier
si une vraie conversion devient nécessaire.
"""
from dataclasses import dataclass

# --- Frontières de palier (bornes exactes documentées comme hypothèse :
# le manuel écrit "<10 000€", "10 000-100 000€", ">100 000€" sans préciser
# à quel palier appartiennent exactement 10 000€ et 100 000€ eux-mêmes.
# Convention retenue ici : le palier 2 est un intervalle FERMÉ à gauche
# ([10k, 100k[), donc 10 000€ pile appartient au palier 2, et 100 000€ pile
# appartient au palier 3 (>=100k, cohérent avec ">100 000€" lu au sens
# large "à partir de 100k on applique la prudence maximale").
TIER_1_MAX_EUR = 10_000.0   # < ce seuil -> PALIER_1
TIER_2_MAX_EUR = 100_000.0  # < ce seuil (et >= TIER_1_MAX_EUR) -> PALIER_2 ; >= -> PALIER_3

PALIER_1 = "PALIER_1_MOINS_10K"
PALIER_2 = "PALIER_2_10K_100K"
PALIER_3 = "PALIER_3_PLUS_100K"

# Hypothèse d'implémentation (cf. docstring module) — pas une valeur du manuel.
TIER_RISK_MULTIPLIER = {
    PALIER_1: 1.25,
    PALIER_2: 1.00,
    PALIER_3: 1.00,   # la contrainte du palier 3 passe par un PLAFOND, pas un multiplicateur
}
TIER_RISK_PCT_CAP = {
    PALIER_1: None,
    PALIER_2: None,
    PALIER_3: 0.02,   # "agressivité maximale déconseillée par précaution"
}

# Règle dure §5, s'applique à TOUS les paliers/profils sans exception :
# "Perte spéculative jamais >5% du capital, quel que soit le profil"
HARD_MAX_RISK_PCT = 0.05

# Cf. docstring module : aucune convention de conversion €→$ n'existe ailleurs
# dans ce projet ; parité 1:1 retenue comme hypothèse simplificatrice explicite.
EUR_TO_USD_RATE = 1.0

def capital_tier(capital_eur: float) -> str:
    """Retourne le palier (PALIER_1/2/3) pour un capital de départ en euros.

    Frontières (cf. docstring module pour la justification du choix) :
      capital_eur < 10 000                      -> PALIER_1
      10 000 <= capital_eur < 100 000            -> PALIER_2
      capital_eur >= 100 000                     -> PALIER_3
    """
    if capital_eur < 0:
        raise ValueError(f"capital_eur doit être positif, reçu {capital_eur}")
    if capital_eur < TIER_1_MAX_EUR:
        return PALIER_1
    if capital_eur < TIER_2_MAX_EUR:
        return PALIER_2
    return PALIER_3

@dataclass(frozen=True)
class EffectiveSizing:
    capital_eur: float
    capital_usd: float
    tier: str
    profile_name: str
    base_risk_pct: float
    risk_pct: float          # risk_pct effectif après modulation + plafonds
    max_tranches: int        # non modulé par palier (cf. docstring module)

def effective_sizing(capital_eur: float, profile_name: str, profiles: dict, max_tranches: int) -> EffectiveSizing:
    """Calcule le sizing effectif (risk_pct modulé) pour un capital de départ
    absolu (en €) et un profil de risque donné.

    `profiles` : dict au format PROFILES_V4 de `backtest_phase2_v7.py`
    (clé -> {"risk_pct": float, ...}). `max_tranches` : nombre de tranches
    simultanées du moteur appelant, transmis tel quel (non modulé ici, cf.
    docstring module).
    """
    if profile_name not in profiles:
        raise KeyError(f"Profil inconnu : {profile_name!r} (attendu un de {sorted(profiles)})")

    tier = capital_tier(capital_eur)
    base_risk_pct = profiles[profile_name]["risk_pct"]

    risk_pct = base_risk_pct * TIER_RISK_MULTIPLIER[tier]
    cap = TIER_RISK_PCT_CAP[tier]
    if cap is not None:
        risk_pct = min(risk_pct, cap)
    risk_pct = min(risk_pct, HARD_MAX_RISK_PCT)

    return EffectiveSizing(
        capital_eur=capital_eur,
        capital_usd=capital_eur * EUR_TO_USD_RATE,
        tier=tier,
        profile_name=profile_name,
        base_risk_pct=base_risk_pct,
        risk_pct=risk_pct,
        max_tranches=max_tranches,
    )

if __name__ == "__main__":
    # Petit aperçu manuel (pas un test -- voir test_capital_tiers.py pour les
    # vérifications automatisées) des 4 profils x 3 montants représentatifs.
    demo_profiles = {
        "FAIBLE": {"risk_pct": 0.01}, "MODERE": {"risk_pct": 0.02},
        "AGRESSIF": {"risk_pct": 0.03}, "TRES_AGRESSIF": {"risk_pct": 0.05},
    }
    for capital in (5_000, 50_000, 500_000):
        for profile in demo_profiles:
            s = effective_sizing(capital, profile, demo_profiles, max_tranches=3)
            print(f"{capital:>8}€ {profile:<14} palier={s.tier:<22} "
                  f"risk_pct base={s.base_risk_pct:.3f} -> effectif={s.risk_pct:.3f}")
