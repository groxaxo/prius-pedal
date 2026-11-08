"""Deterministic selector tests; no Params, native runtime, sockets or CAN."""
import copy
from types import SimpleNamespace as NS
import unittest

import numpy as np

from openpilot.selfdrive.controls.lib.conditional_experimental_mode import ConditionalExperimentalMode


def model(speed=20., end_speed=None, stop=False, accel=0., curve=False):
  t = np.linspace(0, 1, 33)**2 * 10
  velocity = np.linspace(speed, speed if end_speed is None else end_speed, 33)
  curvature = np.zeros(33)
  if curve:
    curvature[16:] = 0.004
  position = np.concatenate(([0.], np.cumsum((velocity[1:] + velocity[:-1]) / 2 * np.diff(t))))
  return NS(velocity=NS(t=t.tolist(), x=velocity.tolist()),
            position=NS(x=position.tolist(), y=np.zeros(33).tolist()),
            orientationRate=NS(z=(velocity * curvature).tolist()),
            action=NS(shouldStop=stop, desiredAcceleration=accel))


class TestConditionalExperimentalMode(unittest.TestCase):
  def setUp(self):
    self.selector = ConditionalExperimentalMode()
    self.frame = 0
    self.inputs = {'requested': True, 'conditional': True, 'enabled': True, 'valid': True, 'model_age': 0.,
                   'car_state': NS(vEgo=20., standstill=False, leftBlinker=False, rightBlinker=False),
                   'model': model(), 'lead': NS(present=False), 'curvature': 0., 'roll': 0.}

  def step(self, **kwargs):
    self.frame += 1
    return self.selector.update(model_time=self.frame * 50_000_000, **(self.inputs | kwargs))

  def test_clear_road_does_not_take_models_near_zero_acceleration(self):
    for _ in range(100):
      self.assertFalse(self.step())
    self.assertEqual(self.selector.reason, 'cruise')

  def test_direct_model_stop_is_immediate_and_has_priority_over_curve(self):
    self.assertTrue(self.step(model=model(stop=True), curvature=.01))
    self.assertEqual(self.selector.reason, 'stop')

  def test_approaching_stop_uses_filtered_prediction(self):
    md = model(end_speed=0.)
    for _ in range(20):
      self.assertFalse(self.step(model=md))
    for _ in range(20):
      self.step(model=md)
    self.assertTrue(self.selector.experimental_mode)
    self.assertEqual(self.selector.reason, 'stop')

  def test_filter_entry_matches_pinned_frogpilot_timing(self):
    # Golden step-response counts from the pinned 20 Hz FrogPilot filters.
    md = model(end_speed=0.)
    for _ in range(30):
      self.assertFalse(self.step(model=md))
    self.assertTrue(self.step(model=md))  # 31 model frames, 1.55 seconds.
    self.selector.reset()
    for _ in range(18):
      self.assertFalse(self.step(curvature=.004))
    self.assertTrue(self.step(curvature=.004))  # 19 model frames, .95 seconds.

  def test_frogpilot_lead_relevance_not_presence_controls_stop_filter(self):
    md = model(end_speed=0.)
    near = NS(present=True, dRel=20., vLead=10., aLeadK=0.)
    for _ in range(60):
      self.assertFalse(self.step(model=md, lead=near))
    distant = NS(present=True, dRel=200., vLead=25., aLeadK=0.)
    for _ in range(40):
      self.step(model=md, lead=distant)
    self.assertTrue(self.selector.experimental_mode)

  def test_curves_enter_and_exit_with_hysteresis(self):
    for _ in range(30):
      self.step(model=model(curve=True))
    self.assertEqual(self.selector.reason, 'curve')
    self.assertTrue(self.step())  # One clear frame must not flicker the mode.
    for _ in range(60):
      self.step()
    self.assertEqual(self.selector.reason, 'cruise')

  def test_current_curve_is_detected_even_with_lead(self):
    lead = NS(present=True, dRel=25., vLead=15., aLeadK=0.)
    for _ in range(30):
      self.step(curvature=.004, lead=lead)
    self.assertEqual(self.selector.reason, 'curve')

  def test_speed_and_turn_signal_alone_do_not_enable_experimental(self):
    cs = NS(vEgo=4., standstill=False, leftBlinker=True, rightBlinker=False)
    for _ in range(60):
      self.assertFalse(self.step(car_state=cs, model=model(speed=4.)))

  def test_two_fresh_clear_frames_release_cached_stop_without_filter_decay(self):
    cs = NS(vEgo=0., standstill=True, leftBlinker=False, rightBlinker=False)
    for _ in range(60):
      self.assertTrue(self.step(car_state=cs, model=model(speed=0., stop=True)))
    moving = model(speed=0., end_speed=6., accel=.452)
    self.assertTrue(self.step(car_state=cs, model=moving))
    # Duplicate messages at the 100 Hz host rate cannot count as new evidence.
    for _ in range(4):
      self.assertTrue(self.selector.update(model_time=self.frame * 50_000_000,
                                          **(self.inputs | {'car_state': cs, 'model': moving})))
    self.assertFalse(self.step(car_state=cs, model=moving))
    self.assertEqual(self.selector.reason, 'cruise')
    for _ in range(40):
      self.assertFalse(self.step(car_state=cs, model=moving))

  def test_new_stop_or_invalid_frame_resets_release_confirmation(self):
    cs = NS(vEgo=0., standstill=True, leftBlinker=False, rightBlinker=False)
    stop = model(speed=0., stop=True)
    go = model(speed=0., end_speed=6., accel=.452)
    self.step(car_state=cs, model=stop)
    self.step(car_state=cs, model=go)
    self.assertTrue(self.step(car_state=cs, model=go, valid=False))
    self.assertTrue(self.step(car_state=cs, model=go))
    self.assertTrue(self.step(car_state=cs, model=stop))
    self.assertTrue(self.step(car_state=cs, model=go))
    self.assertFalse(self.step(car_state=cs, model=go))

  def test_starting_to_roll_does_not_reintroduce_filtered_release_delay(self):
    stopped = NS(vEgo=0., standstill=True, leftBlinker=False, rightBlinker=False)
    rolling = NS(vEgo=.2, standstill=False, leftBlinker=False, rightBlinker=False)
    for _ in range(60):
      self.step(car_state=stopped, model=model(speed=0., stop=True))
    go = model(speed=0., end_speed=6., accel=.452)
    self.assertTrue(self.step(car_state=stopped, model=go))
    self.assertFalse(self.step(car_state=rolling, model=go))

  def test_stationary_trajectory_does_not_release_on_acceleration_alone(self):
    cs = NS(vEgo=0., standstill=True, leftBlinker=False, rightBlinker=False)
    self.step(car_state=cs, model=model(speed=0., stop=True))
    for _ in range(40):
      self.assertTrue(self.step(car_state=cs, model=model(speed=0., accel=.1)))

  def test_stale_missing_and_nonfinite_data_never_select_clear_cruise(self):
    bad = copy.deepcopy(self.inputs['model'])
    bad.velocity.x[4] = float('nan')
    short = copy.deepcopy(self.inputs['model'])
    short.position.y = []
    for overrides in ({'valid': False}, {'model_age': .251}, {'model': bad}, {'model': short},
                      {'curvature': float('inf')}, {'model_age': -1.}):
      with self.subTest(overrides=tuple(overrides)):
        self.assertTrue(self.step(**overrides))
        self.assertEqual(self.selector.reason, 'invalid')

  def test_master_off_full_experimental_and_disengagement(self):
    self.step(model=model(stop=True))
    self.assertFalse(self.step(requested=False))
    self.assertFalse(self.step(enabled=False))
    self.assertTrue(self.step(conditional=False))
    self.assertFalse(self.step(requested=False, conditional=False))
    self.assertFalse(self.step())


if __name__ == '__main__':
  unittest.main()
