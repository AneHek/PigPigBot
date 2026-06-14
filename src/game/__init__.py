from src.game.base import PetGameBase
from src.game.adopt import AdoptMixin
from src.game.stats_cmd import StatsMixin
from src.game.manage import ManageMixin
from src.game.evolve import EvolveMixin
from src.game.training import TrainingMixin
from src.game.pvp import PvPMixin
from src.game.leaderboard import LeaderboardMixin
from src.game.help_cmd import HelpMixin
from src.game.economy import EconomyMixin
from src.game.interact import InteractMixin
from src.game.dungeon import DungeonMixin
from src.game.boss import BossMixin
from src.game.title import TitleMixin
from src.game.event import EventMixin
from src.game.passive import PassiveMixin
from src.data import data_manager


class PetGame(PetGameBase, AdoptMixin, StatsMixin, ManageMixin,
              EvolveMixin, TrainingMixin, PvPMixin,
              LeaderboardMixin, HelpMixin, EconomyMixin,
              InteractMixin, DungeonMixin, BossMixin,
              TitleMixin, EventMixin, PassiveMixin):
    pass


game = PetGame(data_manager)
