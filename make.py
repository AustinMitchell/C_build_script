from subprocess import Popen, PIPE, STDOUT
from typing import List, Tuple, Any, Generator, Iterator, Set, Dict
from pathlib import Path
import shutil
import os
import sys
import yaml
import io
import argparse
import re


DEFAULT_CONFIG = """\
COMPILER: "clang++"
FLAGS: "-std=c++17 -Wall -Wextra"

EXE_DIR: "./bin"
EXE_FILE: "a.out"

SOURCE_MAIN: "main.cc"
SOURCE_DIR: "./src/"
SOURCE_EXT: "cc"
HEADER_DIR: "./include/"
HEADER_EXT: "h"
OBJECT_DIR: "./build/"
OBJECT_EXT: "o"

OTHER_INCLUDES: "-I./lib/"
"""

class config:
    COMPILER:str
    FLAGS:str

    EXE_DIR: str
    EXE_FILE: str

    SOURCE_MAIN: str

    SOURCE_DIR: str
    SOURCE_EXT: str
    HEADER_DIR: str
    HEADER_EXT: str
    OBJECT_DIR: str
    OBJECT_EXT: str

    OTHER_INCLUDES: str

    MAIN_SOURCE: str
    MAIN_HEADER: str
    MAIN_OBJECT: str

    @classmethod
    def construct(cls, input):
        config_file = yaml.safe_load(input.read())
        print(config_file)

        config.COMPILER = config_file["COMPILER"]
        config.FLAGS = config_file["FLAGS"]

        config.EXE_DIR  = config_file["EXE_DIR"]
        config.EXE_FILE = config_file["EXE_FILE"]

        config.SOURCE_MAIN = config_file["SOURCE_MAIN"]

        config.SOURCE_DIR = config_file["SOURCE_DIR"]
        config.SOURCE_EXT = config_file["SOURCE_EXT"]
        config.HEADER_DIR = config_file["HEADER_DIR"]
        config.HEADER_EXT = config_file["HEADER_EXT"]
        config.OBJECT_DIR = config_file["OBJECT_DIR"]
        config.OBJECT_EXT = config_file["OBJECT_EXT"]

        config.OTHER_INCLUDES = config_file["OTHER_INCLUDES"]


class Colour:
    def __init__(self, val):
        self.val = val


class Style:
    def __init__(self, val):
        self.val = val


class colours:
    NIL = Colour('')          # No change
    BLK = Colour('\033[90m')  # Black
    RED = Colour('\033[91m')  # Red
    GRN = Colour('\033[92m')  # Green
    YLW = Colour('\033[93m')  # Yellow
    BLU = Colour('\033[94m')  # Blue
    MGT = Colour('\033[95m')  # Magenta
    CYN = Colour('\033[96m')  # Cyan
    WHT = Colour('\033[97m')  # White


class styles:
    NIL = Style('')         # No change
    END = Style('\033[0m')  # Remove all changes (including color)
    BLD = Style('\033[1m')  # Bold
    ULN = Style('\033[4m')  # Underlined
    ALL = Style('\033[1m\033[4m')  # Bold+underlined


def colour_print(message: str,
                 colour: Colour = colours.NIL,
                 style: Style = styles.NIL,
                 reset: bool = True,
                 **kwargs) -> None:
    """
    Prints a message with the given colour and style, if your shell supports ANSI codes
    """
    resetColor = styles.END.val if reset else ''
    print(f"{colour.val}{style.val}{message}{resetColor}", **kwargs)



def shell(cmd: str, stdout=None) -> Popen:
    """
    Executes a command on the shell using Popen and returns the object created
    """

    return Popen(cmd, shell=True, stdin=PIPE, stdout=stdout, stderr=None)


def test_source(source:Path, dependencies:List[Path]) -> bool:
    """
    Checks to see if source file needs to be built
    """

    # constructs object file name from source file name
    objectfile = source_to_object(source)

    build_required = False
    source_mtime = source.stat().st_mtime

    if os.path.exists(objectfile):
        object_mtime = objectfile.stat().st_mtime
        if object_mtime < source_mtime:
            # Source is newer than object file, compile
            build_required = True
        else:
            # Check if any dependencies are newer than object file
            for dep in dependencies:
                if object_mtime < dep.stat().st_mtime:
                    # Dependency is newer than object file, compile
                    build_required = True
                    break
    else:
        # Objectfile hasnt been made, we need to compile
        build_required = True

    return build_required

