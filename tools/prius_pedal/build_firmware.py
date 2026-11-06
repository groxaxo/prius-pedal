#!/usr/bin/env python3
"""Build a bench-test panda image without replacing the inherited prebuilt image."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def build(output_dir: Path):
  root = Path(__file__).resolve().parents[2]
  revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
  git_dir = subprocess.check_output(['git', 'rev-parse', '--absolute-git-dir'], cwd=root, text=True).strip()
  dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip())
  compiler = subprocess.check_output(['arm-none-eabi-gcc', '--version'], text=True).splitlines()[0]
  output_dir.mkdir(parents=True, exist_ok=True)

  with tempfile.TemporaryDirectory(prefix='prius-pedal-firmware-') as temp:
    panda = Path(temp) / 'panda'
    shutil.copytree(root / 'panda', panda, ignore=shutil.ignore_patterns('obj', '__pycache__', '.sconsign.dblite', 'compile_commands.json'))
    (panda / 'board/obj').mkdir(parents=True)
    env = os.environ.copy()
    env.update(RELEASE='1', CERT=str(panda / 'board/crypto/certs/debug'),
               GIT_DIR=git_dir, GIT_WORK_TREE=str(root),
               PYTHONPATH=str(root / 'opendbc_repo') + os.pathsep + env.get('PYTHONPATH', ''))
    # RELEASE compiles out debug-only safety modes. The public test key does
    # not produce a comma-official signature or prove bootstub compatibility.
    subprocess.run(['scons', '-j4', 'board/obj/panda_h7.bin.signed'], cwd=panda, env=env, check=True)
    for name in ('panda_h7.bin.signed', 'version'):
      shutil.copy2(panda / 'board/obj' / name, output_dir / name)

  manifest = {
    'source_commit': revision,
    'source_dirty': dirty,
    'compiler': compiler,
    'target': 'STM32H7 panda / comma 3X',
    'signing': 'Public upstream debug test key; not an official release signature',
    'acceptance': 'Build artifact only; bench, bootstub and vehicle validation required',
    'sha256': {name: hashlib.sha256((output_dir / name).read_bytes()).hexdigest()
               for name in ('panda_h7.bin.signed', 'version')},
  }
  (output_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
  print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--output-dir', type=Path, required=True)
  build(parser.parse_args().output_dir.resolve())
