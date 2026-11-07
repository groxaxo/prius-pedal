import itertools
import unittest

from opendbc.can import CANPacker
from opendbc.car.structs import CarParams
from opendbc.car.toyota import toyotacan
from opendbc.car.toyota.values import ToyotaSafetyFlags
from opendbc.safety.tests import test_toyota
from opendbc.safety.tests.libsafety import libsafety_py


class TestToyotaPriusPedalSafety(test_toyota.TestToyotaSafetyTorque):
  DBC = 'toyota_prius_pedal_pt_generated'
  EPS_SCALE = 66
  TX_MSGS = test_toyota.TOYOTA_COMMON_TX_MSGS + test_toyota.TOYOTA_COMMON_LONG_TX_MSGS + [[0x200, 0]]

  @property
  def SAFETY_PARAM(self):
    return self.EPS_SCALE | ToyotaSafetyFlags.PRIUS_PEDAL

  def setUp(self):
    super().setUp()
    self.sensor_counter = 0
    self.assertTrue(self._rx(self._sensor()))
    self.assertTrue(self._rx(self._sdsu()))

  def _sensor(self, gas=805, state=0, counter=None):
    if counter is None:
      self.sensor_counter = (self.sensor_counter + 1) & 0xF
      counter = self.sensor_counter
    return self.packer.make_can_msg_safety('GAS_SENSOR', 0, {
      'INTERCEPTOR_GAS': gas, 'INTERCEPTOR_GAS2': gas, 'STATE': state, 'COUNTER_PEDAL': counter,
    })

  def test_live_four_byte_sdsu_is_valid(self):
    self.safety.set_safety_hooks(self.SAFETY_MODEL, self.SAFETY_PARAM | ToyotaSafetyFlags.PRIUS_PEDAL_SDSU_4)
    self.safety.init_tests()
    self.assertTrue(self._rx(self._sensor()))
    self.assertTrue(self._rx(libsafety_py.make_CANPacket(0x2FF, 0, bytes.fromhex('00000005'))))
    self.safety.set_controls_allowed(True)
    self.assertTrue(self._tx(self._pedal(True)))

  def _sdsu(self, state=0):
    return self.packer.make_can_msg_safety('SDSU', 0, {'STATE': state})

  def _pedal(self, active, counter=0):
    addr, data, bus = toyotacan.create_prius_pedal_command(self.packer, active, counter)
    return libsafety_py.make_CANPacket(addr, bus, data)

  def _user_gas_msg(self, gas):
    return self._sensor(806 if gas else 805)

  def test_only_fixed_standstill_assist(self):
    for allowed, moving, brake, gas in itertools.product((False, True), repeat=4):
      self.assertTrue(self._rx(self._speed_msg(1 if moving else 0)))
      self.assertTrue(self._rx(self._user_brake_msg(brake)))
      self.assertTrue(self._rx(self._user_gas_msg(gas)))
      self.safety.set_controls_allowed(allowed)
      self.assertEqual(self._tx(self._pedal(True)), allowed and not moving and not brake and not gas)
      self.assertTrue(self._tx(self._pedal(False)))

  def test_pedal_command_checksum_reserved_bits_and_tracks(self):
    self.safety.set_controls_allowed(True)
    for offset in range(6):
      msg = self._pedal(True)
      msg[0].data[offset] ^= 1
      self.assertFalse(self._tx(msg))
    # Recompute CRC after corrupting each command field: CRC alone is not a limit.
    addr, data, bus = toyotacan.create_prius_pedal_command(self.packer, True, 0)
    for offset, value in ((0, 0), (1, 0x9B), (2, 0), (3, 0x75), (4, 0x90), (4, 0)):
      mutated = bytearray(data)
      mutated[offset] = value
      mutated[-1] = toyotacan.pedal_checksum(mutated[:-1])
      self.assertFalse(self._tx(libsafety_py.make_CANPacket(addr, bus, bytes(mutated))))
    for counter in range(32):
      self.assertTrue(self._tx(self._pedal(True, counter)))

  def test_fresh_pedal_and_sdsu_required_for_actuation(self):
    self._reset_safety_hooks()
    self.safety.set_controls_allowed(True)
    self.assertFalse(self._tx(self._pedal(True)))
    self.assertFalse(self._tx(self._accel_msg(1)))
    self.assertTrue(self._tx(self._accel_msg(0)))
    self.assertTrue(self._rx(self._sensor()))
    self.assertFalse(self._tx(self._pedal(True)))
    self.assertTrue(self._rx(self._sdsu()))
    self.safety.set_controls_allowed(True)
    self.assertTrue(self._tx(self._pedal(True)))
    self.assertTrue(self._tx(self._accel_msg(1)))
    self.safety.set_timer(250001)
    self.assertFalse(self._tx(self._pedal(True)))
    self.assertFalse(self._tx(self._accel_msg(1)))
    self.assertTrue(self._tx(self._pedal(False)))
    self.assertTrue(self._rx(self._sensor()))
    self.assertFalse(self._tx(self._pedal(True)))
    self.assertTrue(self._rx(self._sdsu()))
    self.safety.set_controls_allowed(True)
    self.assertTrue(self._tx(self._pedal(True)))

  def test_faulted_inputs_cannot_actuate(self):
    for device, state in itertools.product(('pedal', 'sdsu'), range(1, 16)):
      if device == 'sdsu' and state == 5 and self.SAFETY_PARAM & ToyotaSafetyFlags.PRIUS_PEDAL_SDSU_4:
        continue  # Legacy stock-ACC watchdog status under openpilot takeover.
      self._reset_safety_hooks()
      self.assertTrue(self._rx(self._sensor()))
      self.assertTrue(self._rx(self._sdsu()))
      self.assertFalse(self._rx(self._sensor(state=state) if device == 'pedal' else self._sdsu(state)))
      self.safety.set_controls_allowed(True)
      self.assertFalse(self._tx(self._pedal(True)))
      self.assertFalse(self._tx(self._accel_msg(1)))
      self.assertTrue(self._tx(self._pedal(False)))

  def test_pedal_sensor_crc_and_replay(self):
    self.safety.set_controls_allowed(True)
    msg = self._sensor()
    msg[0].data[5] ^= 1
    self.assertFalse(self._rx(msg))
    self.safety.set_controls_allowed(True)
    self.assertFalse(self._tx(self._pedal(True)))
    good = self._sensor()
    self.assertTrue(self._rx(good))
    for _ in range(6):
      self._rx(good)
    self.safety.set_controls_allowed(True)
    self.assertFalse(self._tx(self._pedal(True)))

  def test_pcm_gas_feedback_is_not_a_driver_override(self):
    self.assertTrue(self._rx(self._sensor(805)))
    self.assertTrue(self._rx(self.packer.make_can_msg_safety('PCM_CRUISE', 0, {'GAS_RELEASED': False, 'CRUISE_ACTIVE': True})))
    self.assertFalse(self.safety.get_gas_pressed_prev())
    self.assertTrue(self._rx(self._sensor(806)))
    self.assertTrue(self.safety.get_gas_pressed_prev())

  def test_pedal_unavailable_in_incompatible_modes(self):
    for incompatible in (0, ToyotaSafetyFlags.STOCK_LONGITUDINAL, ToyotaSafetyFlags.LTA,
                         ToyotaSafetyFlags.ALT_BRAKE, ToyotaSafetyFlags.SECOC):
      param = self.EPS_SCALE if incompatible == 0 else self.SAFETY_PARAM | incompatible
      self.safety.set_safety_hooks(self.SAFETY_MODEL, param)
      self.safety.set_controls_allowed(True)
      self.assertFalse(self._tx(self._pedal(True)))
      self.assertFalse(self._tx(self._pedal(False)))


