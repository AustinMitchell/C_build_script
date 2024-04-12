#!python3

from subprocess import Popen, PIPE, STDOUT
from typing import List, Tuple, Any, Generator, Set, Dict
from pathlib import Path
import shutil
import os
import sys
import yaml
import argparse
import re


class Config:
    """
    Contains the configurations required for building. Takes in an argument dict and converts the arguments to more practical forms
    """

    COMPILER: str
    COMPILER_FLAGS: str
    LINKER_FLAGS: str

    EXE_DIR: str
    EXE_FILE: str

    # Can be a glob. If it's a glob and there's multiple mains(), SKIP_LINKER should be enabled.
    SOURCE_MAIN: str

    SOURCE_DIR: str
    SOURCE_EXT: str
    HEADER_DIR: str
    HEADER_EXT: str
    OBJECT_DIR: str
    OBJECT_EXT: str

    OTHER_INCLUDE_PATHS: str
    OTHER_LIB_PATHS: str

    RESOURCES: Dict[Path, Path]

    DEPEND_MAPPING: Dict[Path, List[Path]]

    COMPILATION_DATABASE: bool

    # Skips linking stage.
    SKIP_LINKER: bool

    @classmethod
    def construct(cls, configuration: Dict[str, Any]):
        """
        Sets the global configuration for this build. The README contains a description of the arguments.
        """

        def _get_default(arg: str, default):
            return configuration[arg] if arg in configuration else default

        # required args
        Config.COMPILER = configuration["COMPILER"]
        Config.SOURCE_MAIN = configuration["SOURCE_MAIN"]

        # non-required args
        Config.COMPILER_FLAGS = _get_default("COMPILER_FLAGS", "")
        Config.LINKER_FLAGS = _get_default("LINKER_FLAGS", "")

        Config.SOURCE_DIR = _get_default("SOURCE_DIR", "src/")
        Config.SOURCE_EXT = _get_default("SOURCE_EXT", "cpp")

        Config.HEADER_DIR = _get_default("HEADER_DIR", "include/")
        Config.HEADER_EXT = _get_default("HEADER_EXT", "hpp")

        Config.OBJECT_DIR = _get_default("OBJECT_DIR", "build/")
        Config.OBJECT_EXT = _get_default("OBJECT_EXT", "o")

        Config.EXE_DIR = _get_default("EXE_DIR", "bin/")
        Config.EXE_FILE = _get_default("EXE_FILE", "a.out")

        Config.OTHER_INCLUDE_PATHS = _get_default("OTHER_INCLUDE_PATHS", [])
        Config.OTHER_INCLUDE_PATHS = " ".join(["-I" + p for p in Config.OTHER_INCLUDE_PATHS])

        Config.OTHER_LIB_PATHS = _get_default("OTHER_LIB_PATHS", [])
        Config.OTHER_LIB_PATHS = " ".join(["-L" + p for p in Config.OTHER_LIB_PATHS])

        if "RESOURCES" in configuration:
            Config.RESOURCES = {Path(in_file): Path(out_file) for in_file, out_file in configuration["RESOURCES"].items()}
        else:
            Config.RESOURCES = {}

        if "DEPEND_MAPPING" in configuration:
            Config.DEPEND_MAPPING = {Path(header): [Path(source) for source in source_list] for header, source_list in configuration["DEPEND_MAPPING"].items()}
        else:
            Config.DEPEND_MAPPING = {}

        Config.COMPILATION_DATABASE = _get_default("COMPILATION_DATABASE", False)

        Config.SKIP_LINKER = _get_default("SKIP_LINKER", False)


class Colour:
    """ Wraps ANSI colour codes in an object for type-checking """
    def __init__(self, val):
        self.val = val


class Style:
    """ Wraps ANSI style codes in an object for type-checking """
    def __init__(self, val):
        self.val = val


