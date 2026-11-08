"""FrogPilot-derived stop/curve selection, adapted to openpilot 0.11.2.

Reference: FrogAi/FrogPilot a22c476734514e36b196168cd39743b74f30dc01,
conditional_experimental_mode.py, frogpilot_planner.py and frogpilot_utilities.py.
Original MIT notices are retained in LICENSE. This selector never commands actuation.
"""
import math

import numpy as np

from openpilot.common.filter_simple import FirstOrderFilter

THRESHOLD = 1 - 1 / math.e
MODEL_DT = 0.05
MAX_MODEL_AGE = 0.25
STOP_DISTANCE = 6.0
CRUISING_SPEED = 5.0
STOPPING_SPEED = 1.0
STOP_TIME = 8.0
PLANNER_TIME = 10.0
CURVE_AHEAD_ENTER = 0.6
CURVE_AHEAD_EXIT = 0.4
MINIMUM_LATERAL_ACCELERATION = 1.3
DEFAULT_LATERAL_ACCELERATION = 2.0


class ConditionalExperimentalMode:
  def __init__(self, dt=MODEL_DT):
    self.stop_filter = FirstOrderFilter(0., 1.5, dt)
    self.curve_filter = FirstOrderFilter(0., 0.9, dt)
    self.reset()

  def reset(self):
    self.experimental_mode = False
    self.reason = 'off'
    self.stop_detected = False
    self.standstill_stop = False
    self.curve_detected = False
    self.curve_ahead = False
    self.lead_relevant = False
    self.release_frames = 0
    self.last_model_time = 0
    self.stop_filter.x = self.curve_filter.x = 0.

  def _invalid(self, model_time):
    # Unknown geometry is never evidence to switch to set-speed acceleration.
    # Existing host/model validity checks still govern engagement and shutdown.
    self.last_model_time = max(self.last_model_time, model_time)
    self.release_frames = 0
    self.experimental_mode = True
    self.reason = 'invalid'
    return self.experimental_mode

  @staticmethod
  def _trajectory(model):
    arrays = [np.asarray(values, dtype=float) for values in
              (model.velocity.t, model.velocity.x, model.position.x, model.position.y, model.orientationRate.z)]
    if any(a.shape != (33,) or not np.isfinite(a).all() for a in arrays):
      raise ValueError('Incomplete or nonfinite model trajectory')
    times = arrays[0]
    if times[0] > 0 or times[-1] < STOP_TIME or np.any(np.diff(times) <= 0):
      raise ValueError('Invalid model time horizon')
    return arrays

  @staticmethod
  def _lead_relevant(lead, standstill, v_ego, model_length):
    if not lead.present:
      return False
    if not all(math.isfinite(x) for x in (lead.dRel, lead.vLead, lead.aLeadK)) or lead.dRel < 0:
      raise ValueError('Invalid lead data')
    following_speed = max(v_ego, CRUISING_SPEED)
    lead_speed = lead.vLead + min(lead.aLeadK, 0) * PLANNER_TIME / 2
    return (lead.dRel < (0 if standstill else model_length) + STOP_DISTANCE + 4 and
            lead.dRel < STOP_DISTANCE + following_speed * 3 + max(following_speed - lead_speed, 0) * PLANNER_TIME)

  def _update_curve(self, v_ego, velocities, position_x, position_y, yaw_rate, curvature, roll, blinker):
    # FrogPilot's geometry and curve-ahead hysteresis, using its Standard 2 m/s²
    # longitudinal curve profile. No lateral-controller setting is modified.
    road_curvature = np.where(velocities >= 2, yaw_rate / np.maximum(velocities, 1), 0)
    distance = np.concatenate(([0], np.cumsum(np.hypot(np.diff(position_x), np.diff(position_y)))))
    time_to_point = distance / max(v_ego, CRUISING_SPEED)
    lateral_acceleration = np.maximum(DEFAULT_LATERAL_ACCELERATION + np.sign(road_curvature) * roll * 9.81, 0)
    curve_speed = np.maximum(np.sqrt(lateral_acceleration / np.maximum(np.abs(road_curvature), 1e-6)), CRUISING_SPEED)
    deceleration = (v_ego - curve_speed) / np.maximum(time_to_point, 1)
    index = np.argmax(deceleration) if deceleration.max() > 0 else np.argmin(curve_speed)
    peak = v_ego**2 * np.abs(road_curvature).max()
    if self.curve_ahead or self.curve_detected:
      self.curve_ahead = bool(peak > CURVE_AHEAD_EXIT)
    else:
      self.curve_ahead = bool(peak > CURVE_AHEAD_ENTER and time_to_point[index] > 1)
    self.curve_ahead &= v_ego > CRUISING_SPEED and not blinker
    self.curve_filter.update(self.curve_ahead or abs(v_ego**2 * curvature) >= MINIMUM_LATERAL_ACCELERATION)
    threshold = 1 - THRESHOLD if self.curve_detected else THRESHOLD
    self.curve_detected = bool(self.curve_filter.x >= threshold and v_ego > CRUISING_SPEED)

  def update(self, *, requested, conditional, enabled, valid, model_time, model_age,
             car_state, model, lead, curvature, roll):
    if not requested or not conditional or not enabled:
      self.reset()
      # Full Experimental retains the official master-switch semantics.
      self.experimental_mode = bool(requested and not conditional)
      self.reason = 'full' if self.experimental_mode else 'off'
      return self.experimental_mode

    if not valid or not math.isfinite(model_age) or not 0 <= model_age <= MAX_MODEL_AGE or model_time <= 0:
      return self._invalid(model_time)
    if model_time < self.last_model_time:
      return self._invalid(model_time)
    if model_time == self.last_model_time:
      return self.experimental_mode

    try:
      times, velocities, position_x, position_y, yaw_rate = self._trajectory(model)
      v_ego = float(car_state.vEgo)
      desired_accel = float(model.action.desiredAcceleration)
      if not all(math.isfinite(x) for x in (v_ego, desired_accel, curvature, roll)) or v_ego < 0:
        raise ValueError('Nonfinite vehicle/model state')
      self.lead_relevant = self._lead_relevant(lead, car_state.standstill, v_ego, position_x[-1])
    except (AttributeError, IndexError, TypeError, ValueError):
      return self._invalid(model_time)

    self.last_model_time = model_time
    self._update_curve(v_ego, velocities, position_x, position_y, yaw_rate, curvature, roll,
                       car_state.leftBlinker or car_state.rightBlinker)

    upcoming_velocities = np.append(velocities[times < STOP_TIME], np.interp(STOP_TIME, times, velocities))
    slowdown_fraction = 0.75 if self.stop_detected else 0.70
    model_slowing = upcoming_velocities.min() <= slowdown_fraction * v_ego
    model_stopping = np.interp([0.5, 1.5], times, velocities).max() < STOPPING_SPEED
    stop_requested = bool(model.action.shouldStop)
    stop_signal = bool((model_slowing or model_stopping) and not self.lead_relevant)
    # A zero initial velocity at standstill alone is not a new stop prediction.
    if car_state.standstill and not model_stopping and not stop_requested:
      stop_signal = False
    self.stop_filter.update(stop_signal)

    if stop_requested or (car_state.standstill and model_stopping and not self.lead_relevant):
      self.stop_detected = True
      self.standstill_stop |= car_state.standstill
      self.release_frames = 0
    elif self.stop_detected and (car_state.standstill or self.standstill_stop):
      # Unlike a decaying approach filter, two distinct, valid go predictions
      # can promptly release a cached stop. The current lead MPC remains in the
      # actual planner's minimum/stop arbitration; never gate on its old combined plan.
      permits_movement = not model_stopping and desired_accel > 0
      self.release_frames = self.release_frames + 1 if permits_movement else 0
      if self.release_frames >= 2:
        self.stop_detected = False
        self.standstill_stop = False
        self.stop_filter.x = 0.
        self.release_frames = 0
    else:
      self.release_frames = 0
      self.stop_detected = bool(self.stop_filter.x >= THRESHOLD or (self.stop_detected and stop_signal))
      if not self.stop_detected:
        self.standstill_stop = False

    self.experimental_mode = self.stop_detected or self.curve_detected
    self.reason = 'stop' if self.stop_detected else 'curve' if self.curve_detected else 'cruise'
    return self.experimental_mode