class TestToyotaPriusPedalFourByteSafety(TestToyotaPriusPedalSafety):
  DBC = 'toyota_prius_pedal_sdsu4_pt_generated'

  @property
  def SAFETY_PARAM(self):
    return super().SAFETY_PARAM | ToyotaSafetyFlags.PRIUS_PEDAL_SDSU_4

  def test_legacy_timeout_status_retains_actuation_limits(self):
    self.assertTrue(self._rx(self._sdsu(state=5)))
    self.safety.set_controls_allowed(True)
    self.assertTrue(self._tx(self._pedal(True)))
    self.assertTrue(self._tx(self._accel_msg(1)))
    self.assertFalse(self._tx(self._accel_msg(3)))
    self.safety.set_controls_allowed(False)
    self.assertFalse(self._tx(self._pedal(True)))
    self.assertFalse(self._tx(self._accel_msg(1)))
    self.safety.set_controls_allowed(True)
    self.assertTrue(self._rx(self._user_brake_msg(True)))
    self.assertFalse(self._tx(self._pedal(True)))
    self.assertFalse(self._tx(self._accel_msg(1)))
    self.assertTrue(self._tx(self._pedal(False)))

  def test_legacy_timeout_status_still_requires_valid_fresh_frames(self):
    self.assertTrue(self._rx(self._sdsu(state=5)))
    self.safety.set_timer(250001)
    self.safety.set_controls_allowed(True)
    self.assertFalse(self._tx(self._pedal(True)))
    self.assertFalse(self._tx(self._accel_msg(1)))
    self.assertTrue(self._rx(self._sensor()))
    msg = self._sdsu(state=5)
    msg[0].data[3] ^= 1
    self.assertFalse(self._rx(msg))
    self.safety.set_controls_allowed(True)
    self.assertFalse(self._tx(self._pedal(True)))
    good = self._sdsu(state=5)
    self.assertTrue(self._rx(good))
    for _ in range(6):
      self._rx(good)
    self.safety.set_controls_allowed(True)
    self.assertFalse(self._tx(self._pedal(True)))
    self.assertFalse(self._tx(self._accel_msg(1)))

  def test_wrong_length_sdsu_cannot_satisfy_freshness(self):
    for length in (0, 1, 2, 3, 5, 6, 7, 8):
      self._reset_safety_hooks()
      self.assertTrue(self._rx(self._sensor()))
      self._rx(libsafety_py.make_CANPacket(0x2FF, 0, bytes(length)))
      self.safety.set_controls_allowed(True)
      self.assertFalse(self._tx(self._pedal(True)))

  def test_sdsu_checksum_and_replay_block_actuation(self):
    msg = self._sdsu()
    msg[0].data[3] ^= 1
    self.assertFalse(self._rx(msg))
    self.safety.set_controls_allowed(True)
    self.assertFalse(self._tx(self._pedal(True)))
    good = self._sdsu()
    self.assertTrue(self._rx(good))
    for _ in range(6):
      self._rx(good)
    self.safety.set_controls_allowed(True)
    self.assertFalse(self._tx(self._pedal(True)))