class Colours:
    """ ANSI code colour constants """
    NIL = Colour('')          # No change
    BLK = Colour('\033[90m')  # Black
    RED = Colour('\033[91m')  # Red
    GRN = Colour('\033[92m')  # Green
    YLW = Colour('\033[93m')  # Yellow
    BLU = Colour('\033[94m')  # Blue
    MGT = Colour('\033[95m')  # Magenta
    CYN = Colour('\033[96m')  # Cyan
    WHT = Colour('\033[97m')  # White


class Styles:
    """ ANSI code style constants """
    NIL = Style('')         # No change
    END = Style('\033[0m')  # Remove all changes (including color)
    BLD = Style('\033[1m')  # Bold
    ULN = Style('\033[4m')  # Underlined
    ALL = Style('\033[1m\033[4m')  # Bold+underlined


def colour_print(message: str,
                 colour: Colour = Colours.NIL,
                 style: Style = Styles.NIL,
                 reset: bool = True,
                 **kwargs) -> None:
    """
    Prints a message with the given colour and style, if your shell supports ANSI codes
    """
    reset_color = Styles.END.val if reset else ''
    print(f"{colour.val}{style.val}{message}{reset_color}", **kwargs)


def merge_compilation_database():
    """
    Merges compilation commands into one compilation database
    """
    result = ""
    for json_path in Path(Config.OBJECT_DIR).glob("*.json"):
        with open(json_path, 'r') as json_file:
            result += json_file.read()

    comma_idx = result.rfind(",")
    result = "[\n" + result[:comma_idx] + result[comma_idx+1:] + "\n]"

    with open('compile_commands.json', 'w') as output_file:
        output_file.write(result)


def copy_if_outdated(source: Path, dest: Path, depth: int = 0) -> None:
    """
    Compares all files in source directory and checks if they are newer than the same files in the destination. If they are, they
    are copied to the destination.
    """

    if not source.exists():
        return

    if not dest.exists():
        if source.is_dir():
            colour_print(f"    Copying folder {str(source)} to {str(dest)}...", colour=Colours.YLW)
            shutil.copytree(str(source), str(dest))
        else:
            colour_print(f"    Copying file {str(source)} to {str(dest)}...", colour=Colours.YLW)
            shutil.copy2(str(source), str(dest))
    else:
        if source.is_file() and source.stat().st_mtime > dest.stat().st_mtime:
            colour_print(f"    Copying file {str(source)} to {str(dest)}...", colour=Colours.YLW)
            shutil.copy2(str(source), str(dest))
        else:
            for f in source.glob("*"):
                copy_if_outdated(f, dest.joinpath(f.name), depth+1)


def shell(cmd: str, stdout=PIPE) -> Popen:
    """
    Executes a command on the shell using Popen and returns the object created
    """

    return Popen(cmd, shell=True, stdin=PIPE, stdout=stdout, stderr=STDOUT)


def test_source(source: Path, dependencies: List[Path]) -> bool:
    """
    Checks to see if source file needs to be built
    """

    # constructs object file name from source file name
    object_file = source_to_object(source)

    build_required = False
    source_mtime = source.stat().st_mtime

    if os.path.exists(object_file):
        object_mtime = object_file.stat().st_mtime
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
        # Object file hasn't been made, we need to compile
        build_required = True

    return build_required


def source_files() -> List[Tuple[Path, bool]]:
    """
    Creates a generator of all files in the project with the source extension set in the config, and determines if they need building
    """
    checked_deps: Set[Path] = set()
    deps: Set[Path] = set()
    sources: List[Tuple[Path, bool]] = []

    for init_source_path in Path(Config.SOURCE_DIR).joinpath(Config.SOURCE_MAIN).parent.glob(Path(Config.SOURCE_MAIN).name):
        new_deps = list(generate_dependencies(init_source_path))
        sources.append((init_source_path, test_source(init_source_path, new_deps)))
        deps.update(new_deps)

    while deps:
        current_dep = deps.pop()
        if current_dep in checked_deps:
            continue

        checked_deps.add(current_dep)

        # If this header has specified source files, use the mapping
        if current_dep in Config.DEPEND_MAPPING:
            for current_source in Config.DEPEND_MAPPING[current_dep]:
                if os.path.exists(current_source):
                    new_deps = generate_dependencies(current_source)
                    sources.append((current_source, test_source(current_source, list(new_deps))))
                    deps.update(new_deps)
        else:
            # Otherwise assume there is a file with the same name and path as the header
            current_source = header_to_source(current_dep)

            if os.path.exists(current_source):
                new_deps = generate_dependencies(current_source)
                sources.append((current_source, test_source(current_source, list(new_deps))))
                deps.update(new_deps)

    return sources


