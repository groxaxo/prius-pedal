"""Exercise the real button handler headlessly, without opening a camera or publishing CAN."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


class TestExperimentalButton(unittest.TestCase):
  def make_button(self, requested, active, conditional):
    source = Path(__file__).resolve().parents[3] / 'openpilot/selfdrive/ui/onroad/exp_button.py'
    tree = ast.parse(source.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ExpButton')
    node.body = [n for n in node.body if isinstance(n, ast.FunctionDef) and n.name in
                 ('_handle_mouse_release', '_is_toggle_allowed', '_held_or_actual_mode')]

    class Widget:
      def _handle_mouse_release(self, event):
        pass

    values = {'ExperimentalMode': requested, 'ConditionalExperimentalMode': conditional, 'ExperimentalModeConfirmed': True}
    params = SimpleNamespace(get_bool=lambda key: values.get(key, False), put_bool=lambda key, value: values.update({key: value}))
    namespace = {'Widget': Widget, 'time': SimpleNamespace(monotonic=lambda: 1.0),
                 'ui_state': SimpleNamespace(has_longitudinal_control=True)}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
    button = namespace['ExpButton']()
    button._params = params
    button._experimental_mode = active
    button._conditional_mode = conditional
    button._held_mode = button._hold_end_time = None
    button._hold_duration = 2.0
    return button, values

  def test_tap_disables_requested_mode_while_auto_is_cruising(self):
    button, values = self.make_button(requested=True, active=False, conditional=True)
    button._handle_mouse_release(None)
    self.assertFalse(values['ExperimentalMode'])

  def test_tap_arms_conditional_mode_without_faking_active_experimental(self):
    button, values = self.make_button(requested=False, active=False, conditional=True)
    button._handle_mouse_release(None)
    self.assertTrue(values['ExperimentalMode'])
    self.assertFalse(button._held_or_actual_mode())

  def test_full_experimental_still_toggles(self):
    button, values = self.make_button(requested=True, active=True, conditional=False)
    button._handle_mouse_release(None)
    self.assertFalse(values['ExperimentalMode'])


if __name__ == '__main__':
  unittest.main()
