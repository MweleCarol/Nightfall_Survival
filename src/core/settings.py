"""Central configuration constants. Change values here, not in the logic."""

TITLE = "Nightfall Survival: Last Stand"
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60
MAX_DT = 0.1  # clamp huge frame times so physics never explodes

# --- Colours (from the main menu design) ---
COLOR_BACKGROUND = (10, 12, 20)
COLOR_TEXT = (232, 238, 247)
COLOR_ACCENT = (224, 34, 27)
COLOR_MUTED = (127, 140, 163)
COLOR_AMBER = (245, 165, 36)

# --- World ---
WORLD_WIDTH = 3200
WORLD_HEIGHT = 2400

# --- Player ---
PLAYER_SIZE = 32
PLAYER_SPEED = 220.0            # pixels per second
PLAYER_SPRINT_MULTIPLIER = 1.6
PLAYER_MAX_HEALTH = 100
PLAYER_MAX_STAMINA = 100.0

# --- Stamina ---
STAMINA_DRAIN_PER_SEC = 25.0
STAMINA_REGEN_PER_SEC = 15.0
STAMINA_REGEN_DELAY = 1.0       # seconds after sprinting before regen starts
STAMINA_MIN_TO_SPRINT = 10.0    # needed to START a sprint (prevents flicker)

# --- Camera ---
CAMERA_SMOOTHING = 8.0          # higher = snappier