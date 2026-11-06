import itertools
import unittest

from opendbc.can import CANPacker, CANParser
from opendbc.car import structs
from opendbc.car.toyota.interface import CarInterface
from opendbc.car.toyota.toyotacan import create_prius_pedal_command, pedal_checksum
from opendbc.car.toyota.values import CAR, ToyotaFlags, ToyotaSafetyFlags

PEDAL_DBC = 'toyota_prius_pedal_pt_generated'


def prius_params(pedal=True, sdsu=True, alpha=False, candidate=CAR.TOYOTA_PRIUS, is_release=False):
  fingerprint = {0: {}, 1: {}, 2: {}}
  if pedal:
    fingerprint[0][0x201] = 6
  if sdsu:
    fingerprint[0][0x2FF] = 8
  return CarInterface.get_params(candidate, fingerprint, [], alpha, is_release, False)


class TestPriusPedal(unittest.TestCase):
  def test_configuration_auto_detects_both_devices_without_alpha_opt_in(self):
    for pedal, sdsu, alpha, is_release in itertools.product((False, True), repeat=4):
      with self.subTest(pedal=pedal, sdsu=sdsu, alpha=alpha, is_release=is_release):
        cp = prius_params(pedal, sdsu, alpha, is_release=is_release)
        enabled = pedal and sdsu
        self.assertEqual(cp.openpilotLongitudinalControl, enabled)
        self.assertFalse(cp.alphaLongitudinalAvailable)
        self.assertEqual(bool(cp.flags & ToyotaFlags.PRIUS_PEDAL), enabled)
        self.assertEqual(bool(cp.safetyConfigs[0].safetyParam & ToyotaSafetyFlags.PRIUS_PEDAL), enabled)
        self.assertEqual(bool(cp.safetyConfigs[0].safetyParam & ToyotaSafetyFlags.STOCK_LONGITUDINAL), not enabled)

  def test_does_not_enable_other_toyotas(self):
    for candidate in CAR:
      if candidate != CAR.TOYOTA_PRIUS:
        with self.subTest(candidate=candidate):
          cp = prius_params(candidate=candidate)
          self.assertFalse(cp.flags & ToyotaFlags.PRIUS_PEDAL)
          self.assertFalse(cp.safetyConfigs[0].safetyParam & ToyotaSafetyFlags.PRIUS_PEDAL)

  def test_wrong_length_or_bus_does_not_enable(self):
    for addr, length in ((0x201, 8), (0x2FF, 6)):
      fp = {0: {0x201: 6, 0x2FF: 8}, 1: {}, 2: {}}
      fp[0][addr] = length
      cp = CarInterface.get_params(CAR.TOYOTA_PRIUS, fp, [], True, False, False)
      self.assertFalse(cp.openpilotLongitudinalControl)
      fp[2][addr] = fp[0].pop(addr)
      cp = CarInterface.get_params(CAR.TOYOTA_PRIUS, fp, [], True, False, False)
      self.assertFalse(cp.openpilotLongitudinalControl)

  def test_command_tracks_counter_and_checksum(self):
    packer = CANPacker(PEDAL_DBC)
    for active, counter in itertools.product((False, True), range(32)):
      addr, data, bus = create_prius_pedal_command(packer, active, counter)
      self.assertEqual((addr, bus, len(data)), (0x200, 0, 6))
      self.assertEqual(data[4], (0x80 if active else 0) | (counter & 0xF))
      self.assertEqual(data[5], pedal_checksum(data[:5]))
      self.assertEqual(data[:4], bytes.fromhex('029a0474') if active else bytes(4))

  def test_parser_rejects_bad_pedal_checksum_and_counter(self):
    dbc = PEDAL_DBC
    packer = CANPacker(dbc)
    parser = CANParser(dbc, [('GAS_SENSOR', 50)], 0)
    good = packer.make_can_msg('GAS_SENSOR', 0, {'COUNTER_PEDAL': 1})
    self.assertIn(0x201, parser.update([[1_000_000, [good]]]))
    corrupt = (good[0], good[1][:-1] + bytes([good[1][-1] ^ 1]), good[2])
    self.assertNotIn(0x201, parser.update([[2_000_000, [corrupt]]]))
    for t in range(3, 10):
      parser.update([[t * 1_000_000, [good]]])
    self.assertFalse(parser.can_valid)

  def test_controller_only_assists_an_eligible_start(self):
    cp = prius_params()
    ci = CarInterface(cp)
    cs = ci.CS
    for active, stopped, accel, brake, gas, ready, valid, fault, gear in (
      (True, True, 1.0, False, False, True, True, False, 'drive'),
      (False, True, 1.0, False, False, True, True, False, 'drive'),
      (True, False, 1.0, False, False, True, True, False, 'drive'),
      (True, True, 0.0, False, False, True, True, False, 'drive'),
      (True, True, -1.0, False, False, True, True, False, 'drive'),
      (True, True, float('nan'), False, False, True, True, False, 'drive'),
      (True, True, float('inf'), False, False, True, True, False, 'drive'),
      (True, True, 1.0, True, False, True, True, False, 'drive'),
      (True, True, 1.0, False, True, True, True, False, 'drive'),
      (True, True, 1.0, False, False, False, True, False, 'drive'),
      (True, True, 1.0, False, False, True, False, False, 'drive'),
      (True, True, 1.0, False, False, True, True, True, 'drive'),
      (True, True, 1.0, False, False, True, True, False, 'reverse'),
    ):
      with self.subTest(active=active, stopped=stopped, accel=accel, brake=brake, gas=gas, ready=ready, valid=valid, fault=fault, gear=gear):
        controller = ci.CarController({bus: parser.dbc_name for bus, parser in ci.can_parsers.items()}, cp)
        cs.out = structs.CarState(canValid=valid, standstill=stopped, vEgoRaw=0 if stopped else 1,
                                 brakePressed=brake, gasPressed=gas, accFaulted=fault, gearShifter=gear).as_reader()
        cs.pedal_ready = ready
        cs.pcm_acc_status = 8
        cc = structs.CarControl(enabled=active, longActive=active)
        cc.actuators.accel = accel
        _, sends = controller.update(cc.as_reader(), cs, 0)
        pedal = [data for addr, data, bus in sends if addr == 0x200]
        self.assertEqual(len(pedal), 1)
        expected_active = (active and stopped and accel > 0 and accel != float('inf') and not brake and
                           not gas and ready and valid and not fault and gear == 'drive')
        self.assertEqual(bool(pedal[0][4] & 0x80), expected_active)
        _, sends = controller.update(cc.as_reader(), cs, 10_000_000)
        self.assertFalse(any(addr == 0x200 for addr, _, _ in sends))

  def test_controller_no_pedal_messages_without_feature(self):
    for pedal, sdsu in ((False, False), (False, True), (True, False)):
      with self.subTest(pedal=pedal, sdsu=sdsu):
        ci = CarInterface(prius_params(pedal=pedal, sdsu=sdsu))
        ci.CS.out = structs.CarState().as_reader()
        _, sends = ci.CC.update(structs.CarControl().as_reader(), ci.CS, 0)
        self.assertFalse(any(addr == 0x200 for addr, _, _ in sends))

  def test_cancel_sends_inactive_pedal_even_if_long_active(self):
    ci = CarInterface(prius_params())
    ci.CS.out = structs.CarState(canValid=True, standstill=True, gearShifter='drive').as_reader()
    ci.CS.pedal_ready = True
    cc = structs.CarControl(enabled=True, longActive=True)
    cc.cruiseControl.cancel = True
    cc.actuators.accel = 1
    _, sends = ci.CC.update(cc.as_reader(), ci.CS, 0)
    pedal = next(data for addr, data, _ in sends if addr == 0x200)
    self.assertEqual(pedal[:5], bytes(5))

  def test_live_parser_driver_override_faults_and_distance_button(self):
    ci = CarInterface(prius_params())
    packers = {bus: CANPacker(parser.dbc_name) for bus, parser in ci.can_parsers.items()}
    ci.CS.update(ci.can_parsers)  # Register all standard Toyota signals.
    timestamp = 1_000_000_000

    def feed(gas1=805, gas2=805, pedal_state=0, sdsu_state=0, distance=0, drop_pedal=False):
      nonlocal timestamp
      timestamp += 20_000_000
      for bus, parser in ci.can_parsers.items():
        frames = []
        for state in list(parser.message_states.values()):
          if state.name == 'GAS_SENSOR' and drop_pedal:
            continue
          values = {
            'GAS_SENSOR': {'INTERCEPTOR_GAS': gas1, 'INTERCEPTOR_GAS2': gas2, 'STATE': pedal_state},
            'SDSU': {'STATE': sdsu_state, 'FD_BUTTON': distance},
            'PCM_CRUISE': {'GAS_RELEASED': False, 'CRUISE_ACTIVE': True},
            'WHEEL_SPEEDS': {f'WHEEL_SPEED_{wheel}': 0 for wheel in ('FL', 'FR', 'RL', 'RR')},
          }.get(state.name, {})
          frames.append(packers[bus].make_can_msg(state.name, parser.bus, values))
        parser.update([[timestamp, frames]])
      return ci.CS.update(ci.can_parsers)

    state = feed(gas1=0, gas2=1610)
    self.assertTrue(ci.CS.pedal_ready)
    self.assertFalse(state.gasPressed)  # Mean is 805; PCM feedback is deliberately ignored.
    self.assertFalse(feed(gas1=0, gas2=1611).gasPressed)  # Match panda's integer average.
    state = feed(gas1=0, gas2=1612, distance=1)
    self.assertTrue(state.gasPressed)
    self.assertTrue(any(event.type == structs.CarState.ButtonEvent.Type.gapAdjustCruise for event in state.buttonEvents))
    for pedal_state, sdsu_state in ((1, 0), (0, 1), (0, 7)):
      state = feed(pedal_state=pedal_state, sdsu_state=sdsu_state)
      self.assertFalse(ci.CS.pedal_ready)
      self.assertTrue(state.accFaulted)
    feed()
    self.assertTrue(ci.CS.pedal_ready)
    for _ in range(15):
      state = feed(drop_pedal=True)
    self.assertFalse(ci.CS.pedal_ready)
    self.assertTrue(state.accFaulted)


if __name__ == '__main__':
  unittest.main()
