#!python3

from subprocess import Popen, PIPE, STDOUT
from typing import List, Tuple, Any, Generator, Iterator, Set, Dict
from pathlib import Path
import shutil
import os
import sys
import io
import argparse
import re



class config:
    """
    Contains all of the configurations required for building. Takes in an argument dict and converts the arguments to more practical forms
    """

    COMPILER:str
    COMPILER_FLAGS:str
    LINKER_FLAGS:str

    EXE_DIR: str
    EXE_FILE: str

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

    @classmethod
    def construct(cls, configuration: Dict[str, Any]):
        """
        Sets the global configuration for this build. The README contains a descrtiption of all of the arguments.
        """

        def get_default(arg:str, default):
            return configuration[arg] if arg in configuration else default

        # required args
        config.COMPILER    = configuration["COMPILER"]
        config.SOURCE_MAIN = configuration["SOURCE_MAIN"]

        # non-required args
        config.COMPILER_FLAGS = get_default("COMPILER_FLAGS", "")
        config.LINKER_FLAGS   = get_default("LINKER_FLAGS", "")

        config.SOURCE_DIR = get_default("SOURCE_DIR", "src/")
        config.SOURCE_EXT = get_default("SOURCE_EXT", "cpp")

        config.HEADER_DIR = get_default("HEADER_DIR", "include/")
        config.HEADER_EXT = get_default("HEADER_EXT", "hpp")

        config.OBJECT_DIR = get_default("OBJECT_DIR", "build/")
        config.OBJECT_EXT = get_default("OBJECT_EXT", "o")

        config.EXE_DIR  = get_default("EXE_DIR", "bin/")
        config.EXE_FILE = get_default("EXE_FILE", "a.out")

        config.OTHER_INCLUDE_PATHS = get_default("OTHER_INCLUDE_PATHS", [])
        config.OTHER_INCLUDE_PATHS = " ".join(["-I"+p for p in config.OTHER_INCLUDE_PATHS])

        config.OTHER_LIB_PATHS = get_default("OTHER_LIB_PATHS", [])
        config.OTHER_LIB_PATHS = " ".join(["-L"+p for p in config.OTHER_LIB_PATHS])

        if "RESOURCES" in configuration:
            config.RESOURCES = {Path(in_file):Path(out_file) for in_file, out_file in configuration["RESOURCES"].items()}
        else:
            config.RESOURCES = {}

        if "DEPEND_MAPPING" in configuration:
            config.DEPEND_MAPPING = {Path(header):[Path(source) for source in source_list] for header, source_list in configuration["DEPEND_MAPPING"].items()}
        else:
            config.DEPEND_MAPPING = {}



class Colour:
    """ Wraps ANSI colour codes in an object for typechecking """
    def __init__(self, val):
        self.val = val


class Style:
    """ Wraps ANSI style codes in an object for typechecking """
    def __init__(self, val):
        self.val = val




class colours:
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




class styles:
    """ ANSI code style constants """
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




def copy_if_outdated(source:Path, dest:Path, depth:int=0) -> None:
    """
    Compares all files in source directory and checks if they are newer than the same files in the destination. If they are, they
    are copied to the destination.
    """

    if not source.exists():
        return

    if not dest.exists():
        if source.is_dir():
            colour_print(f"    Copying folder {str(source)} to {str(dest)}...", colour=colours.YLW)
            shutil.copytree(str(source), str(dest))
        else:
            colour_print(f"    Copying file {str(source)} to {str(dest)}...", colour=colours.YLW)
            shutil.copy2(str(source), str(dest))
    else:
        if source.is_file() and source.stat().st_mtime > dest.stat().st_mtime:
            colour_print(f"    Copying file {str(source)} to {str(dest)}...", colour=colours.YLW)
            shutil.copy2(str(source), str(dest))
        else:
            for f in source.glob("*"):
                copy_if_outdated(f, dest.joinpath(f.name), depth+1)




def shell(cmd: str, stdout=None) -> Popen:
    """
    Executes a command on the shell using Popen and returns the object created
    """

    return Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT)




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

        # If this header has specified source files, use the mapping
        if current_dep in config.DEPEND_MAPPING:
            for current_source in config.DEPEND_MAPPING[current_dep]:
                if os.path.exists(current_source):
                    new_deps = generate_dependencies(current_source)
                    sources.append((current_source, test_source(current_source, list(new_deps))))
                    deps.extend(new_deps)
        else:
            # Otherwise assume there is a file with the same name and path as the header
            current_source = header_to_source(current_dep)

            if os.path.exists(current_source):
                new_deps = generate_dependencies(current_source)
                sources.append((current_source, test_source(current_source, list(new_deps))))
                deps.extend(new_deps)

    return sources




