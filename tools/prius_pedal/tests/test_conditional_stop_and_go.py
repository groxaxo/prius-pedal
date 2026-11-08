"""Actual planner/controller/CAN-packer integration in an inactive full runtime; no CAN I/O."""
import unittest

from opendbc.car import structs
from openpilot.cereal import log
from openpilot.selfdrive.controls.lib.conditional_experimental_mode import ConditionalExperimentalMode
from openpilot.selfdrive.controls.lib.longcontrol import LongControl, LongCtrlState
from openpilot.selfdrive.controls.lib.longitudinal_planner import LongitudinalPlanner
from openpilot.selfdrive.controls.tests.test_conditional_experimental import model
from tools.prius_pedal import test_stop_and_go


class TestConditionalStopAndGo(unittest.TestCase):
  make_car = test_stop_and_go.TestPriusStopAndGo.make_car

  def make_chain(self, length):
    cp, ci, state = self.make_car(length)
    state = state.as_builder()
    state.vCruise = state.vCruiseCluster = 60.
    sm = {'carState': state, 'carControl': structs.CarControl.new_message(),
          'controlsState': log.ControlsState.new_message(), 'selfdriveState': log.SelfdriveState.new_message(),
          'vehicleParameters': log.VehicleParameters.new_message(), 'radarState': log.RadarState.new_message(),
          'modelV2': log.ModelDataV2.new_message()}
    sm['selfdriveState'].enabled = True
    sm['selfdriveState'].personality = 'standard'
    sm['controlsState'].longControlState = 'stopping'
    sm['modelV2'].meta.disengagePredictions.gasPressProbs = [1., 1.]
    return cp, ci, state, sm, ConditionalExperimentalMode(), LongitudinalPlanner(cp), LongControl(cp)

  @staticmethod
  def set_model(sm, go):
    sample = model(speed=0., end_speed=6. if go else 0., stop=not go, accel=.452 if go else -1.)
    md = sm['modelV2']
    md.velocity.t, md.velocity.x = sample.velocity.t, sample.velocity.x
    md.position.x, md.position.y = sample.position.x, sample.position.y
    md.orientationRate.z = sample.orientationRate.z
    md.action.shouldStop = sample.action.shouldStop
    md.action.desiredAcceleration = sample.action.desiredAcceleration

  def test_repeated_stop_release_without_resume_or_stronger_pedal(self):
    for length in (4, 8):
      with self.subTest(sdsu_length=length):
        self.run_cycles(length)

  def run_cycles(self, length):
    cp, ci, state, sm, selector, planner, control = self.make_chain(length)
    frame = 0
    cc = structs.CarControl(enabled=True, longActive=True)

    def step(go, lead_stopped=False):
      nonlocal frame
      frame += 1
      self.set_model(sm, go)
      lead = sm['radarState'].leadOne
      lead.present = lead_stopped
      lead.dRel, lead.vLead, lead.vRel = 6., 0., 0.
      sm['selfdriveState'].experimentalMode = selector.update(
        requested=True, conditional=True, enabled=True, valid=True, model_time=frame * 50_000_000,
        model_age=0., car_state=state, model=sm['modelV2'], lead=lead, curvature=0., roll=0.)
      planner.update(sm)
      outputs = []
      for tick in range(5):
        cc.actuators.accel = float(control.update(True, state, planner.output_a_target,
                                                 planner.output_should_stop, (-3.5, 1.5)))
        cc.actuators.longControlState = control.long_control_state
        sm['controlsState'].longControlState = control.long_control_state
        _, commands = ci.CC.update(cc.as_reader(), ci.CS, (frame * 5 + tick) * 10_000_000)
        outputs.extend(data for addr, data, _ in commands if addr == 0x200)
      return outputs

    for _ in range(5):
      for _ in range(60):
        self.assertTrue(all(not data[4] & 0x80 for data in step(False)))
        self.assertEqual(control.long_control_state, LongCtrlState.stopping)
      step(True)
      self.assertTrue(selector.experimental_mode)
      outputs = step(True)
      self.assertFalse(selector.experimental_mode)
      for _ in range(30):
        outputs.extend(step(True))
      active = [data for data in outputs if data[4] & 0x80]
      self.assertTrue(active)
      self.assertTrue(all(data[:4] == bytes.fromhex('029a0474') for data in active))
      self.assertEqual(control.long_control_state, LongCtrlState.pid)
      self.assertFalse(cc.cruiseControl.resume)
      self.assertFalse(state.cruiseState.standstill)

  def test_lead_stop_remains_authoritative_after_mode_release(self):
    for length in (4, 8):
      with self.subTest(sdsu_length=length):
        cp, ci, state, sm, selector, planner, control = self.make_chain(length)
        self.set_model(sm, go=True)
        lead = sm['radarState'].leadOne
        lead.present, lead.dRel, lead.vLead, lead.vRel = True, 3., 0., 0.
        sm['selfdriveState'].experimentalMode = False
        for _ in range(60):
          planner.update(sm)
          self.assertTrue(planner.output_should_stop)
          self.assertLessEqual(control.update(True, state, planner.output_a_target, planner.output_should_stop, (-3.5, 1.5)), 0.)
          self.assertEqual(control.long_control_state, LongCtrlState.stopping)

  def test_actual_planner_recovers_cruise_request_outside_stop_and_curve(self):
    # Synthetic steady road matching the diagnosed speed/request relationship;
    # no private route, images, identifying data or raw log fixture is published.
    for length in (4, 8):
      with self.subTest(sdsu_length=length):
        cp, ci, state, sm, _, _, _ = self.make_chain(length)
        state.vEgo = state.vEgoRaw = 23.3526
        state.vCruise, state.vCruiseCluster = 105., 111.
        state.standstill = False
        sm['controlsState'].longControlState = 'pid'
        sample = model(speed=23.3526, accel=.0012445)
        md = sm['modelV2']
        md.velocity.t, md.velocity.x = sample.velocity.t, sample.velocity.x
        md.position.x, md.position.y = sample.position.x, sample.position.y
        md.orientationRate.z = sample.orientationRate.z
        md.action.shouldStop, md.action.desiredAcceleration = False, .0012445
        lead = sm['radarState'].leadOne
        lead.present, lead.dRel, lead.vLead, lead.vRel = True, 107., 26.2, 2.8474
        lead.aLeadK, lead.aLeadTau = -.25, 1.5
        results = {}
        for conditional in (False, True):
          selector = ConditionalExperimentalMode()
          planner = LongitudinalPlanner(cp, init_v=state.vEgo)
          for frame in range(60):
            sm['selfdriveState'].experimentalMode = selector.update(
              requested=True, conditional=conditional, enabled=True, valid=True,
              model_time=(frame + 1) * 50_000_000, model_age=0., car_state=state, model=md,
              lead=lead, curvature=0., roll=0.)
            planner.update(sm)
          results[conditional] = planner.output_a_target
          self.assertFalse(planner.output_should_stop)
          self.assertEqual(state.vCruise, 105.)
          self.assertEqual(state.vCruiseCluster, 111.)
        self.assertAlmostEqual(results[False], .0012445, places=5)
        self.assertGreater(results[True], .7)


if __name__ == '__main__':
  unittest.main()
