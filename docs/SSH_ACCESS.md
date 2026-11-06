# Keep an existing Mac SSH key through GitHub refreshes

[← Back to Prius Pedal Lab](../README.md)

Use an existing owner-managed Mac SSH identity and register its **public key as an authentication key** on the GitHub account entered on the comma. Refreshing that account's keys then downloads the same public key again. Keep the working private identity on the Mac across software deployments.

This uses the existing comma SSH-key workflow. The fork's [`SshKeyFetcher`](../openpilot/selfdrive/ui/widgets/ssh_key.py) downloads `https://github.com/<username>.keys` and replaces the saved `GithubSshKeys` parameter. A key added only to the comma's cached list survives a reboot, but a later GitHub refresh replaces that list. Registering the existing public key on GitHub makes it part of every successful refresh.

## Register the existing public key

For an existing identity at `~/.ssh/id_ed25519`, inspect its public fingerprint:

```sh
ssh-keygen -lf ~/.ssh/id_ed25519.pub
```

Use the actual `.pub` path if your existing identity has another name. Keep the corresponding private file on the Mac; GitHub and the comma receive the public key.

1. Open GitHub **Settings → SSH and GPG keys → New SSH key** on the account used by the comma.
2. Select **Authentication Key**. A signing-only key is excluded from the account's SSH authentication-key list.
3. Paste the contents of the existing `.pub` file and give it a recognizable, durable name such as `Prius owner Mac (existing key)`.
4. Compare the saved fingerprint with the Mac's public fingerprint above.

An authentication key also authorizes its holder to authenticate to GitHub over SSH with that account's repository permissions. Register an identity controlled by the owner, and retain its private file according to the owner's credential-backup policy. There is no need to generate another key pair for a deployment or refresh.

## Refresh the comma's keys

Keep the car disconnected while configuring and checking access.

1. On the comma, open **Settings → Developer → SSH Keys**.
2. Remove the saved GitHub username and add the same username again. Keep SSH enabled.
3. Let the key download finish, then open a new SSH connection from the Mac.

The existing public key remains authorized because the refreshed GitHub list includes it. A network/download failure can leave the cached list empty; complete the import successfully before relying on a new login.

If the cached Mac entry was the only working access route, confirm that GitHub publishes it before refreshing. For an account called `YOUR_GITHUB_USERNAME`, the public list can be checked with:

```sh
curl --fail --silent --show-error https://github.com/YOUR_GITHUB_USERNAME.keys | ssh-keygen -lf -
```

The displayed fingerprints should include the Mac fingerprint. This endpoint contains public authentication keys.

## Save a repeatable Mac connection

Add a host block to `~/.ssh/config`, using the comma's current IP and the existing private-identity path:

```sshconfig
Host comma-prius
  HostName COMMA_IP
  User comma
  Port 22
  IdentityFile ~/.ssh/id_ed25519
  IdentitiesOnly yes
  ForwardAgent no
  StrictHostKeyChecking yes
  ServerAliveInterval 15
  ServerAliveCountMax 3
```

If the connection uses an existing bridge, add `ProxyJump BRIDGE_USER@BRIDGE_HOST` to this block. Verify the device and bridge host keys before their first connection. Update `HostName` if the comma's address changes.

Test a fresh login without reusing a previous SSH connection:

```sh
ssh -o BatchMode=yes -o ControlPath=none comma-prius 'id -un'
```

The result should be `comma`. Repeat this check after refreshing the GitHub keys. A normal offroad reboot followed by another fresh login verifies reboot persistence as well.

## Recover through USB when needed

The [upstream connection guide](how-to/connect-to-comma.md) describes the comma 3X port layout. Power the device through **USB-C 2**, enable ADB, and connect the Mac's USB data cable to **USB-C 1**. A connection to USB-C 2 alone can expose the panda controller without exposing the Linux ADB interface.

Check `adb devices -l` and identify the intended comma before opening a shell. Preserve the existing saved keys and settings while repairing access. Once the existing public key is registered with the correct GitHub account, use the normal on-device key refresh and verify a new Mac SSH login.

## Preserve and revoke access deliberately

- Keep the working private identity, Mac host alias, and GitHub authentication entry across deployments. An owner-managed key is durable access; exclude it from temporary-key cleanup.
- To revoke this Mac's access, delete its authentication entry from GitHub and refresh the comma's keys. Deleting the GitHub entry alone leaves the old cached device authorization in place until it is refreshed.
- Use the device's SSH toggle to turn SSH off when desired. Recheck the actual connection after changing authorization.
- Commit setup instructions and generic examples. Keep private keys, account credentials, device-settings archives, and machine-specific connection configuration outside the repository.

The Prius banner, Pedal controls, firmware and update preferences are independent of this authentication setup.