def header_to_source(header: Path) -> Path:
    """
    Takes in a path to a header file and produces a path to where a corresponding source file should be
    """
    return Path(Config.SOURCE_DIR).joinpath(Path(header).relative_to(Config.HEADER_DIR).parent, f"{Path(header).stem}.{Config.SOURCE_EXT}")


def source_to_object(source: Path) -> Path:
    """
    Takes in a path to a source file and produces a path to where a corresponding object file should be
    """
    return Path(Config.OBJECT_DIR).joinpath(Path(source).relative_to(Config.SOURCE_DIR).parent, f"{Path(source).stem}.{Config.OBJECT_EXT}")


def generate_dependencies(file: Path) -> Generator[Path, None, None]:
    """
    Generates a list of non-system dependencies to a source file using -MM
    """

    # This will create a string of all the non-system dependencies for our source file separated by spaces
    cmd = f"{Config.COMPILER} {Config.OTHER_INCLUDE_PATHS} -MM -I{Config.HEADER_DIR} {file}"
    deps = re.findall(r"\S+\.hpp", str(shell(cmd, stdout=PIPE).stdout.read()))

    return (Path(dep) for dep in deps)


def build():
    """
    Starts off the building process
    """

    # Builds dependency tree. Adding (0, mainHeader) guarantees that the list follows
    # the rules specified in the function documentation
    object_building_success = True
    linking_required = False
    compiled_with_warnings = False
    check_resources = False

    for (source, needs_building) in source_files():
        if needs_building:
            (compiled, has_warnings) = build_object(source)
            if compiled:
                linking_required = True
                compiled_with_warnings = compiled_with_warnings or has_warnings
            else:
                object_building_success = False
                break
        else:
            colour_print(f"Skipping (up to date):                {source_to_object(source)}", colour=Colours.GRN)

    # if we've built any new files
    if Config.COMPILATION_DATABASE and linking_required:
        colour_print("Merging compilation database into compile_commands.json...", colour=Colours.WHT)
        merge_compilation_database()

    if not object_building_success:
        colour_print("\nBuilding failed!", colour=Colours.YLW, style=Styles.BLD)
        colour_print("Skipping executable generation", colour=Colours.YLW, style=Styles.BLD)
        colour_print("------------------------------", colour=Colours.YLW)
    else:
        print("")
        exe_full_path = Path(Config.EXE_DIR).joinpath(Config.EXE_FILE)
        if not linking_required and not os.path.exists(exe_full_path):
            linking_required = True
            # colour_print(f"The file {exe_full_path} doesn't exist.", colour=colours.MGT, style=styles.BLD)

        if linking_required and not Config.SKIP_LINKER:
            # Build exe location folders
            Path(Path(Config.EXE_DIR)).mkdir(parents=True, exist_ok=True)

            cmd = f"{Config.COMPILER} {Config.OTHER_LIB_PATHS} {Config.LINKER_FLAGS} -o {exe_full_path} {' '.join((str(source_to_object(s)) for (s, b) in source_files()))}"

            colour_print("Generating executable... ", colour=Colours.CYN, style=Styles.BLD)
            colour_print("Running: ", colour=Colours.CYN, style=Styles.BLD, end='')
            colour_print(cmd, colour=Colours.WHT)

            ret = shell(cmd)
            ret.wait()

            msg = ret.stdout.readlines()

            if msg:
                for line in msg:
                    print(f"\t{line.decode(sys.stdout.encoding)}", end='')

            print()

            if ret.returncode != 0:
                colour_print("Compilation failed", colour=Colours.RED, style=Styles.BLD)
                colour_print("------------------", colour=Colours.RED)
            else:
                if compiled_with_warnings:
                    colour_print("Compilation succeeded with warnings", colour=Colours.YLW, style=Styles.BLD)
                    colour_print("---------------------", colour=Colours.YLW)
                else:
                    colour_print("Compilation succeeded", colour=Colours.BLU, style=Styles.BLD)
                    colour_print("---------------------", colour=Colours.BLU)

                check_resources = True
        else:
            if Config.SKIP_LINKER:
                colour_print("\nConfig.SKIP_LINKER is set", colour=Colours.GRN, style=Styles.BLD)
                colour_print("Skipping executable generation", colour=Colours.GRN, style=Styles.BLD)
                colour_print("------------------------------", colour=Colours.GRN)
            else:
                # Skips building if nothing was updated.
                colour_print("\nEverything up to date!", colour=Colours.GRN, style=Styles.BLD)
                colour_print("Skipping executable generation", colour=Colours.GRN, style=Styles.BLD)
                colour_print("------------------------------", colour=Colours.GRN)

                check_resources = True

    if check_resources and Config.RESOURCES:
        colour_print("")
        colour_print("Updating resource files ", colour=Colours.WHT, style=Styles.BLD)
        for in_file, out_folder in Config.RESOURCES.items():
            colour_print(f"Checking {in_file}...", colour=Colours.WHT)
            for matched_file in Path(".").glob(str(in_file)):
                copy_if_outdated(matched_file, Path(Config.EXE_DIR).joinpath(out_folder, matched_file.name))


