"""Local-only Windows hardware inventory and a real PyTorch device probe."""
import csv
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys


def inspect_hardware():
    report = {'os': platform.system(), 'architecture': platform.machine(),
              'logicalCores': os.cpu_count() or 1, 'nvidia': [],
              'diskFreeGiB': round(shutil.disk_usage(Path(__file__).resolve().parents[1]).free / 2**30, 1)}
    # No usernames, serial numbers, network addresses, or installed-program lists.
    script = """
    $ErrorActionPreference = 'Stop'
    $cpu = @(Get-CimInstance Win32_Processor)
    $gpu = @(Get-CimInstance Win32_VideoController)
    [ordered]@{
      cpu = @($cpu | ForEach-Object {$_.Name})
      physicalCores = ($cpu | Measure-Object NumberOfCores -Sum).Sum
      memoryGiB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
      graphics = @($gpu | ForEach-Object {$_.Name})
    } | ConvertTo-Json -Compress
    """
    try:
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                                 '[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; ' + script],
                                capture_output=True, text=True, encoding='utf-8', timeout=30, check=True)
        report.update(json.loads(result.stdout.lstrip('\ufeff')))
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        report['inventoryNote'] = type(error).__name__
    candidates = [shutil.which('nvidia-smi'),
                  str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'System32/nvidia-smi.exe'),
                  str(Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'NVIDIA Corporation/NVSMI/nvidia-smi.exe')]
    smi = next((path for path in candidates if path and Path(path).is_file()), None)
    if smi:
        try:
            result = subprocess.run([smi, '--query-gpu=index,name,memory.total,driver_version', '--format=csv,noheader,nounits'],
                                    capture_output=True, text=True, timeout=20, check=True)
            for row in csv.reader(io.StringIO(result.stdout)):
                report['nvidia'].append({'index': int(row[0]), 'name': row[1].strip(),
                                         'vramMiB': int(row[2]), 'driver': row[3].strip()})
            result = subprocess.run([smi], capture_output=True, text=True, timeout=20, check=True)
            match = re.search(r'CUDA Version:\s*(\d+\.\d+)', result.stdout)
            report['driverCudaVersion'] = match.group(1) if match else None
        except (OSError, subprocess.SubprocessError, ValueError, IndexError) as error:
            report['nvidiaNote'] = type(error).__name__
    return report


def choose_profile(report):
    cores = int(report.get('physicalCores') or max(1, report.get('logicalCores', 2) // 2))
    profile = {'wheel': 'cpu', 'device': 'cpu', 'dtype': 'float32',
               'cpuThreads': min(8, max(1, cores)), 'reason': '사용 가능한 NVIDIA CUDA GPU가 없어 CPU로 설정했습니다.'}
    cuda = tuple(int(x) for x in (report.get('driverCudaVersion') or '0.0').split('.'))
    eligible = [gpu for gpu in report.get('nvidia', []) if gpu.get('vramMiB', 0) >= 6144]
    if eligible and cuda >= (12, 8):
        profile.update(wheel='cu128', reason='NVIDIA GPU를 발견했습니다. PyTorch에서 실제 연산을 확인합니다.')
    elif report.get('nvidia'):
        profile['reason'] = 'GPU 메모리 6 GiB 또는 CUDA 12.8 지원 드라이버 조건을 충족하지 않아 CPU를 선택했습니다.'
    return profile


def probe_torch():
    import torch
    devices = []
    if torch.cuda.is_available():
        for index in range(torch.cuda.device_count()):
            try:
                properties = torch.cuda.get_device_properties(index)
                if properties.total_memory < 6144 * 2**20:
                    continue
                with torch.cuda.device(index):
                    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
                    x = torch.ones((128, 128), device=f'cuda:{index}', dtype=dtype)
                    y = x @ x
                    torch.cuda.synchronize(index)
                    if not bool(torch.isfinite(y).all()):
                        raise RuntimeError('Non-finite CUDA test')
                    del x, y
                    free, _ = torch.cuda.mem_get_info(index)
                devices.append({'device': f'cuda:{index}', 'dtype': str(dtype).split('.')[-1],
                                'name': properties.name, 'freeMiB': free // 2**20})
            except (RuntimeError, AssertionError):
                continue
    # Leave headroom for the speech tokenizer and Chrome; do not use an already full GPU.
    available = [device for device in devices if device['freeMiB'] >= 4096]
    best = max(available, key=lambda device: device['freeMiB']) if available else {'device': 'cpu', 'dtype': 'float32'}
    if best['device'] == 'cpu':
        x = torch.ones((16, 16))
        if not bool(torch.isfinite(x @ x).all()):
            raise RuntimeError('CPU tensor test failed')
    return {'torchVersion': torch.__version__, **best}


if __name__ == '__main__':
    print(json.dumps(probe_torch() if '--torch' in sys.argv else inspect_hardware(), ensure_ascii=False))
