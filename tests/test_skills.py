import pytest

from src.services.data_loader import DataLoadError
from src.systems.progression import Progression
from src.systems.skills import CATEGORIES, KNOWN_STATS, SkillDef, SkillSet, load_skill_defs


def make_defs() -> dict[str, SkillDef]:
    return {
        "vitality": SkillDef(id="vitality", name="Vitality", category="survivor",
                             stat="max_health", per_rank=10, max_rank=5, description="+10 HP"),
        "precision": SkillDef(id="precision", name="Precision", category="combat",
                              stat="crit_chance", per_rank=0.03, max_rank=2, description="+3%"),
    }


def test_shipped_skills_load_and_use_known_names():
    defs = load_skill_defs()
    assert len(defs) >= 9
    for skill in defs.values():
        assert skill.stat in KNOWN_STATS and skill.category in CATEGORIES


def test_bonus_is_rank_times_per_rank():
    skills = SkillSet(make_defs(), {"vitality": 3})
    assert skills.bonus("max_health") == 30
    assert skills.bonus("crit_chance") == 0


def test_purchase_spends_a_point_and_adds_a_rank():
    skills, progression = SkillSet(make_defs()), Progression(skill_points=2)
    assert skills.purchase("vitality", progression) is True
    assert skills.rank("vitality") == 1 and progression.skill_points == 1


def test_purchase_needs_a_skill_point():
    skills, progression = SkillSet(make_defs()), Progression(skill_points=0)
    assert skills.purchase("vitality", progression) is False
    assert skills.rank("vitality") == 0


def test_maxed_skill_cannot_be_bought_and_keeps_the_point():
    skills, progression = SkillSet(make_defs()), Progression(skill_points=5)
    skills.purchase("precision", progression)
    skills.purchase("precision", progression)
    assert skills.is_maxed("precision")
    assert skills.purchase("precision", progression) is False
    assert progression.skill_points == 3


def test_unknown_skill_is_rejected():
    assert SkillSet(make_defs()).purchase("flying", Progression(skill_points=1)) is False


def test_deserialize_clamps_ranks_and_ignores_unknown_skills():
    skills = SkillSet.deserialize({"vitality": 99, "ghost": 3, "precision": -1}, make_defs())
    assert skills.serialize() == {"vitality": 5}


def test_unknown_stat_is_rejected():
    data = {"id": "x", "name": "X", "category": "combat", "stat": "fly",
            "per_rank": 1, "max_rank": 1, "description": "d"}
    with pytest.raises(DataLoadError, match="stat"):
        SkillDef.from_dict(data, "test")