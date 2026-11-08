# Conditional Experimental Mode: stops and curves

This Prius/Pedal option uses normal cruise and lead planning to approach Toyota's internal set-speed target, and selects Experimental model planning for predicted stops and curves. It addresses recorded cases where full Experimental selected near-zero acceleration well below the cruise setting. It does not increase acceleration limits or Pedal force.

## Controls and availability

The option is available only with the supported Toyota Prius Pedal flag and openpilot longitudinal control. Other platforms retain their existing behavior. Its persistent `ConditionalExperimentalMode` Boolean defaults to false; existing installations keep their mode until the option is deliberately enabled. The new key requires rebuilding the native parameter library before enabling it on a device. A source update with the older native library keeps legacy behavior and disables the new setting instead of failing on an unknown key.

| Experimental master | Conditional option | Planning policy |
| --- | --- | --- |
| Off | Either | Normal Chill/cruise and lead planning |
| On | Off | Original full Experimental; set speed is a ceiling |
| On | On | Cruise/lead normally; Experimental for stops and curves |

Change the conditional policy in Settings while disengaged. The existing Experimental confirmation remains required. The on-road button toggles the saved master, including when automatic mode currently selects cruise. Its **AUTO** badge indicates the policy is armed; the icon independently indicates whether Experimental is actually active. **AUTO OFF** means the conditional preference is saved but its master is off. The offroad card labels the enabled policy as automatic.

## Selection and FrogPilot reference

The implementation adapts [FrogPilot's selector](https://github.com/FrogAi/FrogPilot/blob/a22c476734514e36b196168cd39743b74f30dc01/frogpilot/controls/lib/conditional_experimental_mode.py), [planner lead relevance](https://github.com/FrogAi/FrogPilot/blob/a22c476734514e36b196168cd39743b74f30dc01/frogpilot/controls/frogpilot_planner.py), and [curve geometry helpers](https://github.com/FrogAi/FrogPilot/blob/a22c476734514e36b196168cd39743b74f30dc01/frogpilot/common/frogpilot_utilities.py), pinned at `a22c476734514e36b196168cd39743b74f30dc01`. MIT attribution is retained. This is a focused port to openpilot 0.11.2; it does not import FrogPilot's navigation, model selection, low-speed, turn-signal or slower-lead mode triggers, custom following profiles, lateral tuning, or Always On Lateral.

- Stop prediction checks the model's first eight seconds, using FrogPilot's 70% approach / 75% release speed fractions, short-term stopping velocities at 0.5 and 1.5 seconds, and a 1.5-second filter. Lead relevance uses distance, speed, deceleration and the model horizon, rather than treating every visible lead as relevant. Current model `shouldStop` requests select Experimental immediately and take priority over curves.
- Curve detection uses planned yaw rate divided by velocity, predicted path geometry and the current measured curvature. It retains FrogPilot's 0.6/0.4 m/s² curve-ahead hysteresis, 0.9-second filter, and 1.3 m/s² current-curve threshold. Its fixed Standard 2 m/s² geometry profile only helps identify an upcoming curve; it does not modify steering parameters or implement a separate curve-speed controller.
- The selector runs once per distinct model timestamp. A background preference read cannot overwrite its effective mode. Transition logs record `conditional_experimental_mode`, armed/active state, reason (`off`, `full`, `cruise`, `stop`, `curve`, `invalid`), and model timestamp. No Cereal schema change is required.
- Missing, nonfinite, malformed or stale model data does not declare a clear road: it selects the conservative Experimental fallback and cancels release confirmation. Existing data-validity and disengagement checks still apply. A model older than 250 ms is rejected even if a repeated host iteration sees the same timestamp.

## Stop holding and quicker response

The existing PCM manual-resume repair and bounded **0.12 Pedal assist** are retained. A direct stop request is never cleared by an elapsed timer. At standstill, an already detected stop can leave the cached stop mode after **two distinct valid model frames** have `shouldStop=false`, a cleared short-term stopping prediction, and finite positive desired acceleration. A new stop or invalid frame resets that confirmation. This avoids waiting for the stop-approach filter to decay; the selector adds at most two nominal 20 Hz periods (100 ms) after those conditions hold, not a guarantee of physical move-off time.

The actual unchanged longitudinal planner continues taking the minimum of current lead/cruise candidates and, while selected, the model. Its current lead stop remains authoritative after a mode switch. The selector never waits for the previous combined plan's stop flag to clear, avoiding a circular stop-release dependency. It does not send timed RES presses, force positive acceleration, infer a green light from a timeout, or engage controls automatically. Driver pedals, cancellation, gear, CAN/Pedal/SDSU health and launch termination when moving retain their existing gates.

## Speed and lateral settings

Toyota's physical speed target and display mapping are retained. In the reviewed interval Toyota showed 111 km/h selected while reporting a 105 km/h internal target. This change addresses the larger model-induced under-speed; it does not add an offset to the commanded target or promise identical displayed numbers. A lead, curve, stop or ordinary acceleration limit can legitimately keep speed below the target.

The [original official lateral parameters and steering-output comparison](PRIUS_LATERAL_VERIFICATION.md) remain the baseline. No lateral source, steering limit, calibration or Toyota controller source is changed by this feature. The existing firmware/source compatibility check must pass; a host-only selector does not require flashing a different Panda policy.

## Validation and deployment status

Local qualification passed 23 selector/host/button tests, 28 Toyota tests, 49 CAN tests, and the full safety suite (3,276 run, including 398 inherited skips). Private offline selector replay covered five completed log segments. Of 180 model frames in the recorded under-speed interval, 165 selected cruise and 15 selected a curve; the 590-second snapshot selected cruise rather than the near-zero model acceleration. Raw logs and identifying route data are not published. Selector replay is distinct from actual-planner replay and physical acceptance.

CI includes a native Linux ARM64 offline integration job using the actual longitudinal planner, controller, Toyota parser and CAN packer. Its repeated-stop tests cover both SDSU formats, unchanged launch payloads, two-frame selector release, and current lead-stop authority. No test transmits CAN. The normal Toyota/CAN/safety/coverage/firmware checks remain required.

At preparation, the saved S10e access route was offline; no comma source, settings, native library or firmware was changed. Deployment requires a staged native parameter rebuild, passing full-runtime tests, recovery and settings backup, and fresh Park/zero-speed/disengaged telemetry or ignition-off NOOUTPUT. After installation, verify the commit, native key, saved preferences, firmware signature, services and inactive parked commands, then reboot and verify again. Record those results separately from owner-driven speed recovery, stopping, physical restarts and traffic-light recognition. Traffic-light perception remains experimental.
