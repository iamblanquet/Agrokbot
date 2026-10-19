"""Keep only the active Campo release. Dry run by default; run as root on server."""
import argparse
import json
from pathlib import Path
import re
import subprocess


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    repo = Path('/home/mblanquet/Agrokbot')
    containers = json.loads(run('docker', 'inspect', *run('docker', 'ps', '-aq').split()))
    active = next(c for c in containers if c['Name'] == '/agrokbot-campo-1')
    assert active['State'].get('Health', {}).get('Status') == 'healthy', 'Active container must be healthy'
    active_path = Path(active['Config']['Labels']['com.docker.compose.project.working_dir']).resolve()
    assert active_path == repo.resolve() or (active_path.parent == repo.parent and active_path.name.startswith('Agrokbot-release-'))
    protected = {active_path, repo.resolve()}
    for c in containers:
        labels = c['Config'].get('Labels') or {}
        if labels.get('com.docker.compose.project.working_dir'):
            protected.add(Path(labels['com.docker.compose.project.working_dir']).resolve())
        for mount in c.get('Mounts', []):
            protected.add(Path(mount['Source']).resolve())
    used_images = {c['Image'] for c in containers}
    worktrees = run('git', '-C', str(repo), 'worktree', 'list', '--porcelain')
    for line in worktrees.splitlines():
        if not line.startswith('worktree '):
            continue
        path = Path(line[9:])
        if path.is_symlink() or path.resolve().parent != repo.parent or not re.fullmatch(r'Agrokbot-release-[0-9a-f]{7,40}', path.name):
            continue
        if any(p == path.resolve() or path.resolve() in p.parents for p in protected):
            continue
        # Never discard modified/untracked work or ignored data. Only env copies
        # and generated Python bytecode are disposable within an old release.
        dirty = run('git', '-C', str(path), 'status', '--porcelain')
        ignored = run('git', '-C', str(path), 'ls-files', '--others', '--ignored', '--exclude-standard').splitlines()
        unexpected = [p for p in ignored if p != '.env' and not (p.endswith('.pyc') and '__pycache__/' in p)]
        if dirty or unexpected:
            print('PRESERVED (local changes/data):', path)
            continue
        print('REMOVE release:', path)
        if args.apply:
            subprocess.run(['git', '-C', str(repo), 'worktree', 'remove', '--force', str(path)], check=True)
    images = run('docker', 'image', 'ls', '--format', '{{.Repository}}:{{.Tag}}').splitlines()
    for tag in images:
        if not re.fullmatch(r'agrokbot-campo:rollback-[0-9a-f]+', tag):
            continue
        image_id = run('docker', 'image', 'inspect', tag, '--format', '{{.Id}}')
        if image_id in used_images:
            continue
        print('REMOVE image:', tag)
        if args.apply:
            subprocess.run(['docker', 'image', 'rm', tag], check=True)
    print('ACTIVE:', active_path)


if __name__ == '__main__':
    main()
