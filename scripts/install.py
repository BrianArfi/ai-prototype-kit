#!/usr/bin/env python3
"""Install the kit into a Claude Code project.

    python scripts/install.py /path/to/your-project
    python scripts/install.py .              # the current folder
    python scripts/install.py . --force      # replace commands that already exist

It does three things:
1. Copies the kit to <project>/.claude/skills/ai-prototype-kit/, unless it already runs from there.
2. Copies commands/*.md to <project>/.claude/commands/, so /mockup, /deck, /artifact,
   /publish and /revise-from-comments work. An existing command with the same name is
   kept unless you pass --force.
3. Adds .kit-build/ to <project>/.gitignore.

Standard library only.
"""
import argparse
import os
import shutil
import sys

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = {'.git', '__pycache__', 'node_modules', '.kit-build', '.wrangler', 'state'}


def main():
    ap = argparse.ArgumentParser(description='Install the AI Prototype Kit into a Claude Code project.')
    ap.add_argument('project', help='the project folder')
    ap.add_argument('--force', action='store_true', help='overwrite existing commands with the same name')
    a = ap.parse_args()

    project = os.path.abspath(os.path.expanduser(a.project))
    if not os.path.isdir(project):
        sys.exit(f'{project} is not a folder.')
    target = os.path.join(project, '.claude', 'skills', 'ai-prototype-kit')

    if os.path.normcase(os.path.abspath(target)) != os.path.normcase(KIT):
        if os.path.exists(target):
            shutil.rmtree(target)
        shutil.copytree(KIT, target, ignore=shutil.ignore_patterns(*SKIP, '*.pyc'))
        print(f'kit copied to {target}')
    else:
        print(f'kit already at {target}')

    cmd_dir = os.path.join(project, '.claude', 'commands')
    os.makedirs(cmd_dir, exist_ok=True)
    for name in sorted(os.listdir(os.path.join(KIT, 'commands'))):
        if not name.endswith('.md'):
            continue
        dest = os.path.join(cmd_dir, name)
        if os.path.exists(dest) and not a.force:
            print(f'  kept your existing /{name[:-3]} (pass --force to replace it)')
            continue
        shutil.copyfile(os.path.join(KIT, 'commands', name), dest)
        print(f'  /{name[:-3]}')

    ignore = os.path.join(project, '.gitignore')
    lines = open(ignore, encoding='utf-8').read().splitlines() if os.path.isfile(ignore) else []
    if '.kit-build/' not in lines:
        with open(ignore, 'a', encoding='utf-8', newline='\n') as fh:
            fh.write(('\n' if lines and lines[-1] else '') + '.kit-build/\n')
        print('  .kit-build/ added to .gitignore')

    print('\nDone. In Claude Code, run /mockup and describe the flow.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
