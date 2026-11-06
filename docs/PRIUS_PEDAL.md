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
| Physical pedal tracks, faults and follow-distance button | `selfdrive/car/toyota/carstate.py` | `opendbc_repo/opendbc/car/toyota/carstate.py` |
| Prius stop/start assist and standstill request | `selfdrive/car/toyota/carcontroller.py` | `opendbc_repo/opendbc/car/toyota/carcontroller.py` |
| Pedal CAN encoder and CRC | `selfdrive/car/__init__.py` | `opendbc_repo/opendbc/car/toyota/toyotacan.py`, `opendbc_repo/opendbc/can/dbc.py` |
| CAN definitions | `opendbc/toyota_nodsu_pt_generated.dbc` | Dedicated `toyota_prius_pedal_pt_generated` DBC, generated from the existing standard and community definitions |
| Firmware enforcement | Source is available in FrogPilot's development tree under `opendbc_repo/opendbc/safety/` | `opendbc_repo/opendbc/safety/modes/toyota.h` and its tests |

The production FrogPilot reference is [`8955eaae9574c2a9723f401bdbaf120bf021d08a`](https://github.com/FrogAi/FrogPilot/tree/8955eaae9574c2a9723f401bdbaf120bf021d08a). Its current development safety implementation was also inspected at [`b5c24be2ff6fa2aee5b058d3131382a0e8395309`](https://github.com/FrogAi/FrogPilot/tree/b5c24be2ff6fa2aee5b058d3131382a0e8395309). FrogPilot is MIT licensed, copyright (c) 2018 Comma.ai, Inc.; the upstream MIT license is retained.

## Implemented behavior

The feature is **off by default**. It is offered only when the existing car identification resolves to `CAR.TOYOTA_PRIUS` and both expected hardware messages are present on bus 0:

- comma Pedal sensor: **`0x201`, 6 bytes**.
- Smart DSU: **`0x2FF`, 8 bytes**.

It requires the existing explicit **alpha longitudinal-control opt-in**. The interface then enables longitudinal control and passes a dedicated Prius/Pedal safety flag. A stock DSU, disconnected DSU, pedal alone, wrong bus, wrong packet length, Prius V, TSS2 Prius, or another Toyota does not activate this path.

FrogPilot treats this Prius as a stop-and-go car. This port uses its fixed **0.12 normalized pedal launch assist**, sent at **50 Hz**, only while longitudinal control is active, the vehicle is stopped, requested acceleration is positive and finite, the gear is Drive, CAN and device state are healthy, and neither driver pedal nor cancel is active. It uses FrogPilot's Prius/Pedal standstill-request behavior. Acceleration and braking otherwise continue through Toyota's existing ACC interface and its limits.

Inactive pedal commands contain **raw zero** in both command tracks, with `ENABLE=0`. Encoding physical zero using the DBC offsets would alter passthrough scaling. The rolling 4-bit counter and reverse CRC-8/D5 are generated and validated. Driver accelerator override uses the integer mean of both physical sensor tracks with FrogPilot's threshold of 805. PCM gas feedback from the interceptor is not mistaken for driver input. SDSU follow-distance button events are preserved.

The panda mode independently checks the fixed command tracks, enable/reserved bits, CRC, controls permission, driver gas/brake, standstill, pedal faults, SDSU state, message counters and data freshness. Both device streams must be valid and no more than **250 ms** old for nonzero longitudinal commands. A stale or invalid stream blocks nonzero actuation while permitting inactive/cancel messages. Incompatible stock-longitudinal, LTA, alternate-brake or SecOC modes cannot enable pedal output. Existing steering limits and the full safety suite are retained.

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

The local full safety suite ran **3,222 tests**, with **394 inherited skips**, successfully. CAN parsing/packing ran **49 tests** successfully. Safety coverage was **100% of 3,030 lines and all 190 functions**; branch coverage was **97.0%**. The targeted tests include the release-mode firmware build, gating across Toyota platforms, driver override, cancellation, device faults, malformed/replayed CAN packets, timeouts, command bounds, 50 Hz scheduling and live parser integration.

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
