# C Build Script

A script to build simple C/C++ executable projects. Requires Python 3 and PyYAML.

The script has some expectations:
- All dependencies of executable can be discovered through the -MM options of your compiler
- All source files intended to be included in the executable have a header file of the same base name and same directory structure, and their headers will be discovered in a dependency tree generated from your main source file
- If a header files is sourced by a file that does not have the same name or is sourced by multiple files, that mapping is listed int the configuration

If your project satisfied these requirements, this script should work.

The script has the following usage:
```
usage: make.py [-h] --target {build,clean} --config CONFIG
```
It takes one flag argument for the action to take, and one flag argument for the config file which will control how `make.py` builds your program. The config file is a YAML file.

### Config Example

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
```

### Flag Description Table
| Flag                  | Description |
| ----                  | :- |
| COMPILER              | Compiler executable name |
| COMPILER_FLAGS        | Extra flags to pass to compiler |
| LINKER_FLAGS          | Flags to pass to the linker |
| EXE_DIR               | Directory to place exectuable |
| EXE_FILE              | Name of exectuable within directoy |
| SOURCE_MAIN           | Name of source containing main function within directory |
| SOURCE_DIR            | Name of folder containing source files |
| SOURCE_EXT            | Source file extension |
| HEADER_DIR            | Name of folder containing header files |
| HEADER_EXT            | Header file extension |
| OBJECT_DIR            | Name of folder to place object files |
| OBJECT_EXT            | Object file extension |
| OTHER_INCLUDE_PATHS   | Array of extra header file directories to include in compilation (it will use the -I flag internally) |
| OTHER_LIB_PATHS       | Array of extra library directories to include in linking (it will use the -L flag internally) |
| RESOURCES             | Object mapping "in" to "out" for resource directory inputs/outputs. Output is relative to EXE_DIR. Build script will only copy files that don't exist to out or files that are out of date. Useful for managing text files and images, for instance |
| DEPEND_MAPPING        | Object mapping header files to one or more source files that supply definitions for declarations in the header file |

### Building from other scripts

The build script can be invoked from another python script by supplying a dictionary with the required flags. For example, following our previous YAML example:

```python
#!/usr/bin/python3

import C_build_script.make as make

def main():
    config = {
        "COMPILER": "clang++",
        "COMPILER_FLAGS": "-std=c++17 -Wall -Wextra",
        "LINKER_FLAGS": "-lpthread",

        "EXE_DIR": "./bin",
        "EXE_FILE": "a.out",

        "SOURCE_MAIN": "main.cc",
        "SOURCE_DIR": "./src/",
        "SOURCE_EXT": "cc",
        "HEADER_DIR": "./include/",
        "HEADER_EXT": "h",
        "OBJECT_DIR": "./build/",
        "OBJECT_EXT": "o",

        "OTHER_INCLUDE_PATHS": ["lib1/include", "lib2/include"],
        "OTHER_LIB_PATHS":     ["lib1/bin", "lib2/bin"],

        "RESOURCES": {
            "./res/images": "dir",
            "./lib/**/*.dll": "",
        },

        "DEPEND_MAPPING": [
            {"helper.hpp": ["helper-part1.cpp",
                            "helper-part2.cpp"]}
        ],
    }

    # Sets the config for the make script
    make.parse_dict(config)
    # Executes based on the config
    make.execute("build")


if __name__ == "__main__":
    main()
```
