#!/usr/bin/python3
"""Root-owned, fixed-repository nginx publisher. SSH entry point accepts no arguments."""
import contextlib
import datetime
import fcntl
import hashlib
import io
import json
import os
import pathlib
import re
import signal
import subprocess
import sys
import tarfile
import tempfile
import time

P = pathlib.Path
BASE = P('/var/lib/homelab-nginx')
RELEASES = BASE / 'releases'
CURRENT = BASE / 'current'
STATE = BASE / 'state.json'
JOURNAL = BASE / 'pending.json'
AUDIT = P('/var/log/homelab-nginx-deploy.jsonl')
REPO = '/home/alvarense/nginx-sites-available'
REMOTE = 'git@github.com:alvarezallas/nginx-sites-available.git'
REQUIRED = {'00-maps.conf', 'default.conf', 'argocd.conf', 'grafana.conf',
            'prometheus.conf', 'qbittorrent.conf', 'pgadmin.conf', 'semaphore.conf'}
HOSTS = [('bearsfamily.aa', (200,)), ('argocd.bearsfamily.aa', (200,)),
         ('grafana.bearsfamily.aa', (200, 302)), ('prometheus.bearsfamily.aa', (200, 302)),
         ('qbittorrent.bearsfamily.aa', (200,)), ('pgadmin.bearsfamily.aa', (200, 302)),
         ('semaphore.bearsfamily.aa', (200,))]


def run(args, timeout=45, binary=False):
    proc = subprocess.run(args, capture_output=True, text=not binary, timeout=timeout,
                          env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'HOME': '/root',
                               'LANG': 'C.UTF-8'})
    if proc.returncode:
        # Do not log arbitrary nginx config contents or Git output; neither is needed here.
        raise RuntimeError('Command failed: ' + args[0] + ' exit=' + str(proc.returncode))
    return proc.stdout


def git(*args, binary=False):
    return run(['/usr/sbin/runuser', '-u', 'alvarense', '--', '/usr/bin/env',
                'HOME=/home/alvarense', 'GIT_TERMINAL_PROMPT=0',
                'GIT_SSH_COMMAND=/usr/bin/ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=yes',
                '/usr/bin/git', '-c', 'core.hooksPath=/dev/null', '-C', REPO, *args], binary=binary)


