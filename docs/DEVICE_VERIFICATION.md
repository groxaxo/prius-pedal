# comma 3X rebuild and offroad verification — 7 November 2026

[← Back to Prius Pedal Lab](../README.md)

The application with four-byte Smart DSU support was rebuilt and reinstalled on the target comma 3X, then passed a normal reboot and offroad verification. The car remained disconnected throughout these checks. Physical vehicle and driving acceptance remain pending.

## Software checked

| Component | Verified version |
| --- | --- |
| Installed application source | [`098a9d9`](https://github.com/groxaxo/prius-pedal/commit/098a9d9832c0996dca7b944f9215b39a5aa9ae8e), including four-byte SDSU support, the earlier main merge and the Prius home banner |
| Four-byte SDSU implementation | [`129e12b`](https://github.com/groxaxo/prius-pedal/commit/129e12b8a77f2fb9c8e51d6c3875116830fb7aa6), retaining the legacy eight-byte variant |
| Device and OS | comma 3X / tizi, AGNOS 19.9 |
| Running panda application | `DEV-129e12b8-RELEASE`; running signature matched the bundled signed image |
| Firmware package | [Manifest at the installed revision](https://github.com/groxaxo/prius-pedal/blob/098a9d9832c0996dca7b944f9215b39a5aa9ae8e/tools/prius_pedal/bundled_firmware.json); source compatibility, image hashes and signature verifier passed |
| SSH identity | Existing owner-managed Mac identity; previously registered as a GitHub authentication key and imported through the normal comma key fetcher |

The firmware package and implementation commits are preserved in `main`. Later documentation commits do not change the recorded installed source or its verified firmware inputs. Native binaries and generated files produced by the physical-device rebuild differ from the packaged release artifacts; the source revision above identifies their inputs.

## Rebuild scope

The native build ran in a separate checkout while the previous installation remained available. It rebuilt common libraries, messaging, estimator helpers, logging/encoding, camera services, pandad and the longitudinal planner. The UI Python files were compiled and exercised with the actual physical-device renderer. Toyota integration tests passed **23 of 23**; the Prius Pedal safety suite, with undefined-behavior sanitizer, ran **101 tests**, including **8 inherited skips**, with no failures.

The release includes compiled driving, driver-monitoring and warp assets but omits their original ONNX model inputs. Those packaged assets were retained byte-for-byte. The successful build used explicit native application targets, avoiding model regeneration. It did not rebuild the neural-network models.

The existing `DEV-129e12b8-RELEASE` firmware pair was retained without flashing. The native build's generated panda version metadata was restored to the saved, verified package before installation, then the firmware/source verifier was rerun. The previous installation and settings were preserved in private device backups before the staged application replaced the running installation.

## Observed results

The record date is **7 November 2026, Pacific/Auckland**. A normal software reboot changed the Linux boot ID. Observation intervals use device uptime, and fresh SSH connections disabled connection reuse.

| Check | Observed result |
| --- | --- |
| Installed source | Device branch `main` at `098a9d9`; the newer four-byte SDSU fix and matching firmware remained present |
| Existing SSH authorization | Saved authorization digest unchanged through the rebuild and reinstall; no new key pair created |
| SSH after reboot | Fresh login succeeded using the existing Mac key and saved host alias, including after removal of the temporary USB port forward |
| Home screen | Actual 2160 × 1080 device render showed the red Prius image with Upgrade Now and the paired-device Firehose promotion absent; owner confirmed the same home screen after final reboot |
| Rebuilt planner library | Loaded successfully from the installed location before and after reboot |
| UI and services | UI, pandad and hardwared remained running with unchanged process IDs across **134.81 seconds** of device uptime |
| MCU health | Monotonic MCU uptime without a reset during that interval; zero faults and SPI errors; healthy heartbeat |
| Firmware identity | Running `DEV-129e12b8-RELEASE` signature matched the bundled signed image after reboot |
| Offroad state | Ignition inactive, harness disconnected, NOOUTPUT safety mode, controls disabled |
| Automatic updates | `DisableUpdates=true`; startup log confirmed updates disabled by this parameter |
| Firehose | Runtime `networkMetered=true`, `GsmMetered=true`, and all saved Wi-Fi/cellular profiles metered; Firehose inactive |
| Startup and storage | No storage-error matches in **1,612 current-boot kernel lines**, no captured application/service traceback, import, segmentation or register-fault messages, and no failed systemd units |

The earlier banner and SSH checks also verified that the existing Mac identity survived a real clear-and-import GitHub-key refresh. The rebuild preserved that authorization and verified fresh access after another reboot. See the [SSH setup guide](SSH_ACCESS.md) for registration, refresh, recovery and deliberate revocation.

These results cover the observed offroad startup window. Update and metering values are saved preferences on the verified device; select and verify them on each installation. Firehose eligibility follows network metering, independently of the home-screen promotion replacement.

## Repeat the checks

1. Keep the car disconnected and power stable. Record source revision, generated/built output differences, AGNOS version, firmware version, boot ID and device uptime. Preserve the previous installation and settings before replacement.
2. Check the [bundled package verifier](../tools/prius_pedal/verify_firmware.py). Separately compare the running MCU signature and version with that verified package, and read its health without changing the safety configuration.
3. When rebuilding a release checkout, preserve its verified firmware package and model assets. Build native application targets in a separate checkout, then rerun tests and package verification before replacing the installation. The release's absent ONNX inputs prevent a full model rebuild from that checkout alone.
4. Exercise the rebuilt home layout on the physical device and confirm it renders the expected banner. Confirm that the installed native planner library loads from its final location.
5. Reboot normally, then open a fresh owner SSH connection:

   ```sh
   ssh -o BatchMode=yes -o ControlPath=none comma-prius 'id -un'
   ```

6. Confirm a new boot ID, the Prius home image, saved update/network preferences and live network metering. Take service and MCU-health readings at least two minutes apart using device uptime. Inspect current-boot application/kernel logs and failed services.

The [firmware and validation guide](PRIUS_PEDAL.md#validation-and-build) lists software tests and matching-image requirements. GitHub Actions separately runs the complete safety/CAN regression suite, coverage and an isolated firmware build for published revisions.

## Evidence and remaining work

Detailed logs, screen capture, settings backups, connection configuration and device identifiers remain in the owner's private deployment records. This public record summarizes source references, methods and observed results without publishing credentials, private identities, authorization lists or local network details.

Recorded vehicle-CAN replay, physical Pedal calibration, SDSU/braking/AEB behavior, stationary driver overrides and driving acceptance remain pending. The [2016 Prius owner guide](PRIUS_2016_OWNER_GUIDE.md#current-status) tracks that boundary.
