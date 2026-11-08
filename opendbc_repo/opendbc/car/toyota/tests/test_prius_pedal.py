import itertools
import math
import unittest

from opendbc.can import CANPacker, CANParser
from opendbc.car import structs
from opendbc.car.toyota.interface import CarInterface
from opendbc.car.toyota.toyotacan import create_prius_pedal_command, pedal_checksum
from opendbc.car.toyota.values import CAR, CarControllerParams, ToyotaFlags, ToyotaSafetyFlags

PEDAL_DBC = 'toyota_prius_pedal_pt_generated'


def prius_params(pedal=True, sdsu=True, alpha=False, candidate=CAR.TOYOTA_PRIUS, is_release=False):
  fingerprint = {0: {}, 1: {}, 2: {}}
  if pedal:
    fingerprint[0][0x201] = 6
  if sdsu:
    fingerprint[0][0x2FF] = 8
  return CarInterface.get_params(candidate, fingerprint, [], alpha, is_release, False)


class TestPriusPedal(unittest.TestCase):
  def test_four_byte_sdsu_selects_openpilot_control(self):
    for alpha, is_release in itertools.product((False, True), repeat=2):
      cp = CarInterface.get_params(CAR.TOYOTA_PRIUS, {0: {0x201: 6, 0x2FF: 4}, 1: {}, 2: {}}, [], alpha, is_release, False)
      self.assertTrue(cp.openpilotLongitudinalControl)
      self.assertTrue(cp.flags & ToyotaFlags.PRIUS_PEDAL)
      self.assertTrue(cp.flags & ToyotaFlags.PRIUS_PEDAL_SDSU_4)
      self.assertFalse(cp.safetyConfigs[0].safetyParam & ToyotaSafetyFlags.STOCK_LONGITUDINAL)
      self.assertTrue(cp.safetyConfigs[0].safetyParam & ToyotaSafetyFlags.PRIUS_PEDAL)
      self.assertTrue(cp.safetyConfigs[0].safetyParam & ToyotaSafetyFlags.PRIUS_PEDAL_SDSU_4)
      self.assertEqual(cp.minEnableSpeed, -1.)
      ci = CarInterface(cp)
      self.assertEqual(ci.can_parsers['pt'].dbc_name, 'toyota_prius_pedal_sdsu4_pt_generated')

  def test_four_byte_control_sends_inactive_heartbeats_while_disengaged(self):
    cp = CarInterface.get_params(CAR.TOYOTA_PRIUS, {0: {0x201: 6, 0x2FF: 4}, 1: {}, 2: {}}, [], False, False, False)
    ci = CarInterface(cp)
    cs = ci.CS
    cs.out = structs.CarState(canValid=True, gearShifter='park').as_reader()
    controller = ci.CarController({bus: parser.dbc_name for bus, parser in ci.can_parsers.items()}, cp)
    cc = structs.CarControl(enabled=False, longActive=False)
    _, sends = controller.update(cc.as_reader(), cs, 0)
    frames = {addr: data for addr, data, _ in sends}
    self.assertEqual(frames[0x200][:5], bytes(5))
    self.assertEqual(frames[0x343][:2], bytes(2))

  def test_four_byte_sdsu_parser_checks_real_counter_and_checksum(self):
    parser = CANParser('toyota_prius_pedal_sdsu4_pt_generated', [('SDSU', 50)], 0)
    for i in range(32):
      counter = i & 15
      data = bytes([0, 0, counter, counter + 5])
      self.assertIn(0x2FF, parser.update([[(i + 1) * 20_000_000, [(0x2FF, data, 0)]]]))
      self.assertEqual(parser.vl['SDSU']['STATE'], 0)
    self.assertTrue(parser.can_valid)
    self.assertNotIn(0x2FF, parser.update([[660_000_000, [(0x2FF, bytes.fromhex('00000004'), 0)]]]))
    for i in range(6):
      parser.update([[(i + 34) * 20_000_000, [(0x2FF, bytes.fromhex('00000005'), 0)]]])
    self.assertFalse(parser.can_valid)

  def test_malformed_sdsu_lengths_do_not_select_pedal(self):
    for length in (0, 1, 2, 3, 5, 6, 7):
      cp = CarInterface.get_params(CAR.TOYOTA_PRIUS, {0: {0x201: 6, 0x2FF: length}, 1: {}, 2: {}}, [], False, False, False)
      self.assertFalse(cp.openpilotLongitudinalControl)

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

  def test_pedal_stop_is_not_a_manual_resume_requirement(self):
    # PCM state 7 is a stock RES-button hold. With the supported Pedal/SDSU,
    # wheel standstill remains true but must not latch LongControl in stopping.
    for pedal, sdsu_length, pcm_state in itertools.product((False, True), (4, 8), (0, 7, 8)):
      fingerprint = {0: {0x2FF: sdsu_length}, 1: {}, 2: {}}
      if pedal:
        fingerprint[0][0x201] = 6
      cp = CarInterface.get_params(CAR.TOYOTA_PRIUS, fingerprint, [], False, False, False)
      ci = CarInterface(cp)
      ci.CS.update(ci.can_parsers)
      for parser in ci.can_parsers.values():
        packer = CANPacker(parser.dbc_name)
        values = {'PCM_CRUISE': {'CRUISE_STATE': pcm_state},
                  'WHEEL_SPEEDS': {f'WHEEL_SPEED_{wheel}': 0 for wheel in ('FL', 'FR', 'RL', 'RR')}}
        frames = [packer.make_can_msg(message.name, parser.bus, values.get(message.name, {}))
                  for message in list(parser.message_states.values())]
        parser.update([[1_000_000_000, frames]])
      state = ci.CS.update(ci.can_parsers)
      with self.subTest(pedal=pedal, sdsu_length=sdsu_length, pcm_state=pcm_state):
        self.assertEqual(ci.CS.pcm_acc_status, pcm_state)
        self.assertTrue(state.standstill)
        self.assertEqual(state.cruiseState.standstill, pcm_state == 7 and not pedal)

  def test_pedal_retains_official_prius_lateral_parameters(self):
    # Frozen from official release-tizi 0.11.2, f7db927c728bab57bb1263e05465766a8f28fc9d.
    # The EPS-specific delay/deadzone must survive both Pedal/SDSU configurations.
    for eps, delay, deadzone in ((None, 0.12, 0.), (b'8965B47060' + bytes(6), 0.12, 0.),
                                 (b'8965B47061' + bytes(6), 0.25, 0.2)):
      firmware = [] if eps is None else [structs.CarParams.CarFw(ecu='eps', fwVersion=eps)]
      for length in (4, 8):
        cp = CarInterface.get_params(CAR.TOYOTA_PRIUS, {0: {0x201: 6, 0x2FF: length}, 1: {}, 2: {}},
                                     firmware, False, False, False)
        with self.subTest(eps=eps, sdsu_length=length):
          self.assertEqual(cp.lateralTuning.which(), 'torque')
          self.assertEqual(str(cp.steerControlType), 'torque')
          self.assertFalse(cp.steerAtStandstill)
          for key, expected in {'minSteerSpeed': 0., 'steerRatio': 15.74,
                                'steerActuatorDelay': delay, 'steerLimitTimer': 0.4}.items():
            self.assertAlmostEqual(getattr(cp, key), expected, places=6)
          for key, expected in {'latAccelFactor': 1.6, 'latAccelOffset': 0., 'friction': 0.151515,
                                'steeringAngleDeadzoneDeg': deadzone}.items():
            self.assertAlmostEqual(getattr(cp.lateralTuning.torque, key), expected, places=6)
          limits = CarControllerParams(cp)
          self.assertEqual({key: getattr(limits, key) for key in ('STEER_MAX', 'STEER_ERROR_MAX', 'STEER_DELTA_UP', 'STEER_DELTA_DOWN')},
                           {'STEER_MAX': 1500, 'STEER_ERROR_MAX': 350, 'STEER_DELTA_UP': 15, 'STEER_DELTA_DOWN': 25})
          self.assertEqual(cp.safetyConfigs[0].safetyParam & 0xFF, 66)

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

  def test_acceleration_feedback_does_not_amplify_small_oscillations(self):
    # Reproduce hunting seen at a steady cruise: small wheel-acceleration
    # fluctuations must not produce much larger alternating ACC commands.
    for sdsu_length in (4, 8):
      cp = CarInterface.get_params(CAR.TOYOTA_PRIUS, {0: {0x201: 6, 0x2FF: sdsu_length}, 1: {}, 2: {}}, [], False, False, False)
      ci = CarInterface(cp)
      controller = ci.CarController({bus: parser.dbc_name for bus, parser in ci.can_parsers.items()}, cp)
      cs = ci.CS
      cs.pedal_ready = True
      cs.pcm_acc_status = 8
      cc = structs.CarControl(enabled=True, longActive=True)
      cc.actuators.accel = 0.05
      cc.actuators.longControlState = 'pid'
      commands = []
      for frame in range(2000):
        acceleration = cc.actuators.accel + 0.1 * math.sin(2 * math.pi * 0.2 * frame * 0.01)
        cs.out = structs.CarState(canValid=True, vEgo=14., vEgoRaw=14., aEgo=acceleration,
                                 gearShifter='drive').as_reader()
        _, sends = controller.update(cc.as_reader(), cs, frame * 10_000_000)
        commands.extend(int.from_bytes(data[:2], 'big', signed=True) / 1000
                        for addr, data, _ in sends if addr == 0x343 and frame >= 1000)
      with self.subTest(sdsu_length=sdsu_length):
        self.assertLess(max(commands) - min(commands), 0.10)
        self.assertLess(max(abs(b - a) for a, b in itertools.pairwise(commands)), 0.025)

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

  def test_legacy_status_does_not_mask_native_or_pedal_faults(self):
    for length in (4, 8):
      cp = CarInterface.get_params(CAR.TOYOTA_PRIUS, {0: {0x201: 6, 0x2FF: length}, 1: {}, 2: {}}, [], False, False, False)
      ci = CarInterface(cp)
      packers = {bus: CANPacker(parser.dbc_name) for bus, parser in ci.can_parsers.items()}
      ci.CS.update(ci.can_parsers)
      timestamp = 1_000_000_000
      for sdsu_state, pedal_state, native_fault, lockout in itertools.product(range(16), (0, 5), (0, 1), (1, 2)):
        timestamp += 20_000_000
        for bus, parser in ci.can_parsers.items():
          frames = []
          for message in list(parser.message_states.values()):
            values = {
              'SDSU': {'STATE': sdsu_state},
              'GAS_SENSOR': {'STATE': pedal_state},
              'PCM_CRUISE_2': {'ACC_FAULTED': native_fault, 'LOW_SPEED_LOCKOUT': lockout},
            }.get(message.name, {})
            frames.append(packers[bus].make_can_msg(message.name, parser.bus, values))
          parser.update([[timestamp, frames]])
        state = ci.CS.update(ci.can_parsers)
        with self.subTest(length=length, sdsu=sdsu_state, pedal=pedal_state, native=native_fault, lockout=lockout):
          expected_ready = pedal_state == 0 and (sdsu_state == 0 or (length == 4 and sdsu_state == 5))
          self.assertEqual(ci.CS.pedal_ready, expected_ready)
          self.assertEqual(state.accFaulted, not expected_ready or bool(native_fault) or lockout == 2)
          self.assertEqual(ci.can_parsers['pt'].vl['SDSU']['STATE'], sdsu_state)

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
