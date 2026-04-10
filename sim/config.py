"""
Simulation constants.

Attribute scale: 1–20
  1–5   very poor
  6–9   below average
  10–11 average
  12–14 good
  15–17 very good
  18–20 elite
"""

# ---------------------------------------------------------------------------
# Squad composition
# ---------------------------------------------------------------------------

POSITIONS = {
    "LW": {"count": 4},
    "C":  {"count": 4},
    "RW": {"count": 4},
    "LD": {"count": 3},
    "RD": {"count": 3},
    "G":  {"count": 2},
}

# ---------------------------------------------------------------------------
# Attribute ranges (min, max) per position
# Used by the generator — actual values drawn from a bell-ish distribution
# within this window, then shifted by quality_bias.
# ---------------------------------------------------------------------------

SKATER_ATTRS = ["skating", "shooting", "passing", "physicality", "defence", "stamina"]
GOALIE_ATTRS = ["positioning", "reflexes", "rebound_control", "stamina"]

ATTR_RANGES = {
    # LW / RW: finishers — elite shooting and skating are realistic;
    #          defence is secondary and can be genuinely poor.
    "LW": {
        "skating":     (4, 20),   # ★ key — elite speedsters exist
        "shooting":    (5, 20),   # ★ key — elite snipers exist
        "passing":     (3, 14),   # supporting; rarely elite
        "physicality": (2, 15),   # wide spread — grinders vs skill players
        "defence":     (2,  9),   # low ceiling; offensive forwards often poor
        "stamina":     (4, 17),
    },
    "RW": {
        "skating":     (4, 20),   # ★ key
        "shooting":    (5, 20),   # ★ key
        "passing":     (3, 14),
        "physicality": (2, 15),
        "defence":     (2,  9),
        "stamina":     (4, 17),
    },
    # C: playmakers and two-way players — passing is the elite ceiling;
    #    shooting is good but capped lower than wings.
    "C": {
        "skating":     (4, 18),   # ★ key — need mobility for all zones
        "shooting":    (3, 15),   # decent but not primary
        "passing":     (5, 20),   # ★ key — elite playmakers exist
        "physicality": (2, 13),
        "defence":     (4, 16),   # two-way centres can be genuinely good
        "stamina":     (5, 18),   # centres skate most — higher stamina floor
    },
    # LD / RD: shutdown defenders — elite defence and physicality;
    #          shooting is a bonus and can be very poor.
    "LD": {
        "skating":     (3, 16),   # mobility matters but not elite
        "shooting":    (2,  9),   # low ceiling — shot rarely a primary weapon
        "passing":     (2, 13),   # some puck-moving defencemen exist
        "physicality": (5, 20),   # ★ key — elite hitters exist
        "defence":     (6, 20),   # ★ key — elite shutdown defenders exist
        "stamina":     (4, 17),
    },
    "RD": {
        "skating":     (3, 16),
        "shooting":    (2,  9),
        "passing":     (2, 13),
        "physicality": (5, 20),   # ★ key
        "defence":     (6, 20),   # ★ key
        "stamina":     (4, 17),
    },
    # G: elite goalies can be elite in both key stats;
    #    rebound control is the differentiator at the top end.
    "G": {
        "positioning":     (3, 20),   # ★ key — elite positioning separates great from good
        "reflexes":        (3, 20),   # ★ key — elite reflexes exist
        "rebound_control": (2, 17),   # differentiator; genuinely poor at the low end
        "stamina":         (4, 18),
    },
}

# ---------------------------------------------------------------------------
# Match engine constants
# ---------------------------------------------------------------------------

# Ice time distribution — line 1 dominates; line 4 is a short-shift line
LINE_WEIGHTS     = [0.35, 0.28, 0.22, 0.15]   # must match POSITIONS["LW"]["count"]
PAIRING_WEIGHTS  = [0.42, 0.35, 0.23]          # must match POSITIONS["LD"]["count"]

EVENTS_PER_PERIOD = 30      # "shift events" resolved per period
OT_EVENTS         = 10      # shorter OT period (sudden death)

# Baseline probabilities — tuned so an average vs average game
# produces ~24 shots and ~5 combined goals over 60 minutes.
SHOT_BASE_PROB = 0.55       # chance of a shot attempt per attacking event
GOAL_BASE_RATE = 0.09       # conversion rate at equal attack vs defence

# How much each rating point of difference shifts probabilities
SHOT_DIFF_FACTOR = 0.015    # per rating point: attack_score - defence_score
GOAL_DIFF_FACTOR = 0.008    # per rating point: attack_score - goalie_score

# Powerplay modifiers
PP_SHOT_BONUS = 0.10
PP_GOAL_BONUS = 0.04
PP_EVENTS     = 3           # PP lasts this many events (approx 2 mins)

# Penalty probability per event (when no PP active)
PENALTY_PROB = 0.055

# Home ice advantage (small shot probability bonus for home team)
HOME_ADVANTAGE = 0.03

# Fatigue — applied in period 3; avg_stamina of 10 = no change
FATIGUE_BASE    = 0.93
FATIGUE_STAMINA = 0.01      # per point above/below avg stamina of 10

# ---------------------------------------------------------------------------
# Penalty infraction types
# ---------------------------------------------------------------------------

INFRACTIONS = [
    "Hooking",
    "Tripping",
    "Roughing",
    "Interference",
    "Slashing",
    "High-Sticking",
    "Holding",
    "Boarding",
    "Cross-Checking",
    "Charging",
]
