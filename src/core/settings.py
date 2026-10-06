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
COLOR_NIGHT = (120, 160, 230)
COLOR_SAFE = (90, 200, 160)

# --- World ---
WORLD_WIDTH = 3200
WORLD_HEIGHT = 2400
DEFAULT_MAP = "data/maps/city_district_01.json"

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

# --- Day / night (real seconds per phase; short for testing) ---
DAY_DURATION = 120.0
NIGHT_DURATION = 90.0
DAY_START_HOUR = 8              # in-game clock: day runs 08:00 -> 20:00
NIGHT_START_HOUR = 20
DUSK_START = 0.75               # fraction of the day when it starts getting dark
DAWN_START = 0.85               # fraction of the night when it starts getting light

# --- Lighting ---
NIGHT_MAX_DARKNESS = 215        # 0-255 overlay opacity at full night
NIGHT_TINT = (6, 9, 22)
PLAYER_LIGHT_RADIUS = 280
STREET_LIGHT_RADIUS = 240


# --- Combat ---
WEAPONS_FILE = "data/weapons.json"
ENEMIES_FILE = "data/enemies.json"
PLAYER_START_WEAPON = "pistol_01"
PLAYER_START_RESERVE_AMMO = 48
PLAYER_HURT_FLASH = 0.2         # seconds the player flashes red when hit
TRACER_LIFETIME = 0.08          # seconds a bullet trail stays visible
MUZZLE_OFFSET = 22              # pixels from player centre to the gun tip
GAME_OVER_DELAY = 1.5           # seconds between death and the game-over screen

# --- Enemy AI ---
ENEMY_LOSE_INTEREST_FACTOR = 1.5   # chase until the player is this x detection range away
ENEMY_ATTACK_HYSTERESIS = 1.2      # stop attacking only when this x attack range away
ENEMY_CORPSE_TIME = 0.8            # seconds before a dead enemy disappears
ENEMY_ARRIVE_DISTANCE = 8.0        # "reached the spot" distance for SEARCH