#!/usr/bin/env python3
"""Guard stays byte-for-byte embedded in standalone bootstrap and tracks version floors."""
from pathlib import Path
import re
import subprocess
import tempfile

repo=Path(__file__).resolve().parents[1]
source=(repo/'bootstrap.sh').read_text()
expected=(repo/'scripts/aapanel-upgrade-guard.sh').read_text()
begin="<<'JQ_AAPANEL_GUARD_SOURCE'\n"
end="\nJQ_AAPANEL_GUARD_SOURCE\n"
assert source.count(begin)==1
embedded=source.split(begin,1)[1].split(end,1)[0]+'\n'
assert embedded==expected, 'Standalone guard and generated bootstrap guard diverge'
subprocess.run(['bash','-n',str(repo/'scripts/aapanel-upgrade-guard.sh')],check=True)
print('PASS generated guard exactly matches tested standalone script')
assert source.count('run_step "22c-panel-upgrade-guard"')==1
assert 'OnBootSec=45s' in source and 'OnUnitActiveSec=2min' in source
print('PASS automatic guard stage and periodic timer configuration')
assert 'sort -V | head -n1' in source
fn=re.search(r'(?ms)^verify_aapanel_version\(\) \{.*?^\}',source)
assert fn
for current,wanted,should_pass in [('8.0.6','8.0.6',True),('8.0.7','8.0.6',True),('8.0.6','8.0.7',False),('8.0.10','8.0.9',True)]:
 code=(f'aapanel_version() {{ printf %s {current}; }}\n'
       f'AAPANEL_EXPECTED_VERSION={wanted}\n'+fn.group(0)+'\nverify_aapanel_version\n')
 r=subprocess.run(['bash','-c',code],capture_output=True)
 assert (r.returncode==0)==should_pass,(current,wanted,r.stderr)
print('PASS installed aaPanel versions at or above baseline are accepted')
assert source.count('aaPanel updater version detection changed; refusing unpinned update')==1
assert source.count('getLatestOfficialVersion)')==1
assert "AAPANEL_EXPECTED_VERSION:-8.0.7" in source
print('PASS pinned updater version with fail-closed source change check')
