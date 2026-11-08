"""Offline integration tests; require the full openpilot runtime and never send CAN.

Run on an inactive checkout: python -m unittest tools.prius_pedal.test_stop_and_go
"""
import unittest

from opendbc.can import CANPacker
from opendbc.car import structs
from opendbc.car.toyota.interface import CarInterface
from opendbc.car.toyota.values import CAR, ToyotaFlags
from openpilot.selfdrive.car.car_events import CarEvents, EventName
from openpilot.selfdrive.controls.lib.longcontrol import LongControl, LongCtrlState


class TestPriusStopAndGo(unittest.TestCase):
  def make_car(self, length):
    cp = CarInterface.get_params(CAR.TOYOTA_PRIUS, {0: {0x201: 6, 0x2FF: length}, 1: {}, 2: {}}, [], False, False, False)
    cp.flags |= ToyotaFlags.HYBRID.value
    ci = CarInterface(cp)
    ci.CS.update(ci.can_parsers)
    packers = {bus: CANPacker(parser.dbc_name) for bus, parser in ci.can_parsers.items()}
    gear = next(key for key, value in ci.CS.shifter_values.items() if value == 'D')
    for frame in range(32):
      frames = []
      for bus, parser in ci.can_parsers.items():
        values = {
          'PCM_CRUISE': {'CRUISE_STATE': 7, 'CRUISE_ACTIVE': 1, 'GAS_RELEASED': 1},
          'PCM_CRUISE_2': {'MAIN_ON': 1, 'LOW_SPEED_LOCKOUT': 1},
          'WHEEL_SPEEDS': {f'WHEEL_SPEED_{wheel}': 0 for wheel in ('FL', 'FR', 'RL', 'RR')},
          'GAS_SENSOR': {'INTERCEPTOR_GAS': 805, 'INTERCEPTOR_GAS2': 805},
          'SDSU': {'STATE': 5 if length == 4 else 0},
          'GEAR_PACKET': {'GEAR': gear},
          'VSC1S07': {'GVC': 0},
        }
        frames += [packers[bus].make_can_msg(message.name, parser.bus, values.get(message.name, {}))
                   for message in list(parser.message_states.values())]
      state = ci.update([[(frame + 1) * 20_000_000, frames]])
    self.assertTrue(state.canValid)
    self.assertTrue(state.standstill)
    self.assertFalse(state.gasPressed)
    self.assertFalse(state.brakePressed)
    self.assertFalse(state.accFaulted)
    self.assertTrue(ci.CS.pedal_ready)
    self.assertEqual(ci.CS.pcm_acc_status, 7)
    return cp, ci, state.as_reader()

  def test_planner_releases_stock_hold_without_resume_button(self):
    for length in (4, 8):
      with self.subTest(sdsu_length=length):
        cp, ci, state = self.make_car(length)
        long_control = LongControl(cp)
        cc = structs.CarControl(enabled=True, longActive=True)
        for frame in range(300):
          # A model/lead stop request always wins, even with positive a_target.
          cc.actuators.accel = float(long_control.update(True, state, 0.5, True, (-3.5, 1.5)))
          cc.actuators.longControlState = long_control.long_control_state
          _, sends = ci.CC.update(cc.as_reader(), ci.CS, frame * 10_000_000)
          self.assertEqual(long_control.long_control_state, LongCtrlState.stopping)
          self.assertTrue(all(not data[4] & 0x80 for addr, data, _ in sends if addr == 0x200))

        # Recorded failure: planner requested +0.452 while PCM still reported 7.
        cc.actuators.accel = float(long_control.update(True, state, 0.452, False, (-3.5, 1.5)))
        cc.actuators.longControlState = long_control.long_control_state
        self.assertEqual(long_control.long_control_state, LongCtrlState.pid)
        self.assertGreater(cc.actuators.accel, 0)
        _, sends = ci.CC.update(cc.as_reader(), ci.CS, 3_000_000_000)
        pedal = next(data for addr, data, _ in sends if addr == 0x200)
        self.assertEqual(pedal[:4], bytes.fromhex('029a0474'))
        self.assertTrue(pedal[4] & 0x80)
        events = CarEvents(cp).update(state, state, cc.as_reader())
        self.assertNotIn(EventName.resumeRequired, events.names)

        # The same unchanged raw PCM status must not keep assist on once moving.
        moving = state.as_builder()
        moving.standstill = False
        moving.vEgo = moving.vEgoRaw = 0.5
        ci.CS.out = moving.as_reader()
        ci.CC.frame += 1
        _, sends = ci.CC.update(cc.as_reader(), ci.CS, 3_020_000_000)
        pedal = next(data for addr, data, _ in sends if addr == 0x200)
        self.assertEqual(pedal[:4], bytes(4))
        self.assertFalse(pedal[4] & 0x80)

  def test_driver_brake_and_disengagement_keep_launch_inactive(self):
    for length in (4, 8):
      cp, ci, state = self.make_car(length)
      for active, brake in ((False, False), (True, True)):
        with self.subTest(sdsu_length=length, active=active, brake=brake):
          state = state.as_builder()
          state.brakePressed = brake
          state = state.as_reader()
          ci.CS.out = state
          long_control = LongControl(cp)
          cc = structs.CarControl(enabled=active, longActive=active)
          cc.actuators.accel = float(long_control.update(active, state, 0.452, False, (-3.5, 1.5)))
          cc.actuators.longControlState = long_control.long_control_state
          ci.CC.frame = 0
          _, sends = ci.CC.update(cc.as_reader(), ci.CS, 0)
          pedal = next(data for addr, data, _ in sends if addr == 0x200)
          self.assertEqual(pedal[:5], bytes(5))


if __name__ == '__main__':
  unittest.main()
