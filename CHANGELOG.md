# Changelog

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
