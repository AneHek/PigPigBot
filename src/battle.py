"""
battle.py — Real-time auto-battle engine.

Based on battle.md design document.
"""
from __future__ import annotations

import copy
import random
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from src.pet_config import PET_SPECIES, Skill, SkillEffect

# ── Constants ──

DT = 0.1          # tick interval in seconds
MAX_DURATION = 60  # max battle duration in seconds
TYPE_ADVANTAGE = 1.15   # 15% bonus for type advantage
TYPE_DISADVANTAGE = 0.90  # 10% penalty for disadvantage

# Type advantage matrix
COUNTER_MAP = {
    "attack": "defense",
    "defense": "speed",
    "speed": "attack",
}

# Control priority (higher = overrides lower)
CONTROL_PRIORITY = {
    "stun": 100, "freeze": 100, "ice": 100,
    "imprison": 80, "float": 80,
    "fear": 60,
    "silence": 40,
    "disarm": 20,
    "taunt": 10, "confuse": 10,
}


# ── Battle Dataclasses ──

@dataclass
class Status:
    """A temporary status effect on a pet."""
    name: str
    type: str               # dot, debuff, control, buff, hot, shield, reflect
    duration: float         # remaining seconds
    value: float = 0        # damage per tick / percentage / shield amount
    stat: str = ""          # affected stat (for debuff/buff)
    tick_interval: float = 1.0
    tick_timer: float = 1.0
    source: str = ""        # owner pet ID
    control_type: str = ""  # for control effects
    confuse_chance: float = 0
    crit_dmg_pct: float = 0


@dataclass
class BattlePet:
    """In-battle pet state (snapshot of Pet)."""
    owner_id: str
    name: str
    species_name: str
    battle_type: str
    evolution_stage: int

    # Current stats
    hp: float
    max_hp: float
    atk: float
    def_: float
    spd: float
    crit: float
    crit_dmg: float
    eva: float
    lifesteal: float

    # Timers
    attack_timer: float = 0
    attack_interval: float = 1.0

    # Skills
    skill_cds: list[float] = field(default_factory=list)
    skill_index: int = 0
    skills: list[dict] = field(default_factory=list)

    # Status
    statuses: list[Status] = field(default_factory=list)
    silenced: bool = False
    disarmed: bool = False

    # Auto-skill flag
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
    """A single event in the battle timeline."""
    time: float
    type: str               # attack, skill, dot, heal, shield, dodge, crit, death, buff, debuff, control
    source: str             # pet name
    target: str             # target pet name
    detail: str = ""        # description
    damage: float = 0
    is_crit: bool = False
    is_dodge: bool = False


@dataclass
class BattleResult:
    """Result of a completed battle."""
    winner: Optional[str]   # owner_id of winner
    winner_name: str = ""
    loser_name: str = ""
    events: list[BattleEvent] = field(default_factory=list)
    duration: float = 0
    pets: list[BattlePet] = field(default_factory=list)


