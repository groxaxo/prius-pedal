# Official Prius lateral configuration and repeated stop checks

The owner's requested lateral configuration is the original official **openpilot 0.11.2 `release-tizi`**, pinned at [`f7db927c728bab57bb1263e05465766a8f28fc9d`](https://github.com/commaai/openpilot/tree/f7db927c728bab57bb1263e05465766a8f28fc9d). The installed Prius lateral configuration matches that release. The Pedal/SDSU additions retain the official steering controller, calibration data and limits.

## Source and live configuration comparison

The source comparison found byte-identical official versions of `controlsd.py`, the lateral-controller base and torque controller, `drive_helpers.py`, the common vehicle interface, steering-limit helpers, shared Panda lateral checks and all three torque-data files. Toyota's lateral parameter selection and steering-command path retain the official behavior. The custom Toyota changes select and implement longitudinal Pedal/SDSU control.

An isolated process on the comma loaded the pinned official Toyota interface and compared its parameter result, using the detected car's firmware inputs, with `CarParamsPersistent`. All 13 compared lateral/dynamics fields matched exactly, including the complete torque-tuning structure. The installed steering limits and EPS factor matched the official values as well.

Representative values for the detected EPS configuration:

| Parameter | Official and installed value |
| --- | --- |
| Steering controller | Torque |
| Steering ratio | 15.74 |
| Steering actuator delay | 0.25 s |
| Steering-angle deadzone | 0.2 degrees |
| Steering-limit alert timer | 0.4 s |
| Initial lateral-acceleration factor | 1.6 |
| Initial friction coefficient | 0.151515 |
| EPS scaling factor | 66 |
| Maximum steering command | 1500 native units |
| Steering-command change, up/down | 15 / 25 native units per control frame |

The 0.25-second delay and 0.2-degree deadzone are the official EPS-firmware-dependent selection, rather than a custom tuning adjustment. The official branch also contains a 0.12-second/zero-deadzone configuration for its matching EPS firmware. The new regression covers both selections, the no-EPS-information default, and both SDSU formats.

The official live calibration/adaptation code remains part of this configuration. Initial torque parameters above are not a replacement for its valid learned estimates. Steering faults, driver overrides, command limits and normal engagement rules follow the official code. Independent steering with cruise disengaged has not been added.

## Steering-command comparison

The installed and pinned official Toyota controllers were run in a separate process on identical synthetic inputs for **24 seconds / 2,400 control frames**. Inputs included changing requested torque, EPS feedback, lateral activation, driver steering override and the high-steering-rate protection condition. Every steering CAN frame matched byte for byte. The generated frames were inspected in memory; **no CAN messages were transmitted**. This qualifies code/output parity, not physical lane-centering performance.

## Repeated stop-and-go qualification

The installed RES-state correction remains in place. A new full-runtime test exercises **five consecutive stop/hold/restart/move cycles for each SDSU format**, using the actual CAN parser, longitudinal controller, Toyota controller and event logic:

- The car enters a stop with PCM state 8, then reports its stock state-7 hold.
- A planner stop request retains stopping/braking and keeps Pedal assist inactive, even with a positive acceleration target.
- A planner release enters normal longitudinal control, emits the bounded 50 Hz launch assist and produces no `resumeRequired` event, with no RES-button or driver-pedal input.
- Pedal assist becomes inactive once wheel speed indicates movement, and the next stop/restart follows the same sequence.

All ten synthetic restarts passed on the comma. The existing full-runtime checks also cover driver braking and disengagement. Run the complete offline qualification in a full openpilot runtime:

```sh
PYTHONPATH="$PWD:$PWD/opendbc_repo" python -m unittest \
  tools.prius_pedal.test_stop_and_go \
  tools.prius_pedal.tests.test_repeated_stops
```

The Toyota suite now runs **28 tests**, including the official-lateral regression. The firmware/source compatibility check still passes: this follow-up adds tests and documentation while the deployed control and safety inputs remain compatible with `DEV-f69d3091-RELEASE`.

## Physical acceptance boundary

At the live check the Prius was in Park at zero speed, with valid CAN, no ACC fault, Experimental Mode enabled and controls disengaged. The 70 completed post-install route segments inspected were all stationary, with no cruise engagement or RES warning. They contain no physical stop-and-go opportunity.

The reproduced manual-RES software deadlock is corrected, and repeated offline control-chain qualification passes. Physical launch calibration, braking/restart response, lane-centering quality and red/green-light recognition still require supervised vehicle acceptance. Neither simulated restarts nor stationary telemetry establishes those results. Raw route logs and identifying data are private.
