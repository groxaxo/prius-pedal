"""Exercise repeated stop/hold/restart cycles with the actual control chain, without CAN I/O."""
import unittest

from opendbc.can import CANPacker
from opendbc.car import structs
from openpilot.selfdrive.car.car_events import CarEvents, EventName
from openpilot.selfdrive.controls.lib.longcontrol import LongControl, LongCtrlState
from tools.prius_pedal import test_stop_and_go


class TestRepeatedPriusStops(unittest.TestCase):
  make_car = test_stop_and_go.TestPriusStopAndGo.make_car

  def test_repeated_stops_follow_planner_without_driver_resume(self):
    for length in (4, 8):
      with self.subTest(sdsu_length=length):
        self.run_cycles(length)

  def run_cycles(self, length):
    cp, ci, _ = self.make_car(length)
    packers = {bus: CANPacker(parser.dbc_name) for bus, parser in ci.can_parsers.items()}
    gear = next(key for key, value in ci.CS.shifter_values.items() if value == 'D')
    long_control = LongControl(cp)
    cc = structs.CarControl(enabled=True, longActive=True)
    timestamp = 640_000_000  # Continue from the fixture's last CAN timestamp.

    def step(speed, pcm_state, should_stop):
      nonlocal timestamp
      timestamp += 10_000_000
      frames = []
      for bus, parser in ci.can_parsers.items():
        values = {
          'PCM_CRUISE': {'CRUISE_STATE': pcm_state, 'CRUISE_ACTIVE': 1, 'GAS_RELEASED': 1},
          'PCM_CRUISE_2': {'MAIN_ON': 1, 'LOW_SPEED_LOCKOUT': 1},
          'WHEEL_SPEEDS': {f'WHEEL_SPEED_{wheel}': speed for wheel in ('FL', 'FR', 'RL', 'RR')},
          'GAS_SENSOR': {'INTERCEPTOR_GAS': 805, 'INTERCEPTOR_GAS2': 805},
          'SDSU': {'STATE': 5 if length == 4 else 0},
          'GEAR_PACKET': {'GEAR': gear},
          'VSC1S07': {'GVC': 0},
        }
        frames += [packers[bus].make_can_msg(message.name, parser.bus, values.get(message.name, {}))
                   for message in list(parser.message_states.values())]
      state = ci.update([[timestamp, frames]])
      self.assertTrue(state.canValid)
      self.assertFalse(state.accFaulted)
      self.assertFalse(state.gasPressed)
      self.assertFalse(state.brakePressed)
      self.assertFalse(state.cruiseState.standstill)
      self.assertFalse(state.buttonEvents)
      self.assertFalse(cc.cruiseControl.resume)
      cc.actuators.accel = float(long_control.update(True, state, 0.452, should_stop, (-3.5, 1.5)))
      cc.actuators.longControlState = long_control.long_control_state
      _, sends = ci.CC.update(cc.as_reader(), ci.CS, timestamp)
      self.assertNotIn(EventName.resumeRequired, CarEvents(cp).update(state, state, cc.as_reader()).names)
      return state, [data for addr, data, _ in sends if addr == 0x200]

    def assert_inactive(commands):
      for data in commands:
        self.assertEqual(data[:4], bytes(4))
        self.assertFalse(data[4] & 0x80)

    restarts = 0
    for _ in range(5):
      for frame in range(300):
        # Enter the stop in PCM state 8, then observe its stock state-7 hold.
        state, commands = step(0, 8 if frame < 25 else 7, True)
        self.assertTrue(state.standstill)
        self.assertEqual(long_control.long_control_state, LongCtrlState.stopping)
        self.assertLessEqual(cc.actuators.accel, 0.)
        assert_inactive(commands)

      active_commands = 0
      for _ in range(6):
        state, commands = step(0, 7, False)
        self.assertTrue(state.standstill)
        self.assertEqual(long_control.long_control_state, LongCtrlState.pid)
        self.assertGreater(cc.actuators.accel, 0.)
        for data in commands:
          self.assertEqual(data[:4], bytes.fromhex('029a0474'))
          self.assertTrue(data[4] & 0x80)
          active_commands += 1
      self.assertEqual(active_commands, 3)  # 50 Hz assist at the 100 Hz control rate.
      restarts += 1

      for _ in range(100):
        state, commands = step(6, 8, False)
        self.assertFalse(state.standstill)
        self.assertEqual(long_control.long_control_state, LongCtrlState.pid)
        assert_inactive(commands)
    self.assertEqual(restarts, 5)


if __name__ == '__main__':
  unittest.main()
