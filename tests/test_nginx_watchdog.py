#!/usr/bin/env python3
"""Verify missing Nginx installer PIDs never terminate the build watchdog."""
import re
import subprocess
from pathlib import Path

source = (Path(__file__).resolve().parents[1] / 'bootstrap.sh').read_text()
functions = []
for name in ('aapanel_nginx_process_snapshot', 'aapanel_nginx_cpu_sum'):
    match = re.search(r'(?ms)^' + name + r'\(\) \{.*?^\}', source)
    if not match:
        raise AssertionError('Function missing: ' + name)
    functions.append(match.group())

assert 'cpu="$(aapanel_nginx_cpu_sum "$pid")" || cpu="0.0"' in source
script = ('set -Eeuo pipefail\n' + '\n'.join(functions) + '\n'
          + 'aapanel_nginx_process_snapshot 99999999 >/dev/null\n'
          + 'cpu="$(aapanel_nginx_cpu_sum 99999999)" || cpu="0.0"\n'
          + '[[ "$cpu" == "0.0" ]]\n'
          + 'echo "PASS: missing process returns 0.0 without aborting"\n')
subprocess.run(['bash','-c',script], check=True)