def header_to_source(header:Path) -> Path:
    """
    Takes in a path to a header file and produces a path to where a corresponding source file should be
    """
    return Path(config.SOURCE_DIR).joinpath(Path(header).relative_to(config.HEADER_DIR).parent, f"{Path(header).stem}.{config.SOURCE_EXT}")


def source_to_object(source:Path) -> Path:
    """
    Takes in a path to a source file and produces a path to where a corresponding object file should be
    """
    return Path(config.OBJECT_DIR).joinpath(Path(source).relative_to(config.SOURCE_DIR).parent, f"{Path(source).stem}.{config.OBJECT_EXT}")




def generate_dependencies(file: Path) -> Generator[Path, None, None]:
    """
    Generates a list of non-system dependencies to a source file using -MM
    """

    # This will create a string of all the non-system dependencies for our source file separated by spaces
    cmd = f"{config.COMPILER} {config.OTHER_INCLUDE_PATHS} -MM -I{config.HEADER_DIR} {file}"
    deps = re.findall(r"\S+\.hpp", str(shell(cmd, stdout=PIPE).stdout.read()))

    return (Path(dep) for dep in deps)




def build():
    """
    Starts off the building process
    """


    #   Builds dependency tree. Adding (0, mainHeader) guarantees that the list follows
    # the rules specified in the function documentation
    object_building_success = True
    linking_required        = False
    compiled_with_warnings  = False
    check_resources         = False

    # print("")
    # print(f"Sources: {' '.join(str(s) for s in source_files())}")
    # print(f"Objects: {' '.join(str(source_to_object(s)) for (s,b) in source_files())}")
    # print("")

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
            #colour_print(f"The file {exe_full_path} doesn't exist.", colour=colours.MGT, style=styles.BLD)

        if linking_required:
            # Build exe location folders
            Path(Path(config.EXE_DIR)).mkdir(parents=True, exist_ok=True)

            cmd = (f"{config.COMPILER} {config.OTHER_LIB_PATHS} {config.LINKER_FLAGS} -o {exe_full_path} {' '.join((str(source_to_object(s)) for (s,b) in source_files()))}")

            colour_print("Generating executable... ", colour=colours.CYN, style=styles.BLD)
            colour_print("Running: ", colour=colours.CYN, style=styles.BLD, end='')
            colour_print(cmd, colour=colours.WHT)

            ret = shell(cmd)
            ret.wait()

            msg = ret.stdout.readlines()

            if (msg):
                for line in msg:
                    print(f"\t{line.decode(sys.stdout.encoding)}", end='')

            print()

            if ret.returncode != 0:
                colour_print("Compilation failed", colour=colours.RED, style=styles.BLD)
                colour_print("------------------", colour=colours.RED)
            else:
                if compiled_with_warnings:
                    colour_print("Compilation succeeded with warnings", colour=colours.YLW, style=styles.BLD)
                    colour_print("---------------------", colour=colours.YLW)
                else:
                    colour_print("Compilation succeeded", colour=colours.BLU, style=styles.BLD)
                    colour_print("---------------------", colour=colours.BLU)

                check_resources = True

        else:
            # Skips building if nothing was updated.
            colour_print("\nEverything up to date!",       colour=colours.GRN, style=styles.BLD)
            colour_print("Skipping executable generation", colour=colours.GRN, style=styles.BLD)
            colour_print("------------------------------", colour=colours.GRN)

            check_resources = True

    if check_resources and config.RESOURCES:
        colour_print("")
        colour_print("Updating resource files ", colour=colours.WHT, style=styles.BLD)
        for in_file, out_folder in config.RESOURCES.items():
            colour_print(f"Checking {in_file}...", colour=colours.WHT)
            for matched_file in Path(".").glob(str(in_file)):
                copy_if_outdated(matched_file, Path(config.EXE_DIR).joinpath(out_folder, matched_file.name))




