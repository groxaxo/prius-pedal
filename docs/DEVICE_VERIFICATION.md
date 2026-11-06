# comma 3X offroad verification — 7 November 2026

[← Back to Prius Pedal Lab](../README.md)

The Prius banner, matching firmware startup, durable owner SSH access, and selected update/upload preferences passed checks on the target comma 3X. The car remained disconnected throughout this verification. Physical vehicle and driving acceptance remain pending.

## Software checked

| Component | Verified version |
| --- | --- |
| Installed application | [`bb35c29`](https://github.com/groxaxo/prius-pedal/commit/bb35c297695f7b91ab6cac16ad7670c816c17dcb), containing the Prius home-screen banner and automatic Pedal selection |
| Device and OS | comma 3X / tizi, AGNOS 19.9 |
| Running panda application | `DEV-c46b3dee-RELEASE`; running signature matched the bundled signed image |
| Firmware package | [Verified bundled manifest](https://github.com/groxaxo/prius-pedal/blob/bb35c297695f7b91ab6cac16ad7670c816c17dcb/tools/prius_pedal/bundled_firmware.json); source/package verifier passed |
| SSH workflow | Existing Mac identity registered as an authentication key on the owner's GitHub account, then imported with the installed key fetcher |

The banner installation kept the existing matching firmware. The later SSH documentation and this verification record add documentation without changing the application, vehicle-control code or firmware inputs.

## Observed results

The record date is **7 November 2026, Pacific/Auckland**. A normal software reboot changed the Linux boot ID. Fresh SSH connections used the existing Mac identity with connection reuse disabled.

| Check | Observed result |
| --- | --- |
| Existing SSH identity | A real clear-and-import GitHub-key refresh retained the existing Mac key and the other original entries; fresh login succeeded afterward |
| SSH after reboot | Fresh noninteractive login succeeded, and the saved authorization list survived |
| Home screen | Owner confirmed the supplied red Prius image appeared on the physical screen after reboot |
| UI and services | UI, pandad and hardwared remained running with unchanged process IDs across **258.62 seconds** of device uptime |
| MCU health | Monotonic MCU uptime without a reset; zero reported faults and SPI errors, with a healthy heartbeat at both observations |
| Offroad state | Ignition inactive, harness disconnected, NOOUTPUT safety mode, controls disabled |
| Automatic updates | `DisableUpdates=true`; startup log confirmed that updates were disabled by this parameter |
| Firehose | Runtime `networkMetered=true`, `GsmMetered=true`, and all saved Wi-Fi/cellular profiles metered; Firehose status inactive |
| Startup and storage | No storage-error matches in **1,644 current-boot kernel lines**, no captured application traceback/import/segmentation/register-fault messages, and no failed systemd units |

The device corrected its wall clock during startup. The stability interval above uses device uptime, so that clock synchronization did not shorten or lengthen the accepted interval.

These results describe the observed offroad startup window. The network and update values are saved preferences on the verified device. Choose and verify the corresponding preferences on each installation. The home-screen promotion replacement changes appearance; Firehose eligibility follows the device's network-metering state.

## Repeat the checks

1. Keep the car disconnected, power the comma steadily, and record the application commit, firmware version, boot ID and device uptime.
2. Check the bundled firmware with the [package verifier](../tools/prius_pedal/verify_firmware.py). Separately compare the running MCU version/signature with the intended package and read its health without changing safety configuration.
3. Use a normal software reboot. After startup, open a fresh owner SSH connection:

   ```sh
   ssh -o BatchMode=yes -o ControlPath=none comma-prius 'id -un'
   ```

4. Confirm the boot ID changed and the normal home screen shows the Prius image. Check saved update/network preferences and live network metering.
5. Take live service and MCU-health readings at least two minutes apart, measuring the interval by device uptime. Inspect the current-boot application/kernel logs and failed-service list.

See the [SSH setup guide](SSH_ACCESS.md) for the existing-key registration, alias, refresh, USB recovery and revocation procedure. The [firmware and validation guide](PRIUS_PEDAL.md#validation-and-build) describes the software checks and matching-image requirements.

## Evidence and remaining work

Detailed device logs, settings backups and machine-specific connection details remain in the owner's private deployment records. This public record includes source references, methods and summarized results. It contains no private keys, authentication material, device identifiers or local network configuration.

Recorded vehicle-CAN replay, physical Pedal calibration, SDSU/braking/AEB behavior, stationary driver overrides, and driving acceptance remain pending. The [2016 Prius owner guide](PRIUS_2016_OWNER_GUIDE.md#current-status) tracks that boundary.
