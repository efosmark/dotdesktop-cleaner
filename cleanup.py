#!/usr/bin/env python
from functools import cache
from pathlib import Path
import io, os, sys
import shutil, shlex
import configparser
import subprocess
import time

import logging
logging.basicConfig(format='%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__file__)
logger.setLevel(logging.WARNING)

DEFAULT_EDITOR = 'nano'
SEARCH_DIRS = [
    
    # User level apps and .desktop overrides
    "~/.local/share/applications/",
    "~/.gnome/apps/",
    "~/.var/app/",
    
    # Auto-start apps
    "~/.config/autostart/", 
    "/etc/xdg/autostart/",
    
    # System apps
    "/usr/share/applications/",
    "/usr/share/gnome/applications/",
    "/usr/share/applications/",
    "/usr/local/share/applications/",
    "/usr/share/kservices5/",
    
    # Containerized apps
    "/var/lib/snapd/desktop/applications/",
    "/var/lib/flatpak/exports/share/applications/",
    "/var/lib/flatpak/exports/bin/",
    
    # Sessions
    "/usr/share/xsessions/",
    "/usr/local/share/xsessions/",
    "/usr/share/wayland-sessions/",
    "/usr/local/share/wayland-sessions/"
]

class Entry:
    location:str|Path
    reason:str|None = None
    exec:str|None = None
    full_exec:str|None = None
    def __init__(self, location:str|Path):
        self.location = location

def find_broken_desktop_files() -> list[Entry]:
    broken = []
    config = configparser.ConfigParser(interpolation=None)
    for d in {Path(d).expanduser().resolve() for d in SEARCH_DIRS}:
        for f in d.glob(f"*.desktop"):
            entry = Entry(d.joinpath(f))
            try:
                config.read(entry.location)
                entry.full_exec = config["Desktop Entry"]["Exec"].strip()
                command = shlex.split(entry.full_exec)
                
                if command[0].lower() == 'env':
                    entry.exec = [c for c in command[1:] if '=' not in c][0]
                else:
                    entry.exec = command[0]
                
                if entry.exec.startswith('/') or entry.exec.startswith('~'):
                    if not os.path.exists(entry.exec):
                        entry.reason = "Executable does not exist."
                        broken.append(entry)
                elif shutil.which(entry.exec) is None:
                    entry.reason = "Executable not found in $PATH."
                    broken.append(entry)
            except configparser.Error as e:
                    entry.reason = e.message.split('\n', 1)[0]
                    broken.append(entry)
            except KeyError as e:
                    entry.reason = "No [Desktop Entry].Exec entry found."
                    broken.append(entry)
    return broken

def start_privilaged():
    while True:
        entry = sys.stdin.readline().strip()
        if ' ' not in entry:
            sys.stdout.write("Must be in the form '[CMD] ...\\n'\n")
            sys.stdout.flush()
            continue
        command, entry = entry.split(' ', 1)
        if command == 'UNLINK':
            if not entry.endswith(".desktop"):
                sys.stdout.write(f"ERR Must be a .desktop file.\n")
                sys.stdout.flush()
                continue
            Path(entry).unlink()
            sys.stdout.write(f"UNLINK {entry} SUCCESS\n")
            sys.stdout.flush()
        else:
            sys.stdout.write(f"ERR Unknown: {command=} {entry=}\n")
            sys.stdout.flush()

@cache
def privilaged_subprocess():
    return subprocess.Popen([
            "pkexec", 
            sys.executable,
            Path(__file__).absolute(),
            "--privilaged"
        ],
        stdout=subprocess.PIPE,
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        text=True
    )

def edit_file(filename:str|Path) -> int:
    logger.debug('EDIT %s', filename)
    args = [os.getenv("EDITOR", DEFAULT_EDITOR), filename ]
    if not os.access(filename, os.W_OK, effective_ids=True):
        logger.debug('No permission. Requesting privilages...')
        args = ["pkexec", *args]
    
    sys.stdout, sys.stdin = io.StringIO(), io.StringIO()
    returncode = subprocess.Popen(
        args,
        stdout=sys.__stdout__,
        stdin=sys.__stdin__,
        stderr=sys.__stderr__
    ).wait()
    time.sleep(0.5)
    sys.stdout, sys.stdin = sys.__stdout__, sys.__stdin__
    
    logger.debug("External editor return code %s", returncode)
    return returncode

def remove_file(filename:str|Path):
    logger.debug('UNLINK %s', filename)
    try:
        Path(filename).unlink()
        return True
    except PermissionError:
        logger.debug("Not enough permission to unlink. Sending to privilaged subprocess.")
        p = privilaged_subprocess()
        
        command = f"UNLINK {filename}"
        if p.stdin is not None:
            logger.debug("--> %s", command)
            p.stdin.write(f'{command}\n')
        if p.stdout is not None:
            ret = p.stdout.readline().strip()
            logger.debug("<-- %s", ret)
            if not ret.endswith("SUCCESS"):
                logger.error("Failed to unlink file. %s", ret)
                return False
            return True

def find_and_fix():
    entries = find_broken_desktop_files()
    if len(entries) == 0:
        print("No broken .desktop files were found.")
        return
    
    delete_count = 0
    edit_count = 0
    for entry in entries:
        print()
        try:
            print(f'╭─ ~/{Path(entry.location).relative_to(Path.home())}')
        except ValueError:
            print(f'╭─ {entry.location}')
        print('│')
        if entry.full_exec is not None:
            print(f'├─ Exec String {entry.full_exec}')
        if entry.full_exec != entry.exec:
            print(f'├─ Executable  {entry.exec}',)
        print(f'├─ Problem     {entry.reason}')
        print(f'│')
        
        resp = input("╰─ [d]elete, [e]dit, [q]uit, or [i]gnore (default):").lower()
        if resp in ('q', 'quit'):
            break
        elif resp in ('e', 'edit'):
            if edit_file(entry.location) == 0:
                edit_count += 1
        elif resp in ('d', 'delete'):
            if remove_file(entry.location):
                delete_count += 1
    print()
    print(f"{len(entries)} potentially bad .desktop files were found.")
    if delete_count > 0:
        print(f"{delete_count} deleted.")
    if edit_count > 0:
        print(f"{edit_count} edited.")
    print()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description='Searches the various XDG .desktop file directories, looking for '
                    'files that are malformed or have bad `Exec` entries.',
        epilog='Be careful and review each entry. MIT License.'
    )
    parser.add_argument("--privilaged",
                        help=argparse.SUPPRESS,
                        action="store_true")
    parser.add_argument("--verbose",
                        help="Show debugging messages",
                        action="store_true")
    args = parser.parse_args()
    
    if args.verbose and not args.privilaged:
        logger.setLevel(logging.DEBUG)
    
    if args.privilaged:
        start_privilaged()
    else:
        find_and_fix()