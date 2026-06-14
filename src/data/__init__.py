from src.data.models import Pet, _redis_client
from src.data.pet_store import PetStoreMixin
from src.data.economy import EconomyMixin
from src.data.energy import EnergyMixin
from src.data.dungeon_store import DungeonMixin
from src.data.boss_store import BossMixin
from src.data.social import SocialMixin
from src.data.checkin import CheckinMixin
from src.data.leaderboard import LeaderboardMixin
from src.data.group import GroupMixin
from src.data.passive_store import PassiveMixin


class DataManager(PetStoreMixin, EconomyMixin, EnergyMixin,
                  DungeonMixin, BossMixin, SocialMixin,
                  CheckinMixin, LeaderboardMixin, GroupMixin,
                  PassiveMixin):

    def __init__(self):
        self._connected = False
        try:
            _redis_client.ping()
            self._connected = True
        except Exception:
            pass


data_manager = DataManager()
