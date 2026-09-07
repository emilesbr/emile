"""
Tests unitaires de `capital_tiers.py` — vérifie (1) que la bonne frontière de
palier est appliquée aux montants limites (9 999€/10 000€/10 001€, puis
99 999€/100 000€/100 001€), et (2) que le sizing résultant est cohérent avec
la règle extraite et ses hypothèses documentées dans `capital_tiers.py` :
  - Palier 1 (<10k€)      : risk_pct MAJORÉ (x1.25) par rapport à la base
  - Palier 2 (10k-100k€)  : risk_pct INCHANGÉ par rapport à la base
  - Palier 3 (>=100k€)    : risk_pct PLAFONNÉ à 2%, jamais au-dessus
  - Règle dure §5 : risk_pct effectif JAMAIS >5%, quel que soit palier/profil
  - MAX_TRANCHES transmis tel quel (non modulé par palier, cf. docstring)

Aucune donnée réelle utilisée. Exécution : `python3 test_capital_tiers.py`.
Affiche PASS/FAIL par test et sort avec un code non-nul si un test échoue.
"""
from capital_tiers import (
    capital_tier, effective_sizing,
    PALIER_1, PALIER_2, PALIER_3,
    HARD_MAX_RISK_PCT, TIER_1_MAX_EUR, TIER_2_MAX_EUR,
)

PROFILES = {
    "FAIBLE": {"risk_pct": 0.01},
    "MODERE": {"risk_pct": 0.02},
    "AGRESSIF": {"risk_pct": 0.03},
    "TRES_AGRESSIF": {"risk_pct": 0.05},
}

_failures = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not condition else ""))
    if not condition:
        _failures.append(name)


# ---------------------------------------------------------------------------
# 1) Frontières exactes du palier 1/2 (9999/10000/10001)
# ---------------------------------------------------------------------------
def test_frontiere_palier_1_2():
    check("9999€ -> PALIER_1", capital_tier(9_999) == PALIER_1, capital_tier(9_999))
    check("10000€ -> PALIER_2 (borne incluse dans palier 2)", capital_tier(10_000) == PALIER_2, capital_tier(10_000))
    check("10001€ -> PALIER_2", capital_tier(10_001) == PALIER_2, capital_tier(10_001))
    check("constante TIER_1_MAX_EUR == 10000", TIER_1_MAX_EUR == 10_000.0)


# ---------------------------------------------------------------------------
# 2) Frontières exactes du palier 2/3 (99999/100000/100001)
# ---------------------------------------------------------------------------
def test_frontiere_palier_2_3():
    check("99999€ -> PALIER_2", capital_tier(99_999) == PALIER_2, capital_tier(99_999))
    check("100000€ -> PALIER_3 (borne incluse dans palier 3)", capital_tier(100_000) == PALIER_3, capital_tier(100_000))
    check("100001€ -> PALIER_3", capital_tier(100_001) == PALIER_3, capital_tier(100_001))
    check("constante TIER_2_MAX_EUR == 100000", TIER_2_MAX_EUR == 100_000.0)


# ---------------------------------------------------------------------------
# 3) Cas limites additionnels : 0€, montant tout juste sous chaque frontière
# ---------------------------------------------------------------------------
def test_cas_limites_additionnels():
    check("0€ -> PALIER_1 (pas de capital = palier le plus bas)", capital_tier(0) == PALIER_1)
    check("9999.99€ -> PALIER_1", capital_tier(9_999.99) == PALIER_1)
    check("99999.99€ -> PALIER_2", capital_tier(99_999.99) == PALIER_2)
    try:
        capital_tier(-1)
        check("capital négatif lève ValueError", False, "aucune exception levée")
    except ValueError:
        check("capital négatif lève ValueError", True)


# ---------------------------------------------------------------------------
# 4) Palier 1 : risk_pct majoré (x1.25) par rapport à la base, pour les 4 profils
# ---------------------------------------------------------------------------
def test_palier_1_majore_risk_pct():
    for profile, cfg in PROFILES.items():
        s = effective_sizing(5_000, profile, PROFILES, max_tranches=3)
        base = cfg["risk_pct"]
        attendu = min(base * 1.25, HARD_MAX_RISK_PCT)
        check(
            f"palier1/{profile} risk_pct effectif == min(base*1.25, {HARD_MAX_RISK_PCT})",
            abs(s.risk_pct - attendu) < 1e-9,
            f"base={base} effectif={s.risk_pct} attendu={attendu}",
        )
        check(f"palier1/{profile} risk_pct effectif >= base (jamais réduit sous le seuil bas)", s.risk_pct >= base - 1e-12)


