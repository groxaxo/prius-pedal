"""Exercise the real host methods without native sockets or realtime processes."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

from openpilot.selfdrive.controls.lib.conditional_experimental_mode import ConditionalExperimentalMode
from openpilot.selfdrive.controls.tests.test_conditional_experimental import model


class TestConditionalHost(unittest.TestCase):
  def setUp(self):
    source = Path(__file__).resolve().parents[3] / 'openpilot/selfdrive/selfdrived/selfdrived.py'
    tree = ast.parse(source.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SelfdriveD')
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in ('update_experimental_mode', 'params_thread')]
    self.events = []
    namespace = {'time': NS(monotonic=lambda: 100., sleep=lambda _: None),
                 'cloudlog': NS(event=lambda *args, **kwargs: self.events.append((args, kwargs)))}
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(source), 'exec'), namespace)
    self.update = namespace['update_experimental_mode']
    self.read_params = namespace['params_thread']

    class SubMaster(dict):
      logMonoTime = {'modelV2': 1}
      recv_time = {'modelV2': 100.}

      def all_checks(self, services):
        return True

    self.host = NS(experimental_mode_requested=True, conditional_experimental_requested=True,
                   conditional_param_available=True,
                   conditional_experimental_available=True, enabled=True, experimental_mode=False,
                   conditional_experimental=ConditionalExperimentalMode(), experimental_mode_status=None,
                   sm=SubMaster(modelV2=model(), radarState=NS(leadOne=NS(present=False)),
                                controlsState=NS(curvature=0.), vehicleParameters=NS(roll=0.)))
    self.car_state = NS(vEgo=20., standstill=False, leftBlinker=False, rightBlinker=False, canValid=True)

  def test_requested_and_effective_modes_are_distinct(self):
    self.update(self.host, self.car_state)
    self.assertTrue(self.host.experimental_mode_requested)
    self.assertFalse(self.host.experimental_mode)
    self.assertEqual(self.events[-1][1]['reason'], 'cruise')
    self.assertTrue(self.events[-1][1]['armed'])
    self.update(self.host, self.car_state)
    self.assertEqual(len(self.events), 1)

  def test_params_thread_does_not_overwrite_effective_mode(self):
    self.host.params = NS(get_bool=lambda _: True, get=lambda *args, **kwargs: 1)
    self.host.CP = NS(openpilotLongitudinalControl=True)
    checks = iter((False, True))
    self.read_params(self.host, NS(is_set=lambda: next(checks)))
    self.assertTrue(self.host.experimental_mode_requested)
    self.assertTrue(self.host.conditional_experimental_requested)
    self.assertFalse(self.host.experimental_mode)

  def test_unsupported_platform_retains_full_experimental(self):
    self.host.conditional_experimental_available = False
    self.update(self.host, self.car_state)
    self.assertTrue(self.host.experimental_mode)
    self.assertEqual(self.events[-1][1]['reason'], 'full')

  def test_disengagement_and_master_off_clear_effective_conditional_mode(self):
    self.host.sm['modelV2'] = model(stop=True)
    self.update(self.host, self.car_state)
    self.assertTrue(self.host.experimental_mode)
    self.host.enabled = False
    self.update(self.host, self.car_state)
    self.assertFalse(self.host.experimental_mode)
    self.host.enabled = True
    self.host.experimental_mode_requested = False
    self.update(self.host, self.car_state)
    self.assertFalse(self.host.experimental_mode)

  def test_stale_data_cannot_switch_to_clear_cruise(self):
    self.host.sm.recv_time = {'modelV2': 99.7}
    self.update(self.host, self.car_state)
    self.assertTrue(self.host.experimental_mode)
    self.assertEqual(self.events[-1][1]['reason'], 'invalid')

  def test_source_update_with_old_native_parameter_library_keeps_legacy_mode(self):
    self.host.conditional_param_available = False
    def read_bool(key):
      if key == 'ConditionalExperimentalMode':
        raise AssertionError('Old native library cannot read the new key')
      return True
    self.host.params = NS(get_bool=read_bool, get=lambda *args, **kwargs: 1)
    self.host.CP = NS(openpilotLongitudinalControl=True)
    checks = iter((False, True))
    self.read_params(self.host, NS(is_set=lambda: next(checks)))
    self.update(self.host, self.car_state)
    self.assertTrue(self.host.experimental_mode)
    self.assertEqual(self.events[-1][1]['reason'], 'full')


if __name__ == '__main__':
  unittest.main()
