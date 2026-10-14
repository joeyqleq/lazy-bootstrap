#!/usr/bin/env bash
# Recover narrowly scoped aaPanel post-upgrade Nginx and panel state.
# Does not modify DNS, SSH, unrelated vhosts, or replace Nginx packages.
set -Eeuo pipefail
[[ $(id -u) == 0 ]] || { echo "Requires root" >&2; exit 2; }
exec 9>/run/lock/jq-aapanel-upgrade-guard.lock
flock -n 9 || exit 0
log(){ logger -t jq-aapanel-upgrade-guard -- "$*" || true; echo "$*"; }
# Never race the vendor updater while it is changing Python packages/config.
[[ ! -e /tmp/update_to7.pl ]] || { log "Vendor update active; deferring"; exit 0; }
root=/www/server/panel
bin=/www/server/nginx/sbin/nginx
ngconf=/www/server/nginx/conf/nginx.conf
domainfile=$root/data/domain.conf
portfile=$root/data/port.pl
[[ -x $bin && -f $ngconf && -f $domainfile && -f $portfile ]] || { log "Missing panel/Nginx preconditions"; exit 1; }
domain=$(tr -d '\r\n' < "$domainfile")
port=$(tr -d '\r\n' < "$portfile")
[[ $domain =~ ^[a-zA-Z0-9.-]+$ && $port =~ ^[0-9]+$ ]] || { log "Invalid panel domain or port"; exit 1; }
vhost=$root/vhost/nginx/$domain.conf
[[ -f $vhost ]] || { log "Missing canonical panel vhost: $vhost"; exit 1; }
ua='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36'
probe_backend() {
  local scheme=$1 code
  code=$(/usr/bin/curl --noproxy '*' -k -sS --connect-timeout 2 --max-time 5 -A "$ua" -H "Host: $domain" -o /dev/null -w '%{http_code}' "$scheme://127.0.0.1:$port/login" 2>/dev/null || true)
  [[ $code == 200 ]]
}
# aaPanel's updater has been observed to report success while both tasks stop.
if ! probe_backend https && ! probe_backend http; then
  /etc/init.d/bt start >/dev/null 2>&1 || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if probe_backend https || probe_backend http; then break; fi
    sleep 2
  done
fi
if [[ -f $root/data/ssl.pl ]]; then expected=https; else expected=http; fi
if ! probe_backend "$expected"; then
  log "Panel backend not healthy with configured $expected transport; leaving proxy untouched"
  exit 1
fi
# Only modify known bootstrap-managed panel proxy lines.
count=$(grep -Ec '^[[:space:]]*proxy_pass[[:space:]]+https?://127\.0\.0\.1:[0-9]+;' "$vhost" || true)
[[ $count == 1 ]] || { log "Unexpected panel vhost proxy structure; manual review required"; exit 1; }
stamp=$(date -u +%Y%m%dT%H%M%SZ)
backupdir=/root/jq-aapanel-guard-backups
install -d -m 700 "$backupdir"
changed=0
backup_vhost=""
backup_nginx=""
active=$(grep -Ec '^[[:space:]]*lua_package_path[[:space:]]+' "$ngconf" || true)
if [[ $active == 1 ]] && ! "$bin" -t >/dev/null 2>&1; then
  diagnostic=$("$bin" -t 2>&1 || true)
  if grep -Fq 'unknown directive "lua_package_path"' <<< "$diagnostic"; then
    # Never silently disable an installed Lua WAF or Lua-dependent vhosts.
    if grep -RIEq '^[[:space:]]*(lua_shared_dict|.*_by_lua(_file)?|include[[:space:]]+.*(luawaf|btwaf|free_waf))' "$ngconf" "$root/vhost/nginx" --include='*.conf' 2>/dev/null; then
      log "Active Lua/WAF directives present: refusing automatic bypass"
      exit 1
    fi
    backup_nginx=$backupdir/nginx.conf.$stamp
    cp -p "$ngconf" "$backup_nginx"
    python3 - "$ngconf" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
lines=s.splitlines(keepends=True)
hits=[i for i,l in enumerate(lines) if l.lstrip().startswith('lua_package_path ')]
assert len(hits)==1
i=hits[0];lines[i]='# jq-guard: Nginx binary lacks Lua support; '+lines[i]
p.write_text(''.join(lines))
PY
    changed=1
    log "Disabled one unsupported Lua path directive, backup $backup_nginx"
  fi
fi
wrong="proxy_pass $([[ $expected == https ]] && echo http || echo https)://127.0.0.1:$port;"
correct="proxy_pass $expected://127.0.0.1:$port;"
if grep -Fq "$wrong" "$vhost"; then
  backup_vhost=$backupdir/panel-vhost.$stamp
  cp -p "$vhost" "$backup_vhost"
  python3 - "$vhost" "$wrong" "$correct" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
assert s.count(sys.argv[2])==1
p.write_text(s.replace(sys.argv[2],sys.argv[3]))
PY
  changed=1
  log "Aligned aaPanel reverse proxy with $expected backend; backup $backup_vhost"
fi
if ! "$bin" -t >/dev/null 2>&1; then
  [[ -z $backup_vhost ]] || cp -p "$backup_vhost" "$vhost"
  [[ -z $backup_nginx ]] || cp -p "$backup_nginx" "$ngconf"
  log "Nginx configuration test failed: rolled back guarded changes"
  exit 1
fi
# aaPanel's sysv init returns error for 'already running'; correct its LSB status.
init=/etc/init.d/nginx
if [[ -f $init ]]; then
  python3 - "$init" "$backupdir" "$stamp" <<'PY'
from pathlib import Path
import sys,shutil
p=Path(sys.argv[1]);s=p.read_text()
old='echo "$NAME (pid `pidof $NAME`) already running."\n\t\t\t\texit 1'
if s.count(old)==2:
  shutil.copy2(p,Path(sys.argv[2])/('nginx.init.'+sys.argv[3]))
  p.write_text(s.replace(old,old[:-1]+'0',1))
  print('Patched LSB already-running exit status')
PY
fi
# Preserve an active master; repair systemd's stale failed/inactive state.
if systemctl is-active --quiet nginx; then
  if (( changed )); then "$bin" -s reload || { log "Nginx reload failed"; exit 1; }; fi
else
  systemctl daemon-reload
  systemctl reset-failed nginx 2>/dev/null || true
  systemctl start nginx || { log "Nginx service start failed"; exit 1; }
  if (( changed )); then "$bin" -s reload || true; fi
fi
status=$(/usr/bin/curl --noproxy '*' -sS --connect-timeout 3 --max-time 8 --resolve "$domain:443:127.0.0.1" -A "$ua" -o /dev/null -w '%{http_code}' "https://$domain/login" 2>/dev/null || true)
if [[ $status != 200 ]]; then
  log "Panel public reverse proxy local check returned HTTP $status"
  exit 1
fi
log "Healthy: $domain aaPanel=$expected, Nginx service active, login HTTP 200"
