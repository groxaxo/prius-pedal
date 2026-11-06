#!/usr/bin/env python3
"""Build panda test firmware in isolation, optionally with a development bootstub."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def source_digest(root: Path) -> str:
  """Bind the images to safety, controller, CAN-definition and build inputs."""
  paths = {root / 'panda/SConscript', root / 'panda/SConstruct'}
  for directory in ('panda/board', 'opendbc_repo/opendbc/safety'):
    paths.update(p for p in (root / directory).rglob('*')
                 if p.is_file() and p.suffix in ('.c', '.h', '.s', '.S', '.ld', '.pub') and
                 not {'obj', 'tests'}.intersection(p.relative_to(root).parts))
  for directory in ('opendbc_repo/opendbc/car/toyota', 'opendbc_repo/opendbc/can', 'tools/prius_pedal'):
    paths.update((root / directory).glob('*.py'))
  paths.update((root / 'opendbc_repo/opendbc/dbc/generator/toyota').glob('*.dbc'))
  digest = hashlib.sha256()
  for path in sorted(paths):
    digest.update(path.relative_to(root).as_posix().encode() + b'\0' + hashlib.sha256(path.read_bytes()).digest())
  return digest.hexdigest()


def copy_panda(root: Path, target: Path):
  shutil.copytree(root / 'panda', target, ignore=shutil.ignore_patterns('obj', '__pycache__', '.sconsign.dblite', 'compile_commands.json'))
  (target / 'board/obj').mkdir(parents=True)


def build(output_dir: Path, with_development_bootstub: bool = False):
  root = Path(__file__).resolve().parents[2]
  revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
  git_dir = subprocess.check_output(['git', 'rev-parse', '--absolute-git-dir'], cwd=root, text=True).strip()
  dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip())
  compiler = subprocess.check_output(['arm-none-eabi-gcc', '--version'], text=True).splitlines()[0]
  output_dir.mkdir(parents=True, exist_ok=True)
  names = ['panda_h7.bin.signed', 'version']

  with tempfile.TemporaryDirectory(prefix='prius-pedal-firmware-') as temp:
    panda = Path(temp) / 'panda'
    copy_panda(root, panda)
    env = os.environ.copy()
    env.update(RELEASE='1', CERT=str(panda / 'board/crypto/certs/debug'),
               GIT_DIR=git_dir, GIT_WORK_TREE=str(root),
               PYTHONPATH=str(root / 'opendbc_repo') + os.pathsep + env.get('PYTHONPATH', ''))
    # RELEASE compiles out debug-only safety modes. The public test key does
    # not produce a comma-official signature or prove bootstub compatibility.
    subprocess.run(['scons', '-j4', 'board/obj/panda_h7.bin.signed'], cwd=panda, env=env, check=True)
    for name in ('panda_h7.bin.signed', 'version'):
      shutil.copy2(panda / 'board/obj' / name, output_dir / name)

    if with_development_bootstub:
      development = Path(temp) / 'panda-development'
      copy_panda(root, development)
      development_env = env.copy()
      development_env.pop('RELEASE', None)
      development_env.pop('CERT', None)
      # Only the bootstub is built with upstream development-key support.
      # The main application above keeps RELEASE safety enforcement.
      subprocess.run(['scons', '-j4', 'board/obj/bootstub.panda_h7.bin'], cwd=development, env=development_env, check=True)
      shutil.copy2(development / 'board/obj/bootstub.panda_h7.bin', output_dir / 'bootstub.panda_h7.bin')
      names.append('bootstub.panda_h7.bin')

  manifest = {
    'source_commit': revision,
    'source_dirty': dirty,
    'compatible_source_sha256': source_digest(root),
    'compiler': compiler,
    'target': 'STM32H7 panda / comma 3X',
    'signing': 'Public upstream debug test key; not an official release signature',
    'main_application_safety': 'RELEASE build; debug safety modes compiled out',
    'bootstub': 'Upstream development bootstub accepting official release and public debug keys' if with_development_bootstub else None,
    'acceptance': 'Build artifact only; bench, bootstub and vehicle validation required',
    'sha256': {name: hashlib.sha256((output_dir / name).read_bytes()).hexdigest()
               for name in names},
  }
  (output_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
  print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--output-dir', type=Path, required=True)
  parser.add_argument('--with-development-bootstub', action='store_true')
  args = parser.parse_args()
  build(args.output_dir.resolve(), args.with_development_bootstub)
