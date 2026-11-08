# Prius Pedal Lab

This is a development candidate for the TSS-P Toyota Prius platform with a physical comma Pedal and Smart DSU. It is based on the exact official `release-tizi` revision installed on the target comma 3X: **openpilot 0.11.2, `f7db927c728bab57bb1263e05465766a8f28fc9d`**. Its AGNOS requirement remains **19.9**.

`main` is this fork's single development and default branch and contains the Pedal changes. The frozen `upstream-release-tizi-0.11.2` tag preserves the exact unchanged official baseline. The `archive/dragonpilot-pre-build` tag preserves the inherited DragonPilot branch separately. The project uses its own name because it modifies the safety model; see the upstream [fork requirements](SAFETY.md#forks-of-openpilot).

For vehicle compatibility, hardware requirements, and current readiness, start with the [2016 Prius owner guide](PRIUS_2016_OWNER_GUIDE.md). The [changelog](../CHANGELOG.md) records the port and branch integration.

## What FrogPilot uses for a 2016 Prius

A 2016 Prius with Toyota Safety Sense P maps to **`CAR.TOYOTA_PRIUS`**, not `TOYOTA_PRIUS_V` or the later `TOYOTA_PRIUS_TSS2`. The fingerprint groups several TSS-P Prius/Prime model years; the software does not independently prove the model year from the label “2016”. The existing firmware fingerprint database and steering configuration are retained.

| Part | FrogPilot release source | Location in this port |
| --- | --- | --- |
| Vehicle/ECU identification | `selfdrive/car/toyota/values.py`, `fingerprints.py` | `opendbc_repo/opendbc/car/toyota/values.py`, existing `fingerprints.py` |
| Pedal + SDSU detection and longitudinal selection | `selfdrive/car/toyota/interface.py` | `opendbc_repo/opendbc/car/toyota/interface.py` |
| Physical pedal tracks and follow-distance button | `selfdrive/car/toyota/carstate.py` | `opendbc_repo/opendbc/car/toyota/carstate.py` |
| Prius stop/start assist and standstill request | `selfdrive/car/toyota/carcontroller.py` | `opendbc_repo/opendbc/car/toyota/carcontroller.py` |
| Pedal CAN encoder and CRC | `selfdrive/car/__init__.py` | `opendbc_repo/opendbc/car/toyota/toyotacan.py`, `opendbc_repo/opendbc/can/dbc.py` |
| CAN definitions | `opendbc/toyota_nodsu_pt_generated.dbc` | Dedicated `toyota_prius_pedal_pt_generated` and `toyota_prius_pedal_sdsu4_pt_generated` DBCs for eight-byte and four-byte SDSU status |
| Firmware enforcement | Source is available in FrogPilot's development tree under `opendbc_repo/opendbc/safety/` | `opendbc_repo/opendbc/safety/modes/toyota.h` and its tests |

