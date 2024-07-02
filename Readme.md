# C Build Script

A script to build simple C/C++ executable projects. Requires Python 3 and PyYAML. With the correct configuration and project structure, this script automatically discovers dependencies. Like `make`, it will only build outdated object files and executables.

## Requirements
- Python 3
- PyYAML if you want to be able to load from file, otherwise it's unneeded.
    - `pip3 install --user pyaml`

## Overview
The script has some expectations:
- All dependencies of executable can be discovered through the `-MM` options of your compiler
- All source files intended to be included in the executable have a header file of the same base name and same directory structure, and their headers will be discovered in a dependency tree generated from your main source file. E.g. if you have a source file named `src_dir_name/subfolder1/subfolder2/source.cpp`, it's expected there is a header file named `include_dir_name/subfolder1/subfolder2/source.hpp`, with source/include dir and extensions defined in the config.
- If a header files is sourced by a file that does not have the same name or is sourced by multiple files, that mapping is listed in the configuration under `DEPEND_MAPPING`

If your project satisfied these requirements, this script should work.

The script has the following usage:
```
usage: make.py [-h] --target {build,clean} --config CONFIG
```
It takes one flag argument for the action to take, and one flag argument for the config file which will control how `make.py` builds your program. The config file is a YAML file.

## Config Example
```yml
COMPILER: "clang++"
COMPILER_FLAGS: "-std=c++17 -Wall -Wextra"
LINKER_FLAGS: "-lpthread"

EXE_DIR:  "./bin"
EXE_FILE: "a.out"

SOURCE_MAIN: "main.cc"
SOURCE_DIR:  "./src/"
SOURCE_EXT:  "cc"
HEADER_DIR:  "./include/"
HEADER_EXT:  "h"
OBJECT_DIR:  "./build/"
OBJECT_EXT:  "o"

# array of include paths
OTHER_INCLUDE_PATHS:
    - lib1/include
    - lib2/include

# array of library paths
OTHER_LIB_PATHS:
    - lib1/bin
    - lib2/bin

# All files in res/images/ will be places in /bin/dir/images/
# All dll files found recursively within lib will be placed directly in bin/
RESOURCES:
    "./res/images": "dir/"
    "./lib/**/*.dll": ""

# part1 and part2 contribute to defining functions laid out in helper.hpp, thus form a dependency tree. Necessary if your source-to-header dependencies
# aren't directly solveable just by their names
DEPEND_MAPPING:
    helper.hpp:
        - helper-part1.cpp
        - helper-part2.cpp

COMPILATION_DATABASE: true
SKIP_LINKER: false
```

### Flag Description Table
| Flag                  | Description |
| ----                  | :- |
| COMPILER              | Compiler executable name |
| COMPILER_FLAGS        | Extra flags to pass to compiler |
| LINKER_FLAGS          | Flags to pass to the linker |
| EXE_DIR               | Directory to place exectuable |
| EXE_FILE              | Name of exectuable within directoy |
| SOURCE_MAIN           | Initial seed file to discover dependencies from relative to `SOURCE_DIR`. Can contain wildcards. If wildcards are selected and multiple `main()` definitions are possible, you should enable SKIP_LINKER as well. |
| SOURCE_DIR            | Name of folder containing source files |
| SOURCE_EXT            | Source file extension |
| HEADER_DIR            | Name of folder containing header files |
| HEADER_EXT            | Header file extension |
| OBJECT_DIR            | Name of folder to place object files |
| OBJECT_EXT            | Object file extension |
| OTHER_INCLUDE_PATHS   | Array of extra header file directories to include in compilation (it will use the `-I` flag internally) |
| OTHER_LIB_PATHS       | Array of extra library directories to include in linking (it will use the `-L` flag internally) |
| RESOURCES             | Object mapping "in" to "out" for resource directory inputs/outputs. Output is relative to EXE_DIR. Build script will only copy files that don't exist to out or files that are out of date. Useful for managing text files and images, for instance |
| DEPEND_MAPPING        | Object mapping header files to one or more source files that supply definitions for declarations in the header file. Normally a header will look for a source file with the same directory structure and base name, but this means if a header is a dependency and its listed in `DEPEND_MAPPING`, it will use this list of files to compile. |
| COMPILATION_DATABASE  | Enables building a compilation database. Creates an entry for each object compiled. If any new files are built, the database is recompiled. |
| SKIP_LINKER           | If enabled, skips the linking step. Useful if you want to build a compilation database for a bunch of source files at once and your source contains multiple `main()` |

### Building from other scripts
The build script can be invoked from another python script by supplying a dictionary with the required flags. For example, following our previous YAML example:

```python
#!/usr/bin/python3

import argparse
import C_build_script.make as make
import shutil
import os
import sys

from pathlib import Path


def main():

    argparser = argparse.ArgumentParser()
    argparser.add_argument("-s", action='store', type=str, metavar="SOURCE",    help="Source file to generate executable from")
    argparser.add_argument("-o", action='store', type=str, metavar="EXE NAME",  help="Executable output name")
    argparser.add_argument("-a", action='store_true', help="Build all and skip linking")
    argparser.add_argument("-d", action='store_true', help="Sets build to debug mode")
    argparser.add_argument("-c", action='store_true', help="Cleans all output files")
    args = argparser.parse_args()

    if args.c:
        if os.path.exists("bin"):
            print("Removing 'bin/'")
            shutil.rmtree("bin")
        if os.path.exists("objects"):
            print("Removing 'objects/'")
            shutil.rmtree("objects")
        if os.path.exists("objects-debug"):
            print("Removing 'objects-debug/'")
            shutil.rmtree("objects-debug")

    # If you want to make a header depend on some files named differently, example in above docs
    dependency_mapping = {

    }

    # If you want to copy resources into the bin directory
    resource_mappings = {

    }

    if args.s or args.a:
        # Sets glob to all *.cpp files in src if -a flag
        # Otherwise, take the source file and chop off src/
        source_main = "*.cpp" if args.a else Path(args.s).relative_to("src")
        config = {
            "COMPILER":             "clang++",
            "LINKER_FLAGS":         "-pthread",
            "SOURCE_DIR":           "src/",
            "SOURCE_MAIN":          source_main,
            "RESOURCES":            resource_mappings,
            "DEPEND_MAPPING":       dependency_mapping,
            "COMPILATION_DATABASE": True,
            # globs for source_main should skip linker to avoid multiple main linkage
            "SKIP_LINKER":          True if "*" in str(source_main) else False
        }

        if args.d:
            config["COMPILER_FLAGS"] = "-std=c++23 -Wall -Wextra -Wpedantic -g -O0 -DDEBUG -Wno-language-extension-token"
            config["LINKER_FLAGS"] += " -g"
            config["OBJECT_DIR"] = "./objects-debug/"
            config["EXE_FILE"] = "prog-debug"
        else:
            config["COMPILER_FLAGS"] = "-std=c++23 -Wall -Wextra -Wpedantic -O3 -Wno-language-extension-token"
            config["OBJECT_DIR"] = "./objects/"
            config["EXE_FILE"] = "prog"

        if args.o:
            config["EXE_FILE"] = args.o

        if sys.platform == "win32":
            config["EXE_FILE"] += ".exe"

        make.parse_dict(config)
        make.execute("build")


if __name__ == "__main__":
    main()
```