def source_files() -> List[Tuple[Path, bool]]:
    """
    Creates a generator of all files in the project with the source extension set in the config, and detemines if they need building
    """
    init_source:  Path                    = Path(config.SOURCE_DIR, config.SOURCE_MAIN)
    deps:         List[Path]              = list(generate_dependencies(init_source))
    sources:      List[Tuple[Path, bool]] = [(init_source, test_source(init_source, deps))]
    checked_deps: Set[Path]               = set()

    while(deps):
        current_dep = deps.pop(0)
        if current_dep in checked_deps:
            continue

        checked_deps.add(current_dep)
        current_source = header_to_source(current_dep)

        if os.path.exists(current_source):
            new_deps = generate_dependencies(current_source)
            sources.append((current_source, test_source(current_source, list(new_deps))))
            deps.extend(new_deps)

    return sources


def header_to_source(header:Path) -> Path:
    return Path(config.SOURCE_DIR).joinpath(Path(header).relative_to(config.HEADER_DIR).parent, f"{Path(header).stem}.{config.SOURCE_EXT}")

def source_to_object(source:Path) -> Path:
    return Path(config.OBJECT_DIR).joinpath(Path(source).relative_to(config.SOURCE_DIR).parent, f"{Path(source).stem}.{config.OBJECT_EXT}")

def generate_dependencies(file: Path) -> Generator[Path, None, None]:
    """
    Generates a list of non-system dependencies to a source file using -MM
    """

    # This will create a string of all the non-system dependencies for our source file separated by spaces
    cmd = f"{config.COMPILER} {config.FLAGS} -MM -I{config.HEADER_DIR} {file}"
    deps = re.findall(r"\S+\.hpp", str(shell(cmd, stdout=PIPE).stdout.read()))

    return (Path(dep) for dep in deps)


def build():
    """ Starts off the building process """


    #   Builds dependency tree. Adding (0, mainHeader) guarantees that the list follows
    # the rules specified in the function documentation
    object_building_success = True
    linking_required = False

    print("")
    print(f"Sources: {' '.join(str(s) for s in source_files())}")
    print(f"Objects: {' '.join(str(source_to_object(s)) for (s,b) in source_files())}")
    print("")

    for (source, needs_building) in source_files():
        if needs_building:
            if build_object(source):
                linking_required = True
            else:
                object_building_success = False
                break
        else:
            colour_print(f"Skipping (up to date):                {source_to_object(source)}", colour=colours.GRN)

    if not object_building_success:
        colour_print("\nBuilding failed!",             colour=colours.YLW, style=styles.BLD)
        colour_print("Skipping executable generation", colour=colours.YLW, style=styles.BLD)
        colour_print("------------------------------", colour=colours.YLW)
    else:
        print("")
        exe_full_path = Path(config.EXE_DIR).joinpath(config.EXE_FILE)
        if not linking_required and not os.path.exists(exe_full_path):
            linking_required = True
            colour_print(f"The file {exe_full_path} doesn't exist.", colour=colours.MGT, style=styles.BLD)

        if linking_required:
            # Build exe location folders
            Path(Path(config.EXE_DIR)).mkdir(parents=True, exist_ok=True)

            cmd = (f"{config.COMPILER} {config.FLAGS} -o {exe_full_path} {' '.join((str(source_to_object(s)) for (s,b) in source_files()))}")

            colour_print("Generating executable... ", colour=colours.CYN, style=styles.BLD)
            colour_print("Running: ", colour=colours.CYN, style=styles.BLD, end='')
            colour_print(cmd, colour=colours.CYN)
            print("")

            ret = shell(cmd)
            ret.wait()

            if ret.returncode != 0:
                colour_print("Compilation failed", colour=colours.RED, style=styles.BLD)
                colour_print("------------------", colour=colours.RED)
            else:
                colour_print("Compilation succeeded", colour=colours.BLU, style=styles.BLD)
                colour_print("---------------------", colour=colours.BLU)

        else:
            # Skips building if nothing was updated.
            colour_print("\nEverything up to date!",       colour=colours.GRN, style=styles.BLD)
            colour_print("Skipping executable generation", colour=colours.GRN, style=styles.BLD)
            colour_print("------------------------------", colour=colours.GRN)


