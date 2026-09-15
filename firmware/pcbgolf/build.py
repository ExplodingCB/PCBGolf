"""Portable, compile/link-only PCBGolf target; never opens a hardware interface.

Uses upstream SConscript's flags, startup, linker script, headers and debug keys.
Run from any directory with the workspace-local Python runtime. No SCons/shell
signing dependency is needed on Windows. All artifacts stay in this folder.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PANDA = ROOT / 'tools/panda-firmware'
OUT = HERE / 'build'
TOOLCHAIN = ROOT / 'tools/arm-gnu/arm-gnu-toolchain-12.3.rel1-mingw-w64-i686-arm-none-eabi/bin'
OPENDBC = PANDA / 'opendbc-src'
EXPECTED_PANDA = '78cf69904c332c599a297fcc2a09c08d10d429d5'
EXPECTED_OPENDBC = '057aee25b5eee7530f0b95b5b508c8c3247b0cd7'


def sha(path):
  return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_head(path):
  return subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()


def public_key(name):
  raw = base64.b64decode((PANDA / f'board/certs/{name}.pub').read_bytes().split()[1])
  values = []
  for _ in range(3):
    length = int.from_bytes(raw[:4], 'big')
    values.append(raw[4:4 + length])
    raw = raw[4 + length:]
  _, e, n = values
  e, n = int.from_bytes(e, 'big'), int.from_bytes(n, 'big')
  assert n.bit_length() == 1024

  def words(value):
    return '{' + ','.join(f'{(value >> (32 * i)) & 0xffffffff}U' for i in range(32)) + '}'

  return (f'RSAPublicKey {name}_rsa_key = {{.len=0x20, '
          f'.n0inv={2**32-pow(n,-1,2**32)}U, .n={words(n)}, '
          f'.rr={words(pow(2**1024,2,n))}, .exponent={e}}};\n')


def main():
  assert git_head(PANDA) == EXPECTED_PANDA, 'Unexpected upstream panda revision'
  assert git_head(OPENDBC) == EXPECTED_OPENDBC, 'Unexpected opendbc revision'
  OUT.mkdir(parents=True, exist_ok=True)
  generated = PANDA / 'board/obj'
  generated.mkdir(parents=True, exist_ok=True)
  version = f'PCBGOLF-{EXPECTED_PANDA[:8]}-DEBUG'
  (generated / 'gitversion.h').write_text(
    f'#pragma once\nextern const uint8_t gitversion[{len(version)+1}];\n'
    f'const uint8_t gitversion[{len(version)+1}]="{version}";\n')
  (generated / 'cert.h').write_text('#pragma once\n' + public_key('debug') + public_key('release'))

  def packet_hash(path):
    return int.from_bytes(hashlib.sha256(path.read_bytes().replace(b'\r', b'')).digest()[:4], 'little')

  flags = [
    '-mcpu=cortex-m7', '-mhard-float', '-DSTM32H7', '-DSTM32H725xx',
    '-mfpu=fpv5-d16', '-DPANDA_JUNGLE', '-DPCBGOLF_BGA100', '-DALLOW_DEBUG',
    '-Wall', '-Wextra', '-Wstrict-prototypes', '-Werror', '-mlittle-endian',
    '-mthumb', '-nostdlib', '-fno-builtin', '-std=gnu11', '-fmax-errors=1',
    '-Tboard/stm32h7/stm32h7x5_flash.ld', '-fsingle-precision-constant', '-Os', '-g',
    '-I.', '-Iboard/stm32h7/inc', '-I' + str(OPENDBC),
    f'-DHEALTH_PACKET_VERSION=0x{packet_hash(PANDA / "board/health.h"):08X}U',
    f'-DCAN_PACKET_VERSION_HASH=0x{packet_hash(OPENDBC / "opendbc/safety/can.h"):08X}U',
    f'-DJUNGLE_HEALTH_PACKET_VERSION=0x{packet_hash(PANDA / "board/jungle/jungle_health.h"):08X}U',
  ]
  log, commands = [], []

  def run(args, env=None):
    commands.append([str(a) for a in args])
    result = subprocess.run(args, cwd=PANDA, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.append(subprocess.list2cmdline(commands[-1]) + '\n' + result.stdout)
    (OUT / 'compile.log').write_text('\n'.join(log))
    if result.returncode:
      print(result.stdout)
      raise SystemExit(result.returncode)
    return result.stdout

  gcc = str(TOOLCHAIN / 'arm-none-eabi-gcc.exe')
  compiler = run([gcc, '--version']).splitlines()[0]
  compile_db = []
  for image, sources in {
    'bootstub': ['board/stm32h7/startup_stm32h7x5xx.s', 'board/crypto/rsa.c',
                 'board/crypto/sha.c', 'board/bootstub.c'],
    'main': ['board/stm32h7/startup_stm32h7x5xx.s', 'board/jungle/main.c'],
  }.items():
    target_flags = flags + (['-DBOOTSTUB'] if image == 'bootstub' else [])
    objects = []
    for src in sources:
      obj = OUT / (image + '-' + Path(src).stem + '.o')
      cmd = [gcc] + target_flags + ['-c', src, '-o', str(obj)]
      run(cmd)
      compile_db.append({'directory': str(PANDA), 'file': src, 'arguments': cmd})
      objects.append(str(obj))
    link_flags = [] if image == 'bootstub' else ['-Wl,--section-start,.isr_vector=0x8020000']
    run([gcc] + target_flags + link_flags + objects + ['-o', str(OUT / f'{image}.elf'),
        f'-Wl,-Map={OUT / (image + ".map")}'])
    run([str(TOOLCHAIN / 'arm-none-eabi-objcopy.exe'), '-O', 'binary',
         str(OUT / f'{image}.elf'), str(OUT / f'{image}.bin')])
  sizes = run([str(TOOLCHAIN / 'arm-none-eabi-size.exe'), str(OUT / 'bootstub.elf'), str(OUT / 'main.elf')])
  # A local development signature only. No upload, reset, USB or DFU operation.
  sign_env = dict(os.environ, SETLEN='1')
  run([sys.executable, 'board/crypto/sign.py', str(OUT / 'main.bin'),
       str(OUT / 'pcbgolf_bga100.bin.signed'), 'board/certs/debug'], env=sign_env)
  (OUT / 'compile_commands.json').write_text(json.dumps(compile_db, indent=2))
  evidence = {
    'status': 'bootstub and application compiled and linked; not hardware tested',
    'panda_commit': EXPECTED_PANDA, 'opendbc_commit': EXPECTED_OPENDBC,
    'compiler': compiler, 'compiler_sha256': sha(gcc),
    'target_macro_in_both_images': 'PCBGOLF_BGA100', 'flags': flags,
    'size_output': sizes, 'signature': 'upstream public development/debug key',
    'hardware_io_performed': False,
    'artifacts': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)}
                  for p in OUT.iterdir() if p.suffix in ('.elf', '.bin', '.signed')},
    'commands': commands,
  }
  (ROOT / 'reports/firmware-build.json').write_text(json.dumps(evidence, indent=2))
  print(compiler)
  print(sizes)
  print('Compiled and linked both PCBGolf images. No hardware interface was opened.')


if __name__ == '__main__':
  main()