def build_object(source_file: Path) -> Tuple[bool, bool]:
    """
    Compiles the given source file and directs it to the given object file location.
    If the path for the object file doesn't exist, a new directory structure will be created for it.
    """

    object_file = source_to_object(source_file)

    # If object file dir is missing, make it
    Path(Path(object_file).parent).mkdir(parents=True, exist_ok=True)

    compile_command_path = Path(Config.OBJECT_DIR).joinpath(f"{'-'.join(source_file.parts)}.json")
    compile_command = f"-MJ {compile_command_path}" if Config.COMPILATION_DATABASE else ""

    cmd = f"{Config.COMPILER} -fdiagnostics-color=always {Config.COMPILER_FLAGS} {compile_command} -c -I{Config.HEADER_DIR} {Config.OTHER_INCLUDE_PATHS} {source_file} -o {object_file}"
    colour_print("Running: ", style=Styles.BLD, end='')
    colour_print(cmd)

    ret = shell(cmd)
    ret.wait()

    msg = ret.stdout.readlines()

    if msg:
        for line in msg:
            print(f"\t{line.decode(sys.stdout.encoding)}", end='')
        print()

    return ret.returncode == 0, len(msg) > 0


def execute(action: str):
    """
    Executes build based on configuration
    """

    print("")
    colour_print("Configuration", style=Styles.ALL)
    colour_print("    EXE directory:    ", colour=Colours.YLW, style=Styles.BLD, end='')
    colour_print(Config.EXE_DIR, colour=Colours.YLW)
    colour_print("    EXE file:         ", colour=Colours.YLW, style=Styles.BLD, end='')
    colour_print(Config.EXE_FILE, colour=Colours.YLW)

    colour_print("    Source main file: ", colour=Colours.GRN, style=Styles.BLD, end='')
    colour_print(Config.SOURCE_MAIN, colour=Colours.GRN)
    colour_print("    Source directory: ", colour=Colours.GRN, style=Styles.BLD, end='')
    colour_print(Config.SOURCE_DIR, colour=Colours.GRN)
    colour_print("    Source extension: ", colour=Colours.GRN, style=Styles.BLD, end='')
    colour_print(Config.SOURCE_EXT, colour=Colours.GRN)

    colour_print("    Header directory: ", colour=Colours.CYN, style=Styles.BLD, end='')
    colour_print(Config.HEADER_DIR, colour=Colours.CYN)
    colour_print("    Header extension: ", colour=Colours.CYN, style=Styles.BLD, end='')
    colour_print(Config.HEADER_EXT, colour=Colours.CYN)

    colour_print("    Object directory: ", colour=Colours.BLU, style=Styles.BLD, end='')
    colour_print(Config.OBJECT_DIR, colour=Colours.BLU)
    colour_print("    Object extension: ", colour=Colours.BLU, style=Styles.BLD, end='')
    colour_print(Config.OBJECT_EXT, colour=Colours.BLU)

    colour_print("    Other includes:   ", colour=Colours.MGT, style=Styles.BLD, end='')
    colour_print(Config.OTHER_INCLUDE_PATHS, colour=Colours.MGT)

    colour_print("    Header mappings:  ", colour=Colours.MGT, style=Styles.BLD)
    for header, source_list in Config.DEPEND_MAPPING.items():
        colour_print(f"        {header} -> ", colour=Colours.MGT, end='')
        space_padding = len(f"        {str(header)} -> ")
        for i, source in enumerate(source_list):
            if i == 0:
                colour_print(f"{str(source)}", colour=Colours.MGT)
            else:
                colour_print(f"{' '*space_padding}{str(source)}", colour=Colours.MGT)

    colour_print("    Compiler:         ", colour=Colours.RED, style=Styles.BLD, end='')
    colour_print(Config.COMPILER, colour=Colours.RED)
    colour_print("    Compiler flags:   ", colour=Colours.RED, style=Styles.BLD, end='')
    colour_print(Config.COMPILER_FLAGS, colour=Colours.RED)
    colour_print("    Linker flags:     ", colour=Colours.RED, style=Styles.BLD, end='')
    colour_print(Config.LINKER_FLAGS, colour=Colours.RED)

    colour_print("    Resources:        ", colour=Colours.YLW, style=Styles.BLD)
    for s in (f"        {in_file} -> {Path(Config.EXE_DIR).joinpath(out_file)}" for in_file, out_file in Config.RESOURCES.items()):
        colour_print(s, colour=Colours.YLW)

    colour_print("")
    colour_print("Running target ", colour=Colours.WHT, end='')
    colour_print(action, colour=Colours.WHT, style=Styles.BLD)

    if action == "build":
        build()

    elif action == "clean":
        exe_full_path = Path(Config.EXE_DIR).joinpath(Config.EXE_FILE)
        if os.path.exists(Config.OBJECT_DIR):
            colour_print("Removing " + Config.OBJECT_DIR + "...", colour=Colours.MGT)
            shutil.rmtree(Config.OBJECT_DIR)
        if os.path.exists(exe_full_path):
            colour_print(f"Removing {exe_full_path}...", colour=Colours.MGT)
            os.remove(exe_full_path)

    print("")