The production FrogPilot reference is [`8955eaae9574c2a9723f401bdbaf120bf021d08a`](https://github.com/FrogAi/FrogPilot/tree/8955eaae9574c2a9723f401bdbaf120bf021d08a). Its current development safety implementation was also inspected at [`b5c24be2ff6fa2aee5b058d3131382a0e8395309`](https://github.com/FrogAi/FrogPilot/tree/b5c24be2ff6fa2aee5b058d3131382a0e8395309). FrogPilot is MIT licensed, copyright (c) 2018 Comma.ai, Inc.; the upstream MIT license is retained.

## Implemented behavior

### Four-byte SDSU takeover status

This port initially treated every nonzero `SDSU.STATE` as an ACC failure. That was an extra interlock introduced by the port, not FrogPilot's behavior. It caused a false Cruise Fault with the observed legacy four-byte protocol. The temporary stock-ACC recovery cleared the warning but disabled the requested openpilot longitudinal control and Experimental Mode.

The current comparison is pinned to FrogPilot production [`a22c476734514e36b196168cd39743b74f30dc01`](https://github.com/FrogAi/FrogPilot/tree/a22c476734514e36b196168cd39743b74f30dc01) and development [`2a34bc4697dc92e2071546edc662b4f228a90112`](https://github.com/FrogAi/FrogPilot/tree/2a34bc4697dc92e2071546edc662b4f228a90112). Production selects openpilot longitudinal control on Smart DSU detection, uses standard Toyota `ACC_CONTROL` (`0x343`), and reads the SDSU follow-distance button without converting its status nibble into `accFaulted`. Development likewise retains native Toyota ACC fault reporting and does not add an SDSU status quality gate.

In [legacy reference firmware](https://github.com/RetroPilot/ocelot/blob/94efc67349227b7a4dc410c585c9dee507a5960e/firmware/smart_dsu/main.c), receiving openpilot's `0x343` suppresses forwarding the stock DSU's ACC frame. That branch also skips refreshing the stock-ACC watchdog, so it reports `STATE 5` after 500 ms even with valid incoming frames. The status does not gate forwarding or openpilot's actuator commands. The captured vehicle startup showed this exact 500 ms transition, healthy Pedal state, no native ACC fault and acknowledged controller output. This matches the reference protocol behavior; it does not identify the installed board or firmware version.

The compatibility correction accepts status **0 or 5 only for the four-byte SDSU path** in both the host and Panda, while preserving the raw status in CAN data. All other SDSU statuses, every nonzero Pedal status, native Toyota ACC faults, low-speed lockout, invalid checksums/counters and stale streams retain their checks. The eight-byte status policy is unchanged. Four-byte detection again selects openpilot longitudinal control and makes Experimental Mode available. This uses FrogPilot's control path without flashing the separate, unidentified Smart DSU or switching to private `0xF10` commands.

The feature is **selected automatically from detected hardware**, following FrogPilot's Prius/Pedal/Smart DSU activation logic. It is selected only when the existing car identification resolves to `CAR.TOYOTA_PRIUS` and both expected hardware messages are present on bus 0:

- comma Pedal sensor: **`0x201`, 6 bytes**.
- Smart DSU: **`0x2FF`, 4 or 8 bytes**.

For four-byte status, the interface selects the dedicated parser definition and `PRIUS_PEDAL_SDSU_4` safety flag. Both layers validate the counter and checksum; malformed lengths, checksum failures and repeated counters are covered by regression tests. The legacy eight-byte definition uses its existing 100 Hz message expectation.

The interface enables longitudinal control and passes a dedicated Prius/Pedal safety flag as soon as that combination is detected. **No alpha longitudinal-control opt-in is required.** The Prius path does not advertise `alphaLongitudinalAvailable`, so the old alpha toggle is not offered for this configuration. The automatic-selection reference is FrogPilot production [`9985af62b02fce21cbdd2941ebb55a598a84fffa`](https://github.com/FrogAi/FrogPilot/blob/9985af62b02fce21cbdd2941ebb55a598a84fffa/selfdrive/car/toyota/interface.py). This port retains its narrower requirement for both correctly sized device messages. A stock DSU, disconnected DSU, pedal alone, wrong bus, wrong packet length, Prius V, TSS2 Prius, or another Toyota does not activate this path.

Hardware selection is separate from engagement and actuation. Cruise must still be engaged, longitudinal control must be active, and all controller and firmware checks below must pass before a nonzero Pedal command is permitted. Other Toyota configurations retain their existing alpha-longitudinal behavior.

FrogPilot treats this Prius as a stop-and-go car. This port uses its fixed **0.12 normalized pedal launch assist**, sent at **50 Hz**, only while longitudinal control is active, the vehicle is stopped, requested acceleration is positive and finite, the gear is Drive, CAN and device state are healthy, and neither driver pedal nor cancel is active. It uses FrogPilot's Prius/Pedal standstill-request behavior. Acceleration and braking otherwise continue through Toyota's existing ACC interface and its limits.

The Prius/Pedal path also uses FrogPilot's gentler acceleration-feedback integral gain: 0.5 at 2 m/s, falling to 0.25 at 5 m/s and above. The base release's non-TSS2 Toyota gain was approximately 8–9 times higher at the observed cruising speeds and produced larger corrections around small acceleration fluctuations. The change is limited to `PRIUS_PEDAL`; the feedforward request, acceleration bounds, driver overrides and other Toyota configurations are preserved. A synthetic feedback-oscillation regression fails with the old gain and passes with this correction. Replaying recorded inputs reduced command swings, but an open-loop replay does not establish comfort or closed-loop stability in the vehicle.

Experimental Mode treats the set speed as an upper bound and can deliberately request less acceleration or a lower speed. Toyota also supplies separate internal and cluster set speeds. Neither the gain correction nor the Pedal path overrides the model's braking, lead constraints or those speed representations to force the car to the displayed maximum.

Inactive pedal commands contain **raw zero** in both command tracks, with `ENABLE=0`. Encoding physical zero using the DBC offsets would alter passthrough scaling. The rolling 4-bit counter and reverse CRC-8/D5 are generated and validated. Driver accelerator override uses the integer mean of both physical sensor tracks with FrogPilot's threshold of 805. PCM gas feedback from the interceptor is not mistaken for driver input. SDSU follow-distance button events are preserved.

The panda mode independently checks the fixed command tracks, enable/reserved bits, CRC, controls permission, driver gas/brake, standstill, pedal faults, the protocol-specific SDSU status policy above, message counters and data freshness. Both device streams must be valid and no more than **250 ms** old for nonzero longitudinal commands. A stale or invalid stream blocks nonzero actuation while permitting inactive/cancel messages. Incompatible stock-longitudinal, LTA, alternate-brake or SecOC modes cannot enable pedal output. Existing steering limits and the full safety suite are retained.

## Validation and build

Use Python 3.12:

```sh
python -m pip install -e 'opendbc_repo[testing]' scons
cd opendbc_repo
python -m unittest opendbc.car.toyota.tests.test_toyota opendbc.car.toyota.tests.test_prius_pedal
python -m unittest discover -s opendbc/can/tests
python -m unittest discover -s opendbc/safety/tests
SAFETY_COVERAGE=1 python -m unittest discover -s opendbc/safety/tests
gcovr -r opendbc/safety --exclude '.*/libsafety/.*' --fail-under-line 100 --txt-summary
```

On macOS, add `--gcov-executable 'xcrun llvm-cov gcov'` to the last command.

The local full safety suite ran **3,276 tests**, with **398 inherited skips**, successfully. CAN parsing/packing ran **49 tests** successfully. Safety coverage was **100% of 3,037 lines and all 190 functions**; branch coverage was **97.0%**. The targeted tests include the release-mode firmware build, gating across Toyota platforms, driver override, cancellation, device faults, malformed/replayed CAN packets, timeouts, command bounds, 50 Hz scheduling and live parser integration.

The four-byte SDSU application was also rebuilt on the target comma 3X. That physical-device run passed **23 Toyota tests** and ran **101 Prius safety tests**, with **8 inherited skips** and no failures. See the [rebuild and offroad boot record](DEVICE_VERIFICATION.md) for the exact installed source, firmware and retained model assets. The workflow below runs the complete regression suite for each published revision.

The modified STM32H7 firmware also compiled with Arm GNU Toolchain 14.3.rel1 and the project's `-Wall -Wextra -Wstrict-prototypes -Werror` flags. From the repository root, reproduce the isolated pair build with `arm-none-eabi-gcc` on PATH:

```sh
python tools/prius_pedal/build_firmware.py --with-development-bootstub --output-dir /tmp/prius-pedal-firmware
python tools/prius_pedal/verify_firmware.py
```

The [GitHub Actions workflow](https://github.com/groxaxo/prius-pedal/actions/workflows/prius-pedal.yml) repeats tests, coverage and the firmware build for pushes and pull requests targeting `main`. CI also checks the bundled image hashes, application signature/version, ARM vectors, and a digest of the compatible safety, controller, CAN-definition and build inputs. Each successful run retains a bench firmware pair with its source revision and SHA-256 hashes for 14 days. The initial implementation passed in [run 42171078154](https://github.com/groxaxo/prius-pedal/actions/runs/42171078154); use the workflow page for the current revision's result.

## Delivery boundary

This branch is a **source/firmware test candidate**, not a road-qualified release. It bundles the matching STM32H7 application and development bootstub in `panda/board/obj`, with provenance in `tools/prius_pedal/bundled_firmware.json`. The application is a RELEASE safety build. Its recorded source revision precedes the packaging commit; the compatibility digest verifies that the control/safety/build inputs still match the images. Documentation and branding changes do not require another firmware build. Back up the device and verify its hardware, signing compatibility and recovery access before deployment. Recorded-CAN replay and stationary hardware verification remain necessary before vehicle use.

The build helper compiles the main application with release safety checks but signs with the upstream **public debug test key**. That is not a comma-official release signature. With `--with-development-bootstub`, it separately builds the upstream development bootstub, which accepts official release and public debug keys. The main application keeps RELEASE safety enforcement. The build and CI steps do not flash anything; they compile in temporary directories. A controlled on-device deployment must install the matching pair, since the normal panda updater can replace both images when it finds a mismatch.

Software tests do not establish Prius-specific pedal calibration, physical harness routing, SDSU firmware behavior, AEB behavior, braking performance, camera/model acceptance, or in-car driving acceptance. The unchanged official baseline and its firmware remain available at the frozen upstream tag for recovery. Keep device-specific installation and boot evidence separate from software-test results.
