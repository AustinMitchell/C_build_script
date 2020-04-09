# C Build Script

A Script to make simple C/C++ executable projects. requires Python 3.

The script has some expectations:
- All dependencies of executable can be discovered through the -MM options of your compiler
- All source files intended to be included in the executable have a header file of the same base name and same directory structure, and their headers will be discovered in the dependency list of your main source file

If your project satisfied these two requirements, this script should work.

The script has the following usage:
```
usage: make.py [-h] [--config CONFIG] {build,clean}
```
It takes one positional argument for the action to take, and one flag argument for the config file which will control how make.py builds your program. The config file is a YAML file. Here is an example config file:

```yml
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
```

| Flag              | Description |
| ----              | :- |
| COMPILER          | Compiler executable name |
| FLAGS             | Extra flags to pass to compiler |
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