def parse_config(file):
    """
    Sets up config based on yaml config file, and executes build with given action
    """

    colour_print("Constructing configuration from file ", end='')
    # colour_print(args.config, style=styles.BLD)
    config_file = yaml.safe_load(file.read())
    Config.construct(config_file)


def parse_dict(configuration: Dict[str, str]):
    """
    Sets up config based on configuration dict, and executes build with given action
    """

    colour_print("Constructing configuration from dictionary")
    # colour_print(str(configuration), style=styles.BLD)
    Config.construct(configuration)


def main():
    """
    Main entry point when running this file as a script. Argparse expects two parameters:
        --target
            Operation to perform, currently supports build or clean.
        --config
            YAML file containing build configurations for this run. This is required for cleaning or building, since the configuration
            stores the paths for the object files and bin folder which will be deleted on cleaning.
    """

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--target", required=True, choices=['build', 'clean'])
    arg_parser.add_argument("--config", required=True, type=str)
    args = arg_parser.parse_args(args=sys.argv[1:])

    if not os.path.exists(args.config):
        colour_print(f"File '{args.config}' does not exist. Aborting.", colour=Colours.RED, style=Styles.BLD, end='')
        sys.exit(1)

    with open(args.config) as f:
        parse_config(f)

    execute(args.target)


if __name__ == "__main__":
    main()