def build_object(source_file:Path) -> int:
    """
    Compiles the given source file and directs it to the given object file location.
    If the path for the object file doesn't exist, a new directory structure will be created for it.
    """

    object_file = source_to_object(source_file)

    # If object file dir is missing, make it
    Path(Path(object_file).parent).mkdir(parents=True, exist_ok=True)

    cmd = f"{config.COMPILER} {config.FLAGS} -c -I{config.HEADER_DIR} {config.OTHER_INCLUDES} {source_file} -o {object_file}"
    colour_print("Running: ", style=styles.BLD, end='')
    colour_print(cmd)

    ret = shell (cmd)
    ret.wait()

    return ret.returncode == 0


if __name__ == "__main__":

    argparser = argparse.ArgumentParser()
    argparser.add_argument("target", choices=['build', 'clean'])
    argparser.add_argument("--config", required=False, type=str)
    args = argparser.parse_args()

    if args.config:
        if not os.path.exists(args.config):
            colour_print(f"File '{args.config}' does not exist. Aborting.", colour=colours.RED, style=styles.BLD, end='')
            sys.exit(1)

        colour_print("Constructing configuration from file ", end='')
        colour_print(args.config, style=styles.BLD)
        with open(args.config) as f:
            config.construct(f)
    else:
        colour_print("Constructing configuration from DEFAULT_CONFIG")
        with io.StringIO() as f:
            f.write(DEFAULT_CONFIG)
            f.seek(0)
            config.construct(f)

    print("")
    colour_print("Configuration", style=styles.ALL)
    colour_print("    EXE directory:    ", colour=colours.YLW, style=styles.BLD, end='')
    colour_print(config.EXE_DIR,  colour=colours.YLW)
    colour_print("    EXE file:         ", colour=colours.YLW, style=styles.BLD, end='')
    colour_print(config.EXE_FILE, colour=colours.YLW)

    colour_print("    Source main file: ", colour=colours.GRN, style=styles.BLD, end='')
    colour_print(config.SOURCE_MAIN, colour=colours.GRN)
    colour_print("    Source directory: ", colour=colours.GRN, style=styles.BLD, end='')
    colour_print(config.SOURCE_DIR, colour=colours.GRN)
    colour_print("    Source extension: ", colour=colours.GRN, style=styles.BLD, end='')
    colour_print(config.SOURCE_EXT, colour=colours.GRN)

    colour_print("    Header directory: ", colour=colours.CYN, style=styles.BLD, end='')
    colour_print(config.HEADER_DIR, colour=colours.CYN)
    colour_print("    Header extension: ", colour=colours.CYN, style=styles.BLD, end='')
    colour_print(config.HEADER_EXT, colour=colours.CYN)

    colour_print("    Object directory: ", colour=colours.BLU, style=styles.BLD, end='')
    colour_print(config.OBJECT_DIR, colour=colours.BLU)
    colour_print("    Object extension: ", colour=colours.BLU, style=styles.BLD, end='')
    colour_print(config.OBJECT_EXT, colour=colours.BLU)

    colour_print("    Other includes:   ", colour=colours.MGT, style=styles.BLD, end='')
    colour_print(config.OTHER_INCLUDES, colour=colours.MGT)

    colour_print("    Compiler:         ", colour=colours.RED, style=styles.BLD, end='')
    colour_print(config.COMPILER, colour=colours.RED)
    colour_print("    Compiler flags:   ", colour=colours.RED, style=styles.BLD, end='')
    colour_print(config.FLAGS, colour=colours.RED)

    colour_print("")
    colour_print("Running target ", colour=colours.WHT, end='')
    colour_print(args.target, colour=colours.WHT, style=styles.BLD)

    if args.target == "build":
        build()

    elif args.target == "clean":
        exe_full_path = Path(config.EXE_DIR).joinpath(config.EXE_FILE)
        if os.path.exists(config.OBJECT_DIR):
            colour_print("Removing " + config.OBJECT_DIR + "...", colour=colours.MGT)
            shutil.rmtree(config.OBJECT_DIR)
        if os.path.exists(exe_full_path):
            colour_print(f"Removing {exe_full_path}...",   colour=colours.MGT)
            os.remove(exe_full_path)

    print("")