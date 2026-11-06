# A guide for 2016 Prius owners

[← Back to Prius Pedal Lab](../README.md)

Prius Pedal Lab is a development project for a **2016 Toyota Prius with Toyota Safety Sense P, a comma 3X, a physical comma Pedal, and a Smart DSU**. Its specific addition is bounded Pedal assist when moving off from standstill, adapted from FrogPilot.

**The code and matching test firmware pair are available. In-car validation is still pending.** The initial custom build passed installation and offroad reboot checks on the target comma 3X on 6 November 2026. Those checks establish boot/signature compatibility, not vehicle behavior. There is no vehicle-qualified installer published for this candidate.

## Is your Prius the right platform?

Check the car's factory equipment, not just the year on its registration. A 2016 Prius needs **Toyota Safety Sense P (TSS-P)** for this path. Equipment can vary by market and trim. Confirm it from the vehicle documentation and actual ECU identification.

The software must identify the vehicle as **`CAR.TOYOTA_PRIUS`**. The existing fingerprint and ECU firmware database handle that identification. This project does not add a manual model-year override.

| Your car or configuration | Scope of this port |
| --- | --- |
| 2016 Prius with TSS-P, Pedal and Smart DSU | Intended hardware-validation target |
| 2016 Prius without TSS-P | Outside this port's scope |
| Prius v / Prius+ | A different vehicle platform; this Pedal path stays disabled |
| Later Prius with TSS2 | A different vehicle platform; this Pedal path stays disabled |
| TSS-P Prius with stock or disconnected DSU | This Pedal path stays disabled |
| TSS-P Prius with Pedal only | This Pedal path stays disabled |
| Later TSS-P Prius / Prius Prime | Some years share the software platform; separate hardware acceptance is required |

## Hardware you need

| Item | Why it matters |
| --- | --- |
| **comma 3X and a compatible, verified Toyota harness** | The device and vehicle connection targeted by this fork's `release-tizi` base |
| **Physical comma Pedal / gas interceptor** | Reads the accelerator's two sensor tracks and accepts the bounded assist command |
| **Smart DSU / SDSU** | Provides the DSU interface used by this longitudinal-control path |
| **Matching panda safety firmware** | Enforces the new Pedal mode independently from the controller |

A Pedal does not replace the DSU's braking interface. Both devices are required. The bundled main application retains release safety checks and is signed with the upstream public debug test key. Its matching development bootstub accepts official release and public debug keys. This is a custom signing configuration; an unchanged official release bootstub may reject the custom application.

The software base is **openpilot 0.11.2** at official commit `f7db927c728bab57bb1263e05465766a8f28fc9d`, with **AGNOS 19.9**. The fork's branch name does not make its custom firmware an official comma release.

## What the Pedal behavior does

With the feature enabled, the controller checks that the car is stationary, the gear is Drive, longitudinal control is active, the acceleration request is positive and finite, and both devices and CAN data are healthy. It then permits the fixed launch-assist command used by FrogPilot for this Prius platform.

The assist stops when the car moves, the driver presses either pedal, cruise is cancelled, or the control/device checks fail. Ongoing acceleration and braking continue through Toyota's existing ACC command path and its limits.

The **0.12 normalized command** is a protocol/control value, not a claim about engine power or a guaranteed percentage of physical throttle. It is sent at **50 Hz** during eligible standstill assist. Physical pedal calibration and vehicle response have not been established by the automated tests.

The Prius/Pedal standstill-request behavior and SDSU follow-distance button input are also included. This port retains the existing steering limits and driver monitoring.

## How activation works

The interface automatically selects this path after identifying the TSS-P Prius platform and seeing both expected hardware messages on bus 0. This follows FrogPilot's hardware-based selection for the Prius/Pedal/Smart DSU combination. No separate Pedal switch or alpha longitudinal opt-in is required.

Selecting the path does not engage cruise or request acceleration. Pedal output still requires normal engagement, active longitudinal control, an eligible stationary start, and healthy device data. The driver pedal/brake and cancel overrides remain in force. If either required device is missing, this Pedal path stays disabled.

<details>
<summary>Hardware-message details for developers and diagnostics</summary>

| Device | CAN address | Required length |
| --- | --- | --- |
| Pedal sensor | `0x201` | 6 bytes |
| Smart DSU | `0x2FF` | 8 bytes |

Messages on another bus or with another length do not enable the feature. During operation, faults, invalid Pedal checksums/counters, or stale device data prevent nonzero actuation. The firmware requires both device streams to be valid and no more than 250 ms old.

Message presence is a detection condition, not proof of correct wiring, device firmware, or physical behavior.

</details>

## Current status

| Area | Status |
| --- | --- |
| Prius/Pedal source port | Implemented and covered by integration tests |
| Toyota/CAN regression tests | Passed |
| Full safety suite and line coverage | Passed; workflow enforces 100% safety line coverage |
| STM32H7 firmware build | Passed; matching application, development bootstub and source/hash manifest bundled in `main` |
| Firmware / bootstub signature compatibility on the target device | Initial custom pair passed offroad installation/reboot checks on 6 November 2026; verify each updated pair on the selected device |
| Recorded vehicle-CAN replay | Pending |
| Physical harness, Pedal calibration, and SDSU/AEB behavior | Pending |
| Stationary hardware and driver-override acceptance | Pending |
| In-car driving acceptance | Pending |

[Latest validation runs](https://github.com/groxaxo/prius-pedal/actions/workflows/prius-pedal.yml) · [Detailed software evidence and build commands](PRIUS_PEDAL.md#validation-and-build)

The bundled panda application implements the new safety mode, and the development bootstub accepts its custom signature. The repository checks both images against their recorded source inputs and hashes. A device backup, controlled deployment, on-device signature/boot checks, recorded-CAN replay, and stationary hardware checks remain necessary before vehicle use. Repository merges do not flash or install anything on the comma device.

## If your setup is not detected

Confirm the actual ECU identification, TSS-P equipment, physical Pedal, and Smart DSU first. Then inspect the two expected message streams, their bus and length, and any Pedal/SDSU faults. The controller intentionally keeps this path disabled when those conditions are missing.

For a useful issue report, include the vehicle's market/trim and TSS-P equipment, device/AGNOS version, repository branch and commit, Pedal/SDSU firmware versions if known, and the observed fault or behavior. Include whether the observation came from a software test, a recorded-CAN replay, or physical hardware.

## Where to go next

- [Implementation, exact behavior, and FrogPilot source map](PRIUS_PEDAL.md)
- [Test and firmware build instructions](PRIUS_PEDAL.md#validation-and-build)
- [Changes in this fork](../CHANGELOG.md)
- [Unchanged official baseline tag](https://github.com/groxaxo/prius-pedal/tree/upstream-release-tizi-0.11.2)
