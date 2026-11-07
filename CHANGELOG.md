# Changelog

## FrogPilot four-byte SDSU compatibility — 8 November 2026

- Restore openpilot longitudinal selection for the TSS-P Prius with a six-byte Pedal and four-byte Smart DSU, making Experimental Mode available again.
- Correct a status interpretation introduced by this port: legacy SDSU status 5 is expected when standard openpilot ACC commands suppress stock ACC forwarding. FrogPilot does not treat SDSU status as a native ACC fault.
- Accept status 5 only on the four-byte path. Preserve the raw status, all other SDSU and Pedal fault checks, native Toyota ACC/lockout faults, checksum/counter/freshness checks and actuator limits.
- Add host and release-safety regressions for the observed status, retained faults and malformed/stale frames. The eight-byte behavior is unchanged.
- Supersede the stock-ACC recovery below; clearing the warning in stock mode did not meet the all-speed/Experimental Mode goal. Hardware driving acceptance remains separate from these software changes.

## Four-byte SDSU stock-ACC recovery

- Keep stock ACC when the detected SDSU uses the four-byte protocol whose observed firmware times out under standard ACC traffic. This prevents unsupported automatic longitudinal activation from causing the Cruise Fault warning.
- Preserve all device-state, counter, checksum and freshness safety checks. Retain the four-byte parser/safety implementation for bench verification.
- The factory speed limit and stock longitudinal control apply in this recovery mode; Experimental Mode requires a subsequently verified compatible hardware/firmware configuration.

## Native rebuild and four-byte SDSU firmware verification — 7 November 2026

- Publish the matching `DEV-129e12b8-RELEASE` STM32H7 application, development bootstub and source/hash manifest alongside the four-byte Smart DSU fix.
- Record the physical comma 3X native application rebuild and reinstall at `098a9d9`, including the deliberate retention of packaged driving/monitoring models because the release omits ONNX source inputs.
- Record 23 passing Toyota tests and 101 Prius safety tests run with 8 inherited skips and no failures on the comma.
- Recheck the full local suite: 3,274 safety tests with 398 inherited skips and no failures, 49 passing CAN tests, and 100% safety line coverage across 3,036 lines and all 190 functions.
- Verify a normal reboot, the physical Prius banner, existing Mac SSH access, unchanged saved authorization, disabled automatic updates and inactive Firehose.
- Record 134.81 seconds of stable offroad service/MCU observations, zero MCU faults or SPI errors, and no captured application/storage faults or failed units in the inspected boot window. In-car acceptance remains pending.

## Smart DSU compatibility fix — 7 November 2026

- Recognize the target Prius's four-byte Smart DSU status at 50 Hz, while retaining the legacy eight-byte variant.
- Select the corresponding CAN definition and firmware safety checks from the detected frame length. The four-byte path validates the Toyota checksum, rolling counter, device state and existing freshness limits.
- Correct the hardware-detection fallback that left stock ACC active and made Experimental Mode unavailable despite the Pedal and Smart DSU being present.
- Add regression cases using the observed four-byte payload, including malformed lengths, checksum failures and replayed counters. Vehicle engagement acceptance remains separate from software validation.

## Offroad verification and durable SSH record — 7 November 2026

- Record the completed comma 3X reboot, physical Prius banner confirmation, matching running-firmware signature, and stable offroad service/MCU observations.
- Document the existing Mac public-key registration that survives the normal GitHub-key refresh, with fresh login and reboot checks, recovery instructions and deliberate revocation.
- Record preserved automatic-update and metered-network preferences, with Firehose inactive after reboot.
- Link the verification record from the front page and owner guide, while retaining the pending vehicle-hardware and driving-acceptance status.

## Prius home-screen banner — 7 November 2026

- Replace the comma 3X home-screen subscription promotion with the owner's supplied Prius image.
- Replace the paired-device Firehose promotion with the wide image panel, keeping the Chill/Experimental mode control, pairing flow and offroad alerts available.
- Fit the image without cropping or distortion. Upload preferences, account state, vehicle controls and matching firmware are unaffected by this display change.

## Automatic Prius Pedal activation — 7 November 2026

- Follow FrogPilot's automatic hardware-based selection for the TSS-P Prius with a physical comma Pedal and Smart DSU. Remove the extra alpha longitudinal opt-in introduced by the initial port.
- Require both hardware messages on bus 0 with their expected lengths. Missing devices, unsupported platforms, faults, stale data and driver overrides retain their existing restrictions.
- Keep the alpha longitudinal toggle unavailable for this automatically supported Prius configuration; other Toyota alpha modes retain their existing behavior.
- Exercise automatic selection with alpha off/on and release status off/on, and verify that missing hardware prevents Pedal messages.
- Update the front page and owner/developer guides to explain automatic selection, engagement and the remaining physical-vehicle validation boundary.

## Matching firmware package — 6 November 2026

- Bundle the STM32H7 RELEASE-safety application and its matching upstream development bootstub for the custom public-debug-key signature.
- Record firmware source revision, compiler, hashes and compatible control/safety/build-input digest.
- Verify bundled hashes, application signature/version and ARM vectors in CI; reject stale firmware when compatible source inputs change.
- Build both images in isolation with `--with-development-bootstub`. Builds and CI do not flash the device.
- This remains a development candidate; device-specific boot/signature checks and in-car acceptance are separate requirements.

## Development candidate — 6 November 2026

### Added

- An opt-in Pedal + Smart DSU path for the TSS-P `TOYOTA_PRIUS` platform, with the 2016 Prius as the hardware-validation target.
- FrogPilot's fixed standstill launch assist, Prius/Pedal standstill-request behavior, and SDSU follow-distance button input.
- Pedal CAN encoding with a rolling counter and CRC, physical accelerator override, fault handling, and device-data freshness checks.
- Independent panda firmware restrictions for the new mode, preserving existing steering limits and the full safety test suite.
- Toyota integration and Pedal safety tests, plus GitHub Actions validation and an isolated STM32H7 bench firmware build with a source/hash manifest.
- A 2016 Prius owner guide, a detailed implementation/source map, and a redesigned repository front page.

### Branch integration

- `main` is the single development and default branch, containing the integrated Prius Pedal work and the new neon Tokyo banner.
- The `upstream-release-tizi-0.11.2` tag preserves the unchanged official baseline at `f7db927c728bab57bb1263e05465766a8f28fc9d`.
- The `archive/dragonpilot-pre-build` tag preserves the separate inherited DragonPilot code at `94ad85cfda64773a960d048dc11cac02d4aa86a5`.
- CI covers pushes and pull requests targeting `main`; the superseded branches have been retired.
- The original upstream README is preserved at the frozen baseline tag; original licenses and copyright notices remain in place.

### Validation and delivery

The implementation's full safety suite ran 3,222 tests with 394 inherited skips and no failures. All 49 CAN parser/packer tests passed. Local safety coverage was 100% of 3,030 lines and all 190 functions; branch coverage was 97.0%. The STM32H7 firmware built successfully locally and in GitHub Actions. The workflow repeats the software checks and build for new revisions.

This remains a source/firmware development candidate. Matching firmware and bootstub/signature compatibility, recorded-CAN replay, stationary hardware checks, and in-car acceptance remain pending. No code or firmware from this port has been installed on the target comma by the repository integration work.
