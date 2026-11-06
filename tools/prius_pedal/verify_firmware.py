#!/usr/bin/env python3
"""Verify the bundled Prius firmware pair against its manifest and source inputs."""
import base64
import hashlib
import json
from pathlib import Path
import struct

from build_firmware import source_digest


def verify(root: Path):
  manifest = json.loads((root / 'tools/prius_pedal/bundled_firmware.json').read_text())
  if manifest['source_dirty'] or manifest['compatible_source_sha256'] != source_digest(root):
    raise ValueError('Bundled firmware is dirty or stale; rebuild it from the current control/safety sources')
  if set(manifest['sha256']) != {'panda_h7.bin.signed', 'bootstub.panda_h7.bin', 'version'}:
    raise ValueError('A complete main-application and bootstub pair is required')

  images = root / 'panda/board/obj'
  for name, expected in manifest['sha256'].items():
    if hashlib.sha256((images / name).read_bytes()).hexdigest() != expected:
      raise ValueError(f'Bundled firmware hash mismatch: {name}')

  app = (images / 'panda_h7.bin.signed').read_bytes()
  length = struct.unpack('<I', app[:4])[0]
  if length + 128 != len(app) or app[length - 8:length] != b'VERS\x02\x00\x00\x00':
    raise ValueError('Invalid signed image length or version tag')
  entry = struct.unpack('<I', app[4:8])[0]
  if not 0x08020000 <= (entry & ~1) < 0x08040000 or not entry & 1:
    raise ValueError('Invalid STM32H7 application entry point')
  version = (images / 'version').read_bytes()
  if version != f"DEV-{manifest['source_commit'][:8]}-RELEASE".encode() or version + b'\x00' not in app[:length]:
    raise ValueError('The main application version does not match its recorded source')

  public = base64.b64decode((root / 'panda/board/crypto/certs/debug.pub').read_text().split()[1])
  fields = []
  while public:
    size = struct.unpack('>I', public[:4])[0]
    fields.append(public[4:4 + size])
    public = public[4 + size:]
  if len(fields) != 3 or fields[0] != b'ssh-rsa':
    raise ValueError('Unexpected upstream debug public-key format')
  exponent, modulus = (int.from_bytes(value, 'big') for value in fields[1:])
  signature = pow(int.from_bytes(app[length:], 'big'), exponent, modulus).to_bytes(128, 'big')
  expected_signature = b'\x00\x01' + b'\xff' * 0x69 + b'\x00' + hashlib.sha1(app[4:length]).digest()
  if signature != expected_signature:
    raise ValueError('Main application signature verification failed')

  bootstub = (images / 'bootstub.panda_h7.bin').read_bytes()
  stack, reset = struct.unpack('<II', bootstub[:8])
  if not 0x20000000 <= stack <= 0x24080000 or not 0x08000000 <= (reset & ~1) < 0x08020000 or not reset & 1:
    raise ValueError('Invalid STM32H7 bootstub vectors')
  if len(bootstub) >= 0x20000 or len(app) >= 0x20000:
    raise ValueError('Unexpected firmware sector size')
  print(f"Bundled firmware verified: source {manifest['source_commit']}, version {version.decode()}")


if __name__ == '__main__':
  verify(Path(__file__).resolve().parents[2])