class TestPriusPedalReleaseSafety(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    cls.safety = libsafety_py.ffi.dlopen(libsafety_py._build_libsafety(release=True))

  def test_release_build_enforces_pedal_mode_and_rejects_secoc_flag(self):
    packer = CANPacker('toyota_prius_pedal_pt_generated')
    for extra in (0, ToyotaSafetyFlags.SECOC, ToyotaSafetyFlags.STOCK_LONGITUDINAL):
      param = 66 | ToyotaSafetyFlags.PRIUS_PEDAL | extra
      self.assertEqual(self.safety.set_safety_hooks(CarParams.SafetyModel.toyota, param), 0)
      self.safety.init_tests()
      for name, values in (('GAS_SENSOR', {'COUNTER_PEDAL': 1}), ('SDSU', {})):
        addr, data, bus = packer.make_can_msg(name, 0, values)
        self.safety.safety_rx_hook(libsafety_py.make_CANPacket(addr, bus, data))
      self.safety.set_controls_allowed(True)
      addr, data, bus = toyotacan.create_prius_pedal_command(packer, True, 0)
      self.assertEqual(bool(self.safety.safety_tx_hook(libsafety_py.make_CANPacket(addr, bus, data))), extra == 0)


if __name__ == '__main__':
  unittest.main()