def _group(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


# ══════════════════════════════════════════════════════════════════════
# Battle Engine
# ══════════════════════════════════════════════════════════════════════

class BattleEngine:
    """Core battle engine."""

    def run(self, pet_a_dict: dict, pet_b_dict: dict) -> BattleResult:
        """Run a battle between two pets. Returns BattleResult."""
        a = self._create_battle_pet(pet_a_dict)
        b = self._create_battle_pet(pet_b_dict)
        events: list[BattleEvent] = []
        elapsed = 0.0

        # Type advantage check
        a_adv = self._type_advantage(a.battle_type, b.battle_type)

        while elapsed < MAX_DURATION:
            # ── Control check ──
            a_controlled = self._is_controlled(a)
            b_controlled = self._is_controlled(b)
            a_silenced = self._has_control_type(a, "silence")
            a_disarmed = self._has_control_type(a, "disarm")
            b_silenced = self._has_control_type(b, "silence")
            b_disarmed = self._has_control_type(b, "disarm")

            # ── Status ticks ──
            self._tick_statuses(a, b, DT, events, elapsed)
            self._tick_statuses(b, a, DT, events, elapsed)
            self._decay_statuses(a, DT)
            self._decay_statuses(b, DT)

            # ── Pet A actions ──
            actions_a = self._process_pet(a, b, DT, a_controlled, a_silenced,
                                          a_disarmed, events, elapsed, a_adv)
            # ── Pet B actions ──
            actions_b = self._process_pet(b, a, DT, b_controlled, b_silenced,
                                          b_disarmed, events, elapsed, 1.0)

            # ── Death check ──
            if a.is_dead or b.is_dead:
                break

            elapsed += DT

        # Determine winner
        winner_id = None
        winner_name = ""
        loser_name = ""
        if a.is_dead and not b.is_dead:
            winner_id = b.owner_id
            winner_name = b.name
            loser_name = a.name
        elif b.is_dead and not a.is_dead:
            winner_id = a.owner_id
            winner_name = a.name
            loser_name = b.name
        # If both dead or timeout: draw, no winner

        return BattleResult(
            winner=winner_id,
            winner_name=winner_name,
            loser_name=loser_name,
            events=events,
            duration=round(elapsed, 1),
            pets=[a, b],
        )

    # ── Battle pet creation ──

    def _create_battle_pet(self, pet_dict: dict) -> BattlePet:
        species_id = pet_dict.get("species_id", "")
        species_info = PET_SPECIES.get(species_id, {})
        stage = pet_dict.get("evolution_stage", 0)

        # Skills: 1 for stage 0, 2 for stage 1, 3 for stage 2
        all_skills = species_info.get("skills", [])  # list[Skill] per stage
        available_skills = []
        if stage < len(all_skills):
            # stages[0] = skill0, stages[1] = skill1, stages[2] = skill2
            # Available = all skills up to and including current stage
            s = all_skills[stage]
            if isinstance(s, Skill):
                # Each skills entry is one Skill for that stage
                available_skills = [all_skills[i] for i in range(stage + 1)
                                    if i < len(all_skills) and isinstance(all_skills[i], Skill)]
            elif isinstance(s, dict):
                for key in ["skill1", "skill2", "skill3"]:
                    if key in s:
                        available_skills.append(s[key])

        # Skill CD timers
        skill_cds = [0.0] * len(available_skills)

        bp = BattlePet(
            owner_id=pet_dict.get("owner_id", ""),
            name=pet_dict.get("name", "未命名"),
            species_name=species_info.get("names", ["??", "??", "??"])[stage] if stage < 3 else "??",
            battle_type=pet_dict.get("battle_type", ""),
            evolution_stage=stage,
            hp=pet_dict.get("hp", 500),
            max_hp=pet_dict.get("hp", 500),
            atk=pet_dict.get("atk", 50),
            def_=pet_dict.get("def_", 0),
            spd=pet_dict.get("spd", 1.0),
            crit=pet_dict.get("crit", 5),
            crit_dmg=pet_dict.get("crit_dmg", 1.5),
            eva=pet_dict.get("eva", 5),
            lifesteal=pet_dict.get("lifesteal", 0.05),
            attack_interval=1.0 / max(pet_dict.get("spd", 1.0), 0.1),
            skill_cds=skill_cds,
            skills=available_skills,
        )
        return bp

    # ── Type advantage ──

    def _type_advantage(self, atk_type: str, def_type: str) -> float:
        if COUNTER_MAP.get(atk_type) == def_type:
            return TYPE_ADVANTAGE
        if COUNTER_MAP.get(def_type) == atk_type:
            return TYPE_DISADVANTAGE
        return 1.0

    # ── Process one pet's actions for a tick ──

    def _process_pet(self, pet: BattlePet, enemy: BattlePet, dt: float,
                     controlled: bool, silenced: bool, disarmed: bool,
                     events: list[BattleEvent], elapsed: float,
                     type_mult: float) -> bool:
        """Process one pet's timers and actions. Returns True if any action executed."""
        acted = False

        # Auto-skill (P010 stage 3 mechanics)
        if pet.auto_skill_interval > 0:
            pet.auto_skill_timer += dt
            while pet.auto_skill_timer >= pet.auto_skill_interval:
                pet.auto_skill_timer -= pet.auto_skill_interval
                if not controlled:
                    self._execute_skill(pet, enemy, 0, events, elapsed, type_mult)
                    acted = True

        # Skill CD timers
        for i in range(len(pet.skill_cds)):
            if pet.skill_cds[i] > 0:
                pet.skill_cds[i] = max(0, pet.skill_cds[i] - dt)

        # Skill rotation (only if not silenced and not controlled)
        if not controlled and not silenced and len(pet.skills) > 0:
            skill = pet.skills[pet.skill_index]
            if pet.skill_cds[pet.skill_index] <= 0:
                self._execute_skill(pet, enemy, pet.skill_index, events, elapsed, type_mult)
                pet.skill_cds[pet.skill_index] = skill.cd
                pet.skill_index = (pet.skill_index + 1) % len(pet.skills)
                # Skill after-swing: reset attack_timer to 50% of interval
                pet.attack_timer = pet.attack_interval * 0.5
                acted = True

        # Auto-attack (only if not controlled and not disarmed)
        if not controlled and not disarmed:
            pet.attack_timer += dt
            while pet.attack_timer >= pet.attack_interval:
                pet.attack_timer -= pet.attack_interval
                self._execute_attack(pet, enemy, events, elapsed, type_mult)
                acted = True

        return acted

    # ── Damage pipeline ──

    def _calc_damage(self, attacker: BattlePet, defender: BattlePet,
                     base_damage: float, type_mult: float,
                     is_true_damage: bool = False) -> tuple[float, bool, bool]:
        """9-step damage pipeline. Returns (damage, is_crit, is_dodge)."""
        damage = base_damage

        # Step 2: Type advantage (skip for true damage)
        if not is_true_damage:
            damage *= type_mult

        # Step 3: Crit check
        is_crit = False
        always_crit = self._get_buff(defender, "crit_guaranteed") is not None
        if always_crit or random.random() * 100 < attacker.crit:
            is_crit = True
            damage *= attacker.crit_dmg

        # Step 4: Dodge check
        is_dodge = False
        effective_eva = defender.eva
        blind_debuff = self._get_debuff(attacker, "hit_rate")
        if blind_debuff:
            effective_eva += blind_debuff.value
        if random.random() * 100 < effective_eva:
            is_dodge = True
            return 0, is_crit, is_dodge

        # Step 5: Shield absorb
        if not is_true_damage:
            shield = self._get_buff(defender, "shield")
            if shield:
                absorbed = min(damage, shield.value)
                damage -= absorbed
                shield.value -= absorbed
                if shield.value <= 0:
                    defender.statuses.remove(shield)

        # Step 6: Defense reduction (skip for true damage)
        if not is_true_damage:
            def_val = defender.def_
            def_debuff = self._get_debuff(defender, "def")
            if def_debuff:
                def_val *= (1 - def_debuff.value / 100)
            damage *= (1 - def_val / (def_val + 1000))

        return max(damage, 0), is_crit, is_dodge

    # ── Execute attack ──

    def _execute_attack(self, attacker: BattlePet, defender: BattlePet,
                        events: list[BattleEvent], elapsed: float,
                        type_mult: float):
        base_dmg = attacker.atk
        dmg, is_crit, is_dodge = self._calc_damage(
            attacker, defender, base_dmg, type_mult)

        detail = ""
        if is_dodge:
            detail = f"{defender.name} 闪避了攻击！"
            events.append(BattleEvent(elapsed, "dodge", attacker.name,
                                     defender.name, detail, 0))
            return

        if is_crit:
            detail = "暴击！"

        defender.hp -= dmg
        events.append(BattleEvent(elapsed, "attack", attacker.name,
                                  defender.name, detail, dmg, is_crit))

        # Step 7: Reflect
        reflect_buff = self._get_buff(defender, "reflect")
        if reflect_buff and dmg > 0:
            reflect_dmg_val = dmg * (reflect_buff.value / 100)
            attacker.hp -= reflect_dmg_val
            events.append(BattleEvent(elapsed, "reflect", defender.name,
                                     attacker.name,
                                     f"反弹 {reflect_dmg_val:.0f} 伤害",
                                     reflect_dmg_val))

        # Step 8: Lifesteal
        if attacker.lifesteal > 0 and dmg > 0:
            heal_amount = dmg * attacker.lifesteal
            attacker.hp = min(attacker.max_hp, attacker.hp + heal_amount)

    # ── Execute skill ──

    def _execute_skill(self, pet: BattlePet, enemy: BattlePet,
                       skill_idx: int, events: list[BattleEvent],
                       elapsed: float, type_mult: float):
        skill: Skill = pet.skills[skill_idx]
        events.append(BattleEvent(elapsed, "skill", pet.name, enemy.name,
                                 f"释放【{skill.name}】"))

        for effect in skill.effects:
            self._resolve_effect(pet, enemy, effect, events, elapsed, type_mult)

    # ── Resolve skill effect ──

    def _resolve_effect(self, source: BattlePet, target: BattlePet,
                        effect: SkillEffect, events: list[BattleEvent],
                        elapsed: float, type_mult: float):
        etype = effect.type

        if etype == "damage":
            if effect.min_val > 0 and effect.max_val > effect.min_val:
                dmg_val = random.uniform(effect.min_val, effect.max_val)
            else:
                dmg_val = effect.value
            for _ in range(effect.hit_count):
                dmg, is_crit, is_dodge = self._calc_damage(
                    source, target, dmg_val, type_mult)
                if is_dodge:
                    events.append(BattleEvent(elapsed, "dodge", source.name,
                                             target.name, "闪避了技能伤害！"))
                else:
                    target.hp -= dmg
                    events.append(BattleEvent(elapsed, "damage", source.name,
                                             target.name, f"伤害 {dmg:.0f}", dmg,
                                             is_crit=is_crit))
                    # Reflect
                    refl = self._get_buff(target, "reflect")
                    if refl and dmg > 0:
                        ref_dmg = dmg * (refl.value / 100)
                        source.hp -= ref_dmg

        elif etype == "true_damage":
            dmg, _, is_dodge = self._calc_damage(source, target, effect.value, 1.0, True)
            if not is_dodge:
                target.hp -= effect.value
                events.append(BattleEvent(elapsed, "damage", source.name,
                                         target.name, f"真实伤害 {effect.value:.0f}",
                                         effect.value))

        elif etype == "dot":
            s = Status("dot_" + effect.stat, "dot", effect.duration,
                      effect.damage_per_tick, tick_interval=effect.tick_interval,
                      source=source.owner_id)
            target.statuses.append(s)

        elif etype == "hot":
            s = Status("hot", "hot", effect.duration, effect.damage_per_tick,
                      source=source.owner_id)
            source.statuses.append(s)

        elif etype == "heal":
            source.hp = min(source.max_hp, source.hp + effect.value)
            events.append(BattleEvent(elapsed, "heal", source.name, source.name,
                                     f"回复 {effect.value:.0f} HP"))

        elif etype == "debuff":
            if effect.stat == "magic_resist":
                dur = effect.duration
            else:
                dur = effect.duration
            s = Status(f"debuff_{effect.stat}", "debuff", dur, effect.stat_pct,
                      stat=effect.stat, source=source.owner_id)
            # Remove existing same-type debuff
            self._remove_status(target, s.type, s.stat)
            target.statuses.append(s)
            events.append(BattleEvent(elapsed, "debuff", source.name, target.name,
                                     f"{effect.stat} -{effect.stat_pct}%"))

        elif etype == "buff":
            self._remove_status(source, "buff", effect.stat)
            s = Status(f"buff_{effect.stat}", "buff", effect.duration, effect.stat_pct,
                      stat=effect.stat, source=source.owner_id)
            source.statuses.append(s)
            events.append(BattleEvent(elapsed, "buff", source.name, source.name,
                                     f"{effect.stat} +{effect.stat_pct}%"))

        elif etype == "control":
            ctype = effect.control_type
            if ctype == "confuse":
                s = Status("confuse", "control", effect.duration,
                          control_type="confuse", confuse_chance=effect.confuse_chance,
                          source=source.owner_id)
            elif ctype == "blind":
                s = Status("blind", "debuff", effect.duration, 20,
                          stat="hit_rate", source=source.owner_id)
            else:
                s = Status(f"control_{ctype}", "control", effect.duration,
                          control_type=ctype, source=source.owner_id)
            self._remove_status(target, "control", ctype)
            target.statuses.append(s)
            events.append(BattleEvent(elapsed, "control", source.name, target.name,
                                     f"施加 {ctype}"))

        elif etype == "shield":
            shield_amount = source.max_hp * (effect.value_pct / 100)
            self._remove_status(source, "shield")
            s = Status("shield", "shield", effect.duration, shield_amount,
                      source=source.owner_id)
            source.statuses.append(s)
            events.append(BattleEvent(elapsed, "shield", source.name, source.name,
                                     f"护盾 {shield_amount:.0f}"))

        elif etype == "reflect":
            self._remove_status(source, "reflect")
            s = Status("reflect", "reflect", effect.duration, effect.value_pct,
                      source=source.owner_id)
            source.statuses.append(s)
            events.append(BattleEvent(elapsed, "buff", source.name, source.name,
                                     f"反伤 {effect.value_pct}%"))

        elif etype == "crit_guaranteed":
            s = Status("crit_next", "crit_guaranteed", 5, effect.crit_dmg_pct,
                      source=source.owner_id)
            source.statuses.append(s)
            events.append(BattleEvent(elapsed, "buff", source.name, source.name,
                                     "下击必暴"))

        elif etype == "purify":
            removed = [s for s in source.statuses
                      if s.type in ("dot", "debuff", "control")]
            for s in removed:
                source.statuses.remove(s)
            events.append(BattleEvent(elapsed, "purify", source.name, source.name,
                                     f"净化了 {len(removed)} 个负面状态"))

        elif etype == "interrupt":
            # Interrupt: set enemy's current skill CD to max (wait again)
            if len(enemy.skill_cds) > 0:
                skill = enemy.skills[enemy.skill_index]
                # Force current skill to wait full CD
                enemy.skill_cds[enemy.skill_index] = skill.cd
            events.append(BattleEvent(elapsed, "control", source.name, target.name,
                                     "打断技能"))

        elif etype == "damage_share":
            # Damage share buff (P012 stage2)
            self._remove_status(source, "damage_share")
            s = Status("damage_share", "damage_share", effect.duration,
                      effect.value_pct, source=source.owner_id)
            source.statuses.append(s)

        elif etype == "auto_skill":
            source.auto_skill_interval = effect.auto_interval
            source.auto_skill_timer = 0
            events.append(BattleEvent(elapsed, "buff", source.name, source.name,
                                     f"自动技能 每{effect.auto_interval}秒"))

    # ── Status tick processing ──

    def _tick_statuses(self, pet: BattlePet, enemy: BattlePet, dt: float,
                       events: list[BattleEvent], elapsed: float):
        for s in pet.statuses[:]:
            if s.type == "dot":
                s.tick_timer -= dt
                while s.tick_timer <= 0:
                    s.tick_timer += s.tick_interval
                    pet.hp -= s.value
                    events.append(BattleEvent(elapsed, "dot", "DOT", pet.name,
                                             f"持续伤害 {s.value:.0f}", s.value))
                    # Reflect DoT
                    refl = self._get_buff(pet, "reflect")
                    if refl:
                        ref = s.value * (refl.value / 100)
                        # Reflect goes to source, but we need enemy ref
                        pass  # simplified: reflect only on direct attacks

            elif s.type == "hot":
                s.tick_timer -= dt
                while s.tick_timer <= 0:
                    s.tick_timer += s.tick_interval
                    pet.hp = min(pet.max_hp, pet.hp + s.value)

    def _decay_statuses(self, pet: BattlePet, dt: float):
        for s in pet.statuses[:]:
            s.duration -= dt
            if s.duration <= 0:
                # Remove auto-skill flag
                if s.type == "auto_skill" and hasattr(pet, 'auto_skill_interval'):
                    pet.auto_skill_interval = 0
                pet.statuses.remove(s)

    # ── Control helpers ──

    def _is_controlled(self, pet: BattlePet) -> bool:
        """Check if pet is fully disabled (cannot act at all)."""
        for s in pet.statuses:
            if s.type == "control" and s.control_type in ("stun", "freeze", "ice",
                                                           "imprison", "float", "fear"):
                return True
        return False

    def _has_control_type(self, pet: BattlePet, ctype: str) -> bool:
        for s in pet.statuses:
            if s.type == "control" and s.control_type == ctype:
                return True
        return False

    # ── Buff/debuff getters ──

    def _get_buff(self, pet: BattlePet, buff_type: str) -> Optional[Status]:
        for s in pet.statuses:
            if s.type == "buff" and s.stat == buff_type:
                return s
            if s.type == "shield" and buff_type == "shield":
                return s
            if s.type == "reflect" and buff_type == "reflect":
                return s
            if s.type == "crit_guaranteed" and buff_type == "crit_guaranteed":
                return s
        return None

    def _get_debuff(self, pet: BattlePet, debuff_stat: str) -> Optional[Status]:
        for s in pet.statuses:
            if s.type == "debuff" and s.stat == debuff_stat:
                return s
        return None

    def _remove_status(self, pet: BattlePet, stype: str, stat: str = ""):
        for s in pet.statuses[:]:
            if s.type == stype and (not stat or s.stat == stat):
                pet.statuses.remove(s)


# ══════════════════════════════════════════════════════════════════════
# Battle Report Formatting
# ══════════════════════════════════════════════════════════════════════

def format_battle_report(result: BattleResult) -> str:
    """Generate a readable battle report."""
    lines = ["⚔️ 战斗结束！"]
    lines.append("━━━━━━━━━━━━━━━━━━")

    if result.winner:
        lines.append(f"🏆 胜利者：{result.winner_name}")
        lines.append(f"💀 战败者：{result.loser_name}")
    else:
        lines.append("🤝 平局！双方势均力敌")

    lines.append(f"⏱ 战斗时长：{result.duration} 秒")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("📜 战斗日志：")

    # Show last 10 events
    recent = result.events[-10:] if len(result.events) > 10 else result.events
    for ev in recent:
        t = f"[{ev.time:.1f}s]"
        if ev.type in ("attack", "damage"):
            c = "💥" if ev.is_crit else "⚔️"
            lines.append(f"  {t} {c} {ev.source} → {ev.target} {ev.detail} (-{ev.damage:.0f})")
        elif ev.type == "skill":
            lines.append(f"  {t} ✨ {ev.source} {ev.detail}")
        elif ev.type == "dodge":
            lines.append(f"  {t} 👻 {ev.detail}")
        elif ev.type == "heal":
            lines.append(f"  {t} 💚 {ev.source} {ev.detail}")
        elif ev.type == "shield":
            lines.append(f"  {t} 🛡️ {ev.source} {ev.detail}")
        elif ev.type == "buff":
            lines.append(f"  {t} ⬆️ {ev.source} {ev.detail}")
        elif ev.type == "debuff":
            lines.append(f"  {t} ⬇️ {ev.source} → {ev.target} {ev.detail}")
        elif ev.type == "control":
            lines.append(f"  {t} 🔒 {ev.source} → {ev.target} {ev.detail}")
        elif ev.type == "dot":
            lines.append(f"  {t} 🔥 {ev.detail} → {ev.target}")
        elif ev.type == "reflect":
            lines.append(f"  {t} 🔄 {ev.source} → {ev.target} {ev.detail}")
        elif ev.type == "purify":
            lines.append(f"  {t} 💫 {ev.source} {ev.detail}")

    return "\n".join(lines)


# Global engine instance
battle_engine = BattleEngine()