def build_object(source_file:Path) -> Tuple[bool, bool]:
    """
    Compiles the given source file and directs it to the given object file location.
    If the path for the object file doesn't exist, a new directory structure will be created for it.
    """

    object_file = source_to_object(source_file)

    # If object file dir is missing, make it
    Path(Path(object_file).parent).mkdir(parents=True, exist_ok=True)

    cmd = f"{config.COMPILER} -fdiagnostics-color=always {config.COMPILER_FLAGS} -c -I{config.HEADER_DIR} {config.OTHER_INCLUDE_PATHS} {source_file} -o {object_file}"
    colour_print("Running: ", style=styles.BLD, end='')
    colour_print(cmd)

    ret = shell (cmd)
    ret.wait()

    msg = ret.stdout.readlines()

    if (msg):
        for line in msg:
            print(f"\t{line.decode(sys.stdout.encoding)}", end='')
        print()

    return (ret.returncode == 0, len(msg)>0)




def execute(action:str):
    """
    Executes build based on configuration
    """

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
    colour_print(config.OTHER_INCLUDE_PATHS, colour=colours.MGT)

    colour_print("    Header mappings:  ", colour=colours.MGT, style=styles.BLD)
    for header, source_list in config.DEPEND_MAPPING.items():
        colour_print(f"        {header} -> ", colour=colours.MGT, end='')
        space_padding = len(f"        {str(header)} -> ")
        for i, source in enumerate(source_list):
            if i==0:
                colour_print(f"{str(source)}", colour=colours.MGT)
            else:
                colour_print(f"{' '*space_padding}{str(source)}", colour=colours.MGT)

    colour_print("    Compiler:         ", colour=colours.RED, style=styles.BLD, end='')
    colour_print(config.COMPILER, colour=colours.RED)
    colour_print("    Compiler flags:   ", colour=colours.RED, style=styles.BLD, end='')
    colour_print(config.COMPILER_FLAGS, colour=colours.RED)
    colour_print("    Linker flags:     ", colour=colours.RED, style=styles.BLD, end='')
    colour_print(config.LINKER_FLAGS, colour=colours.RED)

    colour_print("    Resources:        ", colour=colours.YLW, style=styles.BLD)
    for s in (f"        {in_file} -> {Path(config.EXE_DIR).joinpath(out_file)}" for in_file, out_file in config.RESOURCES.items()):
        colour_print(s,  colour=colours.YLW)

    colour_print("")
    colour_print("Running target ", colour=colours.WHT, end='')
    colour_print(action, colour=colours.WHT, style=styles.BLD)

    if action == "build":
        build()

    elif action == "clean":
        exe_full_path = Path(config.EXE_DIR).joinpath(config.EXE_FILE)
        if os.path.exists(config.OBJECT_DIR):
            colour_print("Removing " + config.OBJECT_DIR + "...", colour=colours.MGT)
            shutil.rmtree(config.OBJECT_DIR)
        if os.path.exists(exe_full_path):
            colour_print(f"Removing {exe_full_path}...",   colour=colours.MGT)
            os.remove(exe_full_path)

    print("")




def parse_config(file):
    """
    Sets up config based on yaml config file, and executes build with given action
    """
    import yaml
    colour_print("Constructing configuration from file ", end='')
    # colour_print(args.config, style=styles.BLD)
    config_file = yaml.safe_load(file.read())
    config.construct(config_file)


def parse_dict(configuration:Dict[str, str]):
    """
    Sets up config based on configuration dict, and executes build with given action
    """

    colour_print("Constructing configuration from dictionary")
    # colour_print(str(configuration), style=styles.BLD)
    config.construct(configuration)




def main():
    """
    Main entry point when running this file as a script. Argparse expects two parameters:
        --target
            Operation to perform, currently supports build or clean.
        --config
            YAML file containing build configurations for this run. This is required for cleaning or building, since the configuration
            stores the paths for the object files and bin folder which will be deleted on cleaning.
    """

    argparser = argparse.ArgumentParser()
    argparser.add_argument("--target", required=True, choices=['build', 'clean'])
    argparser.add_argument("--config", required=True, type=str)
    args = argparser.parse_args(args=sys.argv[1:])

    if not os.path.exists(args.config):
        colour_print(f"File '{args.config}' does not exist. Aborting.", colour=colours.RED, style=styles.BLD, end='')
        sys.exit(1)

    with open(args.config) as f:
        parse_config(f)

    execute(args.target)


if __name__ == "__main__":
    main()