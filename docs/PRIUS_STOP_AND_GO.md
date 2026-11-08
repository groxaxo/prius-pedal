# Prius stop-and-go and Experimental Mode follow-up

This follow-up addresses a reproduced manual-resume deadlock in the Prius/Pedal port. Software qualification, installation, parked verification and physical driving acceptance are separate steps. Publishing this change does not establish successful physical automatic restarts or traffic-light recognition.

## Recorded failure and correction

A drive recorded on `52a0ea2` showed the lead moving away while the Prius remained stopped. The planner had released its stop request and requested **+0.452 m/s²**, but the longitudinal controller remained in `stopping` and requested **−1.688 m/s²**. Toyota's PCM still reported its stock RES-button hold, the screen displayed `resumeRequired`, and no Pedal launch command was active. The driver subsequently used the accelerator.

The port had retained the stock manual-resume requirement even though it had selected the Pedal/SDSU path. This prevented a positive actuator request from reaching the existing launch assist.

FrogPilot explicitly ignores cruise standstill for gas-interceptor vehicles in its [longitudinal state machine](https://github.com/FrogAi/FrogPilot/blob/a22c476734514e36b196168cd39743b74f30dc01/selfdrive/controls/lib/longcontrol.py), and excludes those vehicles from the [Toyota resume-required event](https://github.com/FrogAi/FrogPilot/blob/a22c476734514e36b196168cd39743b74f30dc01/selfdrive/car/toyota/interface.py). This port implements the same behavior at the Toyota state boundary: PCM state 7 does not become a **manual-resume requirement** when `PRIUS_PEDAL` is selected. Wheel standstill and the controller's raw `pcm_acc_status` remain available. Other Toyota configurations retain their existing behavior.

The resulting path is:

1. The planner requests a stop: normal braking/holding continues and launch assist remains inactive.
2. The planner releases the stop request and requests positive acceleration: the longitudinal controller can leave `stopping` without a RES-button press.
3. Existing launch-assist checks require active engagement, Drive, a stationary vehicle, healthy CAN/Pedal/SDSU, no driver pedal input or cancel, and a finite positive acceleration request.
4. The bounded 0.12 Pedal assist ends when the wheels move. Acceleration and braking continue through Toyota ACC.

This is a controller-state correction, not an alert-only suppression. It does not add automatic engagement, timed RES-button presses, a traffic-light detector, or a command that overrides the planner's stop decision. Existing Panda safety checks and limits remain enforced.

## Why Experimental Mode can still feel slow

Three later one-minute logs confirm the installed gain correction was active. In a model-limited, no-lead subset, the median selected speed was **55 km/h**, measured speed **32.8 km/h**, model/requested acceleration **+0.133 m/s²**, and measured acceleration **+0.151 m/s²**. In another subset, the model requested **−0.572 m/s²** and measured acceleration was **−0.560 m/s²** at about **42 km/h**. The controller was generally following the model's low or negative request. These are aggregate diagnostic samples, not a controlled comparison of driving models.

Calibration was valid and model frame-drop percentage was zero in the inspected segments. A separate live sample was limited by a slower lead about 42 m ahead. This evidence does not support increasing the feedback gain or forcing the car toward the cruise setting past model/lead limits.

Experimental Mode uses the set speed as a ceiling and may choose a lower speed for the scene. It may attempt stops and restarts at traffic lights, but recognition and timing remain experimental. The stop-and-go correction allows a restart **when the planner releases the stop**; it cannot guarantee recognition of every red or green light. The driver must supervise and intervene when needed. See [comma's Experimental Mode explanation](https://blog.comma.ai/090release/#experimental-mode).

The reported low chosen speed remains a model-behavior limitation; this patch does not claim to solve it. Changing that policy requires a separate reviewed planner/model change and physical acceptance, not a hidden acceleration override.

## Regression checks

- The CAN-parser regression fails on the previous code for both four-byte and eight-byte SDSU configurations. It verifies wheel standstill and raw PCM status remain intact, and a Prius without the required Pedal retains its manual-resume behavior.
- `tools/prius_pedal/test_stop_and_go.py` uses the actual CAN parser, longitudinal controller, Toyota controller and alert logic with synthetic messages. It checks stop holding, positive planner release without RES, bounded Pedal activation, assist termination when moving, driver braking and disengagement. It never transmits CAN.
- Local Toyota suite: **27 tests passed**. CAN suite: **49 passed**. Full safety suite: **3,276 run, 398 inherited skips, no failures**. The public workflow independently repeats its parser, CAN, safety, coverage and firmware checks.

The full integration test requires the complete openpilot runtime, including native dependencies. Run it on an inactive checkout:

```sh
PYTHONPATH="$PWD:$PWD/opendbc_repo" python -m unittest tools.prius_pedal.test_stop_and_go
```

Firmware provenance is recorded in `tools/prius_pedal/bundled_firmware.json`. The bundle is rebuilt to bind it to the updated source; this correction does not change the C safety policy. Deployment must preserve recovery and native artifacts and must wait for fresh Park/zero-speed/disengaged telemetry. Physical stop-and-go and traffic-light acceptance remain outstanding after software tests alone.

Raw drive logs, camera images and identifying route data are private and are not included in this repository.