# ---------------------------------------------------------------------------
# 5) Palier 2 : risk_pct strictement inchangé par rapport à la base
# ---------------------------------------------------------------------------
def test_palier_2_inchange():
    for profile, cfg in PROFILES.items():
        s = effective_sizing(50_000, profile, PROFILES, max_tranches=3)
        check(
            f"palier2/{profile} risk_pct effectif == base (aucune modulation)",
            abs(s.risk_pct - cfg["risk_pct"]) < 1e-9,
            f"base={cfg['risk_pct']} effectif={s.risk_pct}",
        )


# ---------------------------------------------------------------------------
# 6) Palier 3 : risk_pct plafonné à 2%, jamais au-dessus, même pour TRES_AGRESSIF
# ---------------------------------------------------------------------------
def test_palier_3_plafonne():
    s_faible = effective_sizing(500_000, "FAIBLE", PROFILES, max_tranches=3)
    s_modere = effective_sizing(500_000, "MODERE", PROFILES, max_tranches=3)
    s_agressif = effective_sizing(500_000, "AGRESSIF", PROFILES, max_tranches=3)
    s_tres = effective_sizing(500_000, "TRES_AGRESSIF", PROFILES, max_tranches=3)

    check("palier3/FAIBLE (1%) inchangé, sous le plafond", abs(s_faible.risk_pct - 0.01) < 1e-9, s_faible.risk_pct)
    check("palier3/MODERE (2%) inchangé, au plafond", abs(s_modere.risk_pct - 0.02) < 1e-9, s_modere.risk_pct)
    check("palier3/AGRESSIF (3% base) plafonné à 2%", abs(s_agressif.risk_pct - 0.02) < 1e-9, s_agressif.risk_pct)
    check("palier3/TRES_AGRESSIF (5% base) plafonné à 2%", abs(s_tres.risk_pct - 0.02) < 1e-9, s_tres.risk_pct)
    check("palier3 : aucun profil ne dépasse 2%", all(
        s.risk_pct <= 0.02 + 1e-9 for s in (s_faible, s_modere, s_agressif, s_tres)
    ))


# ---------------------------------------------------------------------------
# 7) Règle dure §5 : jamais >5%, quel que soit palier/profil (contrôle croisé
#    exhaustif, pas seulement les cas déjà couverts ci-dessus)
# ---------------------------------------------------------------------------
def test_jamais_plus_de_5_pct():
    montants = [0, 1, 9_999, 10_000, 50_000, 99_999, 100_000, 500_000, 10_000_000]
    violations = []
    for capital in montants:
        for profile in PROFILES:
            s = effective_sizing(capital, profile, PROFILES, max_tranches=3)
            if s.risk_pct > HARD_MAX_RISK_PCT + 1e-9:
                violations.append((capital, profile, s.risk_pct))
    check("aucune combinaison capital x profil ne dépasse 5%", not violations, violations)


# ---------------------------------------------------------------------------
# 8) MAX_TRANCHES transmis tel quel (non modulé par palier)
# ---------------------------------------------------------------------------
def test_max_tranches_non_module():
    for capital in (5_000, 50_000, 500_000):
        s = effective_sizing(capital, "MODERE", PROFILES, max_tranches=3)
        check(f"max_tranches transmis inchangé (capital={capital})", s.max_tranches == 3, s.max_tranches)


# ---------------------------------------------------------------------------
# 9) Conversion €→$ : parité 1:1 documentée (hypothèse explicite du module)
# ---------------------------------------------------------------------------
def test_conversion_eur_usd_parite():
    s = effective_sizing(12_345, "MODERE", PROFILES, max_tranches=3)
    check("capital_usd == capital_eur (parité 1:1, hypothèse documentée)", abs(s.capital_usd - 12_345) < 1e-9)


# ---------------------------------------------------------------------------
# 10) Profil inconnu -> erreur explicite, pas un plantage silencieux
# ---------------------------------------------------------------------------
def test_profil_inconnu_leve_erreur():
    try:
        effective_sizing(5_000, "INEXISTANT", PROFILES, max_tranches=3)
        check("profil inconnu lève KeyError", False, "aucune exception levée")
    except KeyError:
        check("profil inconnu lève KeyError", True)


def main():
    tests = [
        test_frontiere_palier_1_2,
        test_frontiere_palier_2_3,
        test_cas_limites_additionnels,
        test_palier_1_majore_risk_pct,
        test_palier_2_inchange,
        test_palier_3_plafonne,
        test_jamais_plus_de_5_pct,
        test_max_tranches_non_module,
        test_conversion_eur_usd_parite,
        test_profil_inconnu_leve_erreur,
    ]
    for t in tests:
        t()
    print()
    if _failures:
        print(f"{len(_failures)} test(s) en échec : {_failures}")
        raise SystemExit(1)
    print(f"Tous les tests passent ({len(tests)} fonctions de test).")


if __name__ == "__main__":
    main()
