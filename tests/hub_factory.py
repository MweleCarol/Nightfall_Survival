"""Shared setup for the hub tests."""
from src.combat.attachments import load_attachment_defs
from src.player.equipment import Equipment, load_equipment_defs
from src.player.inventory import Inventory, load_item_defs
from src.player.player import Player
from src.systems.progression import Progression
from src.systems.skills import SkillSet, load_skill_defs
from src.ui.hub import HubContext
from tests.factories import make_weapon


def make_context() -> HubContext:
    items = load_item_defs()
    inventory = Inventory(20, items)
    player = Player((1000, 1000), weapon=make_weapon(), inventory=inventory)
    return HubContext(
        assets=None, item_defs=items, player=player, inventory=inventory,
        equipment=Equipment(load_equipment_defs(items)), skills=SkillSet(load_skill_defs()),
        progression=Progression(), base_capacity=lambda: 20,
        attachment_defs=load_attachment_defs(items))