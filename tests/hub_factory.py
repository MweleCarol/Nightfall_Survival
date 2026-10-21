"""Shared setup for the hub tests."""
import random

from src.combat.attachments import load_attachment_defs
from src.core import settings
from src.player.equipment import Equipment, load_equipment_defs
from src.player.inventory import Inventory, load_item_defs
from src.player.player import Player
from src.systems.crafting import CraftingSystem, load_crafting_data
from src.systems.mission_system import MissionManager, load_missions
from src.systems.progression import Progression
from src.systems.skills import SkillSet, load_skill_defs
from src.systems.story import StoryState, load_story_data
from src.ui.hub import HubContext
from src.world.map import GameMap
from src.world.story_world import load_story_world
from tests.factories import make_weapon


def make_context() -> HubContext:
    items = load_item_defs()
    inventory = Inventory(20, items)
    player = Player((1000, 1000), weapon=make_weapon(), inventory=inventory)
    ctx = HubContext(
        assets=None, item_defs=items, player=player, inventory=inventory,
        equipment=Equipment(load_equipment_defs(items)), skills=SkillSet(load_skill_defs()),
        progression=Progression(), base_capacity=lambda: 20,
        attachment_defs=load_attachment_defs(items),
        crafting=CraftingSystem(load_crafting_data(items), inventory, random.Random(1)),
        missions=MissionManager(load_missions(items)), story=StoryState(load_story_data()),
        game_map=GameMap.load(settings.DEFAULT_MAP), locations=load_story_world(items).locations)

    def set_tracked(mission_id: str) -> None:
        ctx.tracked_id = mission_id

    ctx.set_tracked = set_tracked
    return ctx