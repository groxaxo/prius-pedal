# Prius parked verification — 8 November 2026

The FrogPilot compatibility correction was installed on the owner's comma 3X, tested with the Prius stationary in Park, and checked again after a full comma reboot. Openpilot longitudinal control and Experimental Mode are enabled; the previous Cruise Fault is absent in live telemetry. These results do not establish road engagement, low-speed actuation or braking acceptance.

## Exact software and installation

- Control and safety source: [`42bec01`](https://github.com/groxaxo/prius-pedal/commit/42bec01b7a7a056cd1090084ce1acba8f0f1d15e).
- Installed application/package revision: [`89d24ed`](https://github.com/groxaxo/prius-pedal/commit/89d24ed4087e6ca29561d3e4c1503cf6b3c7f785).
- Running Panda application: `DEV-42bec01b-RELEASE`. Its running signature matches the bundled signed image and the source/hash verifier passes.
- Installation used an inactive staging clone, a private rollback backup, fresh sustained Park/zero-speed/disengaged checks before service stop and reboot, and an application-only Panda flash. The existing bootstub was retained.
- All 24 native files from the earlier device rebuild were preserved by SHA256. The correction changes Python control selection/status interpretation and the matching Panda application; it does not rebuild driving models.

The [source comparison](PRIUS_PEDAL.md#four-byte-sdsu-takeover-status) explains why the port's additional SDSU status check differed from FrogPilot. The observed four-byte legacy status 5 remains visible in raw CAN data. The corrected host and Panda no longer mistake that stock-ACC watchdog status during openpilot takeover for an actuator fault. Other device statuses, native Toyota faults, checksum/counter/freshness checks and actuator limits remain enforced.

## Observed after reboot

The Linux boot ID changed, and SSH through the existing phone bridge returned. Fresh device, Panda, car-state, selfdrive-state and car-control messages were alive and valid.

| Check | Result |
| --- | --- |
| Vehicle | `TOYOTA_PRIUS`, Park, 0 km/h, disengaged |
| Longitudinal selection | `openpilotLongitudinalControl=true`, flags `12289`, safety parameter `12354` |
| Minimum software engagement speed | `minEnableSpeed=-1`; actual low-speed engagement remains untested |
| CAN and ACC state | `canValid=true`, `accFaulted=false` |
| Published UI alert fields | Empty |
| Experimental Mode | Saved preference and running backend both true after reboot |
| Panda | No faults, invalid receive checks, lost heartbeat or SPI errors; controls disallowed |
| Smart DSU sample | 757 status messages with legacy status 5 during a 15-second observation |
| Pedal sample | 732 status messages, all state 0 |
| Acknowledged commands | 749 inactive Pedal messages and 500 zero-acceleration ACC messages in that observation |
| Nonzero parked commands | None observed |
| Firmware and rebuilt artifacts | Matching running signature; all 24 native-file hashes preserved |
| Saved preferences | Automatic updates disabled and metered cellular preference preserved |

Experimental Mode was separately switched off and on through its saved preference while the car remained parked and disengaged. The running backend followed both transitions. The owner's existing confirmation was already present and was retained. Mode was left on and survived the reboot. This verifies preference/backend behavior and the UI's longitudinal-availability prerequisite; a physical tap on the settings toggle was not part of this test.

## Software validation

[GitHub validation for the installed revision passed](https://github.com/groxaxo/prius-pedal/actions/runs/42423358943): lint, bundled image/source verification, 25 Toyota tests, 49 CAN tests, full safety tests with undefined-behavior sanitizer, 100% safety line coverage and the isolated ARM firmware build. Locally the safety suite ran 3,276 tests with 398 inherited skips and no failures; line coverage was 3,037 of 3,037 lines. The inactive on-device stage ran 117 targeted tests with eight inherited skips and no failures.

The new regressions cover protocol-specific status handling, native ACC/low-speed-lockout faults, Pedal faults, invalid and replayed frames, stale data, braking overrides and acceleration limits. They preserve the stricter status policy for the eight-byte protocol.

## Remaining physical acceptance

No cruise engagement, active throttle/brake command, steering actuation or road test was requested remotely. Physical Pedal calibration, harness behavior, braking/AEB behavior, driver overrides and engagement below the factory ACC threshold still require controlled vehicle validation. A parked successful boot cannot prove those behaviors. The separate Smart DSU's precise board and firmware identity also remain unverified; this repair did not flash that module.

The [7 November rebuild record](DEVICE_VERIFICATION.md) documents the preceding native build, home banner and offroad checks. Device identifiers, raw logs, settings and recovery backups remain private.
