from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Status:
    name: str
    type: str
    duration: float
    value: float = 0
    stat: str = ""
    tick_interval: float = 1.0
    tick_timer: float = 1.0
    source: str = ""
    control_type: str = ""
    confuse_chance: float = 0
    crit_dmg_pct: float = 0


@dataclass
class BattlePet:
    owner_id: str
    name: str
    species_name: str
    battle_type: str
    evolution_stage: int

    hp: float
    max_hp: float
    atk: float
    def_: float
    spd: float
    crit: float
    crit_dmg: float
    eva: float
    lifesteal: float

    attack_timer: float = 0
    attack_interval: float = 1.0

    skill_cds: list[float] = field(default_factory=list)
    skill_index: int = 0
    skills: list[dict] = field(default_factory=list)

    statuses: list[Status] = field(default_factory=list)
    silenced: bool = False
    disarmed: bool = False

    auto_skill_interval: float = 0
    auto_skill_timer: float = 0

    @property
    def is_dead(self) -> bool:
        return self.hp <= 0

    @property
    def attack_speed(self) -> float:
        return 1.0 / max(self.spd, 0.1)


@dataclass
class BattleEvent:
    time: float
    type: str
    source: str
    target: str
    detail: str = ""
    damage: float = 0
    is_crit: bool = False
    is_dodge: bool = False


@dataclass
class BattleResult:
    winner: Optional[str]
    winner_name: str = ""
    loser_name: str = ""
    events: list[BattleEvent] = field(default_factory=list)
    duration: float = 0
    pets: list[BattlePet] = field(default_factory=list)