def write_json(path, value):
    tmp = path.with_suffix('.tmp')
    with tmp.open('w') as f:
        json.dump(value, f, sort_keys=True)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    fd = os.open(str(path.parent), os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def audit(event, **values):
    record = {'time': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'event': event, **values}
    with AUDIT.open('a') as f:
        f.write(json.dumps(record, sort_keys=True) + '\n')
        f.flush()
        os.fsync(f.fileno())
    print(json.dumps(record, sort_keys=True), flush=True)


def current_sha():
    assert CURRENT.is_symlink(), 'Current release pointer missing'
    dest = CURRENT.resolve(strict=True)
    assert dest.parent == RELEASES and re.fullmatch('[0-9a-f]{40}', dest.name)
    return dest.name


def switch(sha):
    assert re.fullmatch('[0-9a-f]{40}', sha)
    assert (RELEASES / sha).is_dir()
    tmp = BASE / 'current.next'
    with contextlib.suppress(FileNotFoundError):
        tmp.unlink()
    tmp.symlink_to(RELEASES / sha)
    os.replace(tmp, CURRENT)
    fd = os.open(str(BASE), os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def validate_tree(tree):
    files = {p.name for p in tree.glob('*.conf')}
    assert REQUIRED <= files, 'A required service configuration is missing'
    assert (tree / 'welcome.html').is_file()
    assert (tree / 'assets/bear-development.png').is_file()
    default = (tree / 'default.conf').read_text()
    assert 'root /var/lib/homelab-nginx/current;' in default, 'Portal root must use current release'
    assert '/home/alvarense/nginx-sites-available' not in default
    config = P('/etc/nginx/nginx.conf').read_text()
    needle = 'include /etc/nginx/sites-enabled/*;'
    assert config.count(needle) == 1, 'Unexpected global nginx include'
    # Test the complete host config with candidate sites, without changing active symlinks.
    config = config.replace(needle, 'include ' + str(tree / 'sites-enabled/*') + ';')
    with tempfile.NamedTemporaryFile(mode='w', dir=BASE, prefix='validate-', suffix='.conf') as f:
        f.write(config)
        f.flush()
        run(['/usr/sbin/nginx', '-t', '-q', '-c', f.name], timeout=20)


def archive(sha):
    target = RELEASES / sha
    if target.exists():
        validate_tree(target)
        return target
    data = git('archive', '--format=tar', sha, binary=True)
    assert len(data) <= 20 * 1024 * 1024, 'Repository archive exceeds size limit'
    with tempfile.TemporaryDirectory(dir=BASE, prefix='candidate-') as td:
        tree = P(td)
        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            members = tf.getmembers()
            assert len(members) <= 256
            total = 0
            for item in members:
                name = item.name.rstrip('/')
                assert name and not name.startswith('/') and '..' not in P(name).parts
                allowed = (re.fullmatch(r'[a-z0-9-]+\.conf', name) or
                           name in ('README.md', 'welcome.html', 'assets') or
                           re.fullmatch(r'assets/[a-zA-Z0-9_.-]+\.(png|jpg|jpeg|svg|ico|webp|css|js)', name))
                assert allowed, 'Unexpected repository path: ' + name
                path = tree / name
                if item.isdir():
                    assert name == 'assets'
                    path.mkdir(exist_ok=True)
                    continue
                assert item.isfile(), 'Symlinks, devices and submodules are forbidden'
                total += item.size
                assert item.size <= 5 * 1024 * 1024 and total <= 15 * 1024 * 1024
                path.parent.mkdir(parents=True, exist_ok=True)
                with tf.extractfile(item) as src, path.open('wb') as dst:
                    dst.write(src.read())
                path.chmod(0o644)
        enabled = tree / 'sites-enabled'
        enabled.mkdir()
        for p in tree.glob('*.conf'):
            (enabled / p.name).symlink_to('../' + p.name)
        tree.chmod(0o755)
        for p in tree.iterdir():
            if p.is_dir():
                p.chmod(0o755)
        validate_tree(tree)
        # Root-created immutable-to-deploy-user snapshot; same filesystem as pointer.
        os.rename(tree, target)
    return target


def config_digest(sha):
    return hashlib.sha256(b''.join(p.name.encode() + b'\0' + p.read_bytes()
                                 for p in sorted((RELEASES / sha).glob('*.conf')))).hexdigest()


def probes(sha):
    results = {}
    for host, allowed in HOSTS:
        code = run(['/usr/bin/curl', '--silent', '--show-error', '--max-time', '6',
                    '--cacert', '/etc/nginx/tls/homelab.crt', '--resolve', host + ':443:127.0.0.1',
                    '--output', '/dev/null', '--write-out', '%{http_code}', 'https://' + host + '/'], timeout=8)
        assert int(code) in allowed, 'HTTPS health check failed for ' + host
        results[host] = int(code)
    for uri, relative in [('/', 'welcome.html'), ('/assets/bear-development.png', 'assets/bear-development.png')]:
        body = run(['/usr/bin/curl', '--fail', '--silent', '--show-error', '--max-time', '6',
                    '--cacert', '/etc/nginx/tls/homelab.crt', '--resolve', 'bearsfamily.aa:443:127.0.0.1',
                    'https://bearsfamily.aa' + uri], timeout=8, binary=True)
        assert hashlib.sha256(body).digest() == hashlib.sha256((RELEASES / sha / relative).read_bytes()).digest(), 'Portal or logo differs from deployed release'
    return results


def reload_nginx():
    run(['/usr/sbin/nginx', '-t', '-q'], timeout=20)
    run(['/usr/bin/systemctl', 'reload', 'nginx'], timeout=20)
    time.sleep(1)
    run(['/usr/bin/systemctl', 'is-active', '--quiet', 'nginx'])


def recover(boot=False):
    if not JOURNAL.exists():
        return
    pending = json.loads(JOURNAL.read_text())
    old = pending['previous']
    switch(old)
    run(['/usr/sbin/nginx', '-t', '-q'], timeout=20)
    if not boot:
        # Reload even if the interrupted transaction failed before it could record a reload.
        reload_nginx()
        probes(old)
    write_json(STATE, {'applied': old, 'rejected': pending['candidate'], 'recovered': True})
    JOURNAL.unlink()
    audit('recovered-at-boot' if boot else 'recovered', applied=old, rejected=pending['candidate'])


def deploy(sha, explicit=False):
    old = current_sha()
    if sha == old:
        audit('no-change', applied=old, reload=False)
        return
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    if not explicit and state.get('rejected') == sha:
        raise RuntimeError('This commit was rejected; push a fix or use root-only --retry')
    audit('detected', candidate=sha, previous=old)
    try:
        archive(sha)
        probes(old)
    except Exception:
        write_json(STATE, {'applied': old, 'rejected': sha})
        audit('rejected-before-promotion', candidate=sha, applied=old, reload=False)
        raise
    reload_required = config_digest(sha) != config_digest(old)
    write_json(JOURNAL, {'previous': old, 'candidate': sha})
    try:
        switch(sha)
        run(['/usr/sbin/nginx', '-t', '-q'], timeout=20)
        if reload_required:
            reload_nginx()
        result = None
        for attempt in range(3):
            try:
                result = probes(sha)
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2)
        write_json(STATE, {'applied': sha, 'previous': old, 'rejected': None,
                           'updated_at': datetime.datetime.now(datetime.timezone.utc).isoformat()})
        JOURNAL.unlink()
        audit('applied', applied=sha, previous=old, reload=reload_required, https=result)
    except BaseException:
        # Keep the on-disk config valid, not just the old nginx workers.
        recover()
        raise


def main():
    assert os.geteuid() == 0, 'Must run as root'
    os.umask(0o022)
    args = sys.argv[1:]
    assert args == [] or args in (['--recover-boot'], ['--retry']) or (len(args) == 2 and args[0] in ['--rollback-to', '--validate-tree'])
    BASE.mkdir(exist_ok=True, mode=0o755)
    RELEASES.mkdir(exist_ok=True, mode=0o755)
    with open('/run/lock/homelab-nginx-deploy.lock', 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            audit('busy', reload=False)
            return
        if args == ['--recover-boot']:
            recover(boot=True)
            return
        if args and args[0] == '--validate-tree':
            tree = P(args[1]).resolve(strict=True)
            assert tree.is_relative_to(BASE)
            validate_tree(tree)
            audit('candidate-validation-ok')
            return
        recover()
        if args and args[0] == '--rollback-to':
            sha = args[1]
            assert re.fullmatch('[0-9a-f]{40}', sha) and (RELEASES / sha).is_dir()
            deploy(sha, explicit=True)
            return
        assert git('config', '--get', 'remote.origin.url').strip() == REMOTE
        assert git('branch', '--show-current').strip() == 'main'
        assert not git('status', '--porcelain').strip(), 'Local edits exist; deployment stopped'
        git('fetch', '--no-tags', 'origin', 'main')
        sha = git('rev-parse', 'refs/remotes/origin/main').strip()
        assert re.fullmatch('[0-9a-f]{40}', sha)
        git('merge-base', '--is-ancestor', 'HEAD', sha)
        deploy(sha, explicit=args == ['--retry'])
        # Source checkout is useful for manual editing but never serves live traffic now.
        git('merge', '--ff-only', '--no-edit', sha)


if __name__ == '__main__':
    def terminate(signum, frame):
        raise RuntimeError('Deployment interrupted by signal ' + str(signum))
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGHUP, terminate)
    try:
        main()
    except Exception as exc:
        audit('error', error=str(exc)[:250])
        sys.exit(1)
