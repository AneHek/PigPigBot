"""
test_data_energy.py — EnergyMixin 单元测试。
"""
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

if 'redis' not in sys.modules:
    sys.modules['redis'] = MagicMock()

from test.test_data_manager import InMemoryRedis

from src.data.energy import EnergyMixin, ENERGY_MAX


class Energy(EnergyMixin):
    pass


class TestEnergy(unittest.TestCase):

    def setUp(self):
        InMemoryRedis.reset()
        self.energy = Energy()

    def test_get_energy_default_max(self):
        result = self.energy.get_energy("u1")
        self.assertEqual(result["value"], ENERGY_MAX)

    def test_use_energy_success(self):
        self.assertTrue(self.energy.use_energy("u1", 20))
        result = self.energy.get_energy("u1")
        self.assertEqual(result["value"], ENERGY_MAX - 20)

    def test_use_energy_insufficient(self):
        self.energy.use_energy("u1", 90)
        self.assertFalse(self.energy.use_energy("u1", 20))

    def test_add_energy(self):
        self.energy.use_energy("u1", 50)
        new_val = self.energy.add_energy("u1", 30)
        self.assertEqual(new_val, ENERGY_MAX - 50 + 30)

    def test_regen_after_time(self):
        self.energy.use_energy("u1", 60)
        energy = self.energy.get_energy("u1")
        self.assertEqual(energy["value"], ENERGY_MAX - 60)

        key = self.energy._energy_key("u1")
        old_update = float(InMemoryRedis._hashes[key]["last_update"])
        InMemoryRedis._hashes[key]["last_update"] = str(old_update - 600)

        energy = self.energy.get_energy("u1")
        self.assertEqual(energy["value"], ENERGY_MAX - 60 + 3)

    def test_regen_capped_at_max(self):
        self.energy.use_energy("u1", 5)
        key = self.energy._energy_key("u1")
        old_update = float(InMemoryRedis._hashes[key]["last_update"])
        InMemoryRedis._hashes[key]["last_update"] = str(old_update - 36000)

        energy = self.energy.get_energy("u1")
        self.assertEqual(energy["value"], ENERGY_MAX)


if __name__ == "__main__":
    unittest.main()
