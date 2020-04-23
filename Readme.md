# C Build Script

A Script to make simple C/C++ executable projects. requires Python 3.

The script has some expectations:
- All dependencies of executable can be discovered through the -MM options of your compiler
- All source files intended to be included in the executable have a header file of the same base name and same directory structure, and their headers will be discovered in a dependency tree generated from your main source file
- If a header files is sourced by a file that does not have the same name or is sourced by multiple files, that mapping is listed int he configuration

If your project satisfied these requirements, this script should work.

The script has the following usage:
```
usage: make.py [-h] [--config CONFIG] {build,clean}
```
It takes one positional argument for the action to take, and one flag argument for the config file which will control how `make.py` builds your program. The config file is a YAML file.

### Config Example

```yml
COMPILER: "clang++"
COMPILER_FLAGS: "-std=c++17 -Wall -Wextra"
LINKER_FLAGS: "-lpthread"

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

RESOURCES:
    ./res/images: images

DEPEND_MAPPING:
    helper.hpp:
        - helper-part1.cpp
        - helper-part2.cpp
```

### Flag Description Table
| Flag              | Description |
| ----              | :- |
| COMPILER          | Compiler executable name |
| COMPILER_FLAGS    | Extra flags to pass to compiler |
| LINKER_FLAGS      | Flags to pass to the linker |
| EXE_DIR           | Directory to place exectuable |
| EXE_FILE          | Name of exectuable within directoy |
| SOURCE_MAIN       | Name of source containing main function within directory |
| SOURCE_DIR        | Name of folder containing source files |
| SOURCE_EXT        | Source file extension |
| HEADER_DIR        | Name of folder containing header files |
| HEADER_EXT        | Header file extension |
| OBJECT_DIR        | Name of folder to place object files |
| OBJECT_EXT        | Object file extension |
| OTHER_INCLUDES    | Other directories to include in compilation |
| RESOURCES         | Object mapping "in" to "out" for resource directory inputs/outputs. Output is relative to EXE_DIR. Build script will only copy files that don't exist to out or files that are out of date. Useful for managing text files and images, for instance |
| DEPEND_MAPPING    | Object mapping header files to one or more source files that supply definitions for declarations in the header file |

### Building from other scripts

The build script can be invoked from another python script by supplying a dictionary with the required flags. For example:

```python
#!/usr/bin/python3

import C_build_script.make as make

def main():
        config = {
            "COMPILER": "clang++"
            "COMPILER_FLAGS": "-std=c++17 -Wall -Wextra"
            "LINKER_FLAGS": "-lpthread"

            "EXE_DIR": "./bin"
            "EXE_FILE": "a.out"

            "SOURCE_MAIN": "main.cc"
            "SOURCE_DIR": "./src/"
            "SOURCE_EXT": "cc"
            "HEADER_DIR": "./include/"
            "HEADER_EXT": "h"
            "OBJECT_DIR": "./build/"
            "OBJECT_EXT": "o"

            "OTHER_INCLUDES": "-I./lib/"

            "RESOURCES": [{"in":"./res/", "out":"res"}]
        }

        # Sets the config for the make script
        make.parse_dict(config)
        # Executes based on the config
        make.execute("build")


if __name__ == "__main__":
    main()
```
