from subprocess import Popen, PIPE, STDOUT
from typing import List
import shutil
import os
import sys


class config:
    FLAGS = "-std=c++17 -Wall -Wextra"

    EXE_DIR  = "./bin"
    EXE_FILE = "./bin/run.exe"

    SOURCE_DIR = "./src/"
    SOURCE_EXT = ".cc"
    HEADER_DIR = "./include/"
    HEADER_EXT = ".h"
    OBJECT_DIR = "./build/"
    OBJECT_EXT = ".o"

    OTHER_INCLDES = "-I./lib/"

    MAIN_SOURCE = SOURCE_DIR + "main" + SOURCE_EXT
    MAIN_HEADER = HEADER_DIR + MAIN_SOURCE[len(SOURCE_DIR):-len(SOURCE_EXT)] + HEADER_EXT
    MAIN_OBJECT = OBJECT_DIR + MAIN_SOURCE[len(SOURCE_DIR):-len(SOURCE_EXT)] + OBJECT_EXT


class Colour:
    def __init__(self, val):
        self.val = val


class Style:
    def __init__(self, val):
        self.val = val


class colours:
    NIL = Style('')
    BLK = Colour('\033[90m')
    RED = Colour('\033[91m')
    GRN = Colour('\033[92m')
    YLW = Colour('\033[93m')
    BLU = Colour('\033[94m')
    MGT = Colour('\033[95m')
    CYN = Colour('\033[96m')
    WHT = Colour('\033[97m')


class styles:
    NIL = Style('')
    END = Style('\033[0m')
    BLD = Style('\033[1m')
    ULN = Style('\033[4m')


def colour_print(message: str,
                 colour: Colour = colours.NIL,
                 style: Style = styles.NIL,
                 reset: bool = True,
                 **kwargs) -> None:
    """
    Prints a message with the given colour and style, if your shell supports ANSI codes
    """
    resetColor = styles.END.val if reset else ''
    print(colour.val + style.val + message + resetColor, **kwargs)
        


def shell(cmd: str) -> Popen:
    """
    Executes a command on the shell using Popen and returns the object created 
    """
    return Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT)


def dependencies(filePath: str) -> List[str]:
    """ Generates a list of dependencies using g++ -H, only using dependencies from your include
    directory.
    """
    cmd = "g++ " + config.FLAGS + " -H -I" + config.HEADER_DIR + " " + filePath
    deps = [s for s in shell(cmd).stdout.read().split("\n") if len(s) > 0 and s[0] == "."]
    deps = [s.strip() for s in deps if config.HEADER_DIR in s]

    filedeps = []
    for d in deps:
        dSplit = d.split(" ")
        if dSplit[0][len(dSplit[0])-1] == ".":
            filedeps.append((len(dSplit[0]), dSplit[1]))

    return filedeps


def build_dep_tree(depth: int, headerFile: str, deps: List[str]):
    """ Builds a dependency tree, takes in a headerfile name and makes a tree in order of how
    they should be built, using header and source dependencies.
    """
    # Basic tree. First item is the dep name, the second is a list, where each item
    # is a tuple where the first item is a name, and the second is a list. Recursive
    # tree based on a python list.
    tree = [headerFile, []]

    # In this project we assume either header files are stand-alone, or have a
    # corresponding source file which includes the header file, but may also include
    # things that aren't included in the header file, so that stuff needs to be added
    # to the tree so we can see if the source needs building based on ALL dependencies.
    sourceFile = config.SOURCE_DIR + headerFile[len(config.HEADER_DIR):-len(config.HEADER_EXT)] + config.SOURCE_EXT
    sourceDeps = []
    if (os.path.exists(sourceFile)):
        sourceDeps = dependencies(sourceFile)
        sourceDeps = [[d+depth, name] for d, name in sourceDeps]

    # Returns the basic structure if there are no dependencies.
    if not deps and not sourceDeps:
        return tree
    # Returns the basic structure with one dependency if theres only one between the
    # two lists.
    if len(deps)+len(sourceDeps) == 1:
        tree[1].append([(deps+sourceDeps)[0][1], []])
        return tree

    # This is a dictionary whose keys are dependency names, and values are a tuple where
    # the first item is the beginning of the headers dependencies in the list, and the
    # second is the end. Basically just splitting the list into groups, searchable by name
    headerDepSet = {}
    if len(deps) > 0:
        nextDepth = depth+1
        depStart = 0
        i = 1
        for d in deps[1:]:
            currentDepth = d[0]
            if currentDepth <= nextDepth:
                headerDepSet[deps[depStart][1]] = (depStart+1, i+1)
                depStart = i
            i += 1
        headerDepSet[deps[depStart][1]] = (depStart+1, len(deps))

    # This is the same but for source deps.
    sourceDepSet = {}
    if len(sourceDeps) > 0:
        nextDepth = depth+1
        depStart = 0
        i = 1
        for d in sourceDeps[1:]:
            currentDepth = d[0]
            if currentDepth <= nextDepth:
                sourceDepSet[sourceDeps[depStart][1]] = (depStart+1, i+1)
                depStart = i
            i += 1
        sourceDepSet[sourceDeps[depStart][1]] = (depStart+1, len(sourceDeps))

    # Builds a tree based on each dependency found, and they build their own trees
    # based on how we split up the list
    for name in headerDepSet:
        depRange = headerDepSet[name]
        tree[1].append(build_dep_tree(depth+1, name, deps[depRange[0]:depRange[1]]))

    # Same, but only adds in stuff not found in the header.
    for name in sourceDepSet:
        if name not in headerDepSet and not name == headerFile:
            depRange = sourceDepSet[name]
            tree[1].append(build_dep_tree(depth+1, name, sourceDeps[depRange[0]:depRange[1]]))

    return tree


def build(mainSource, exeFile):
    """ Starts off the building process """
    config.mainHeader = config.HEADER_DIR + config.MAIN_SOURCE[len(config.SOURCE_DIR):-len(config.SOURCE_EXT)] + config.HEADER_EXT

    #   Builds dependency tree. Adding (0, mainHeader) guarantees that the list follows
    # the rules specified in the function documentation
    colour_print("\nGenerating dependency tree for " + mainSource + "...", colour=colours.BLU, style=styles.BLD)
    tree = []
    if (os.path.exists(config.mainHeader)):
        tree = build_dep_tree(0, config.MAIN_HEADER, dependencies(config.MAIN_HEADER))
    else:
        tree = build_dep_tree(0, config.MAIN_HEADER, dependencies(mainSource))

    objectList = []
    buildFailed = build_tree(tree, objectList, {})

    if buildFailed:
        colour_print("\nBuilding failed!",             colour=colours.YLW, style=styles.BLD)
        colour_print("Skipping executable generation", colour=colours.YLW, style=styles.BLD)
        colour_print("------------------------------", colour=colours.YLW)
    else:
        print("")
        needsCompiling = False
        if not os.path.exists(exeFile):
            needsCompiling = True
            colour_print("The file " + exeFile + " doesn't exist", colour=colours.MGT, style=styles.BLD)
        else:
            for obj in objectList:
                if os.path.getmtime(obj) > os.path.getmtime(exeFile):
                    needsCompiling = True
                    colour_print("The file " + exeFile + " out of date", colour=colours.MGT, style=styles.BLD)
                    break

        if needsCompiling:
            if not os.path.exists(config.EXE_DIR):
                os.makedirs(config.EXE_DIR)

            cmd = ("g++ " + config.FLAGS + " -o " + exeFile + " " + " ".join(objectList))

            colour_print("Generating executable... ", colour=colours.CYN, style=styles.BLD)
            colour_print("Running: ", colour=colours.CYN, style=styles.BLD, end='')
            colour_print(cmd, colour=colours.CYN)
            print("")

            ret = shell(cmd)
            ret.wait()
            msg = ret.stdout.read()

            if msg:
                if not ret.returncode:
                    colour_print(msg,                                  colour=colours.YLW)
                    colour_print("Compilation finished with warnings", colour=colours.YLW, style=styles.BLD)
                    colour_print("----------------------------------", colour=colours.YLW)
                else:
                    colour_print(msg,                  colour=colours.RED)
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


def build_object(sourceFile, objectFile):
    """
    Calls 'g++ -c' on the given source file and directs it to the given object file location.
    If the path for the object file doesn't exist, a new directory structure will be created for it.
    """

    buildDir = "/".join(objectFile.split("/")[:-1])
    if not os.path.exists(buildDir):
        os.makedirs(buildDir)

    cmd = "g++ " + config.FLAGS + " -c -I" + config.HEADER_DIR + " " + config.OTHER_INCLDES + " " + sourceFile + " -o " + objectFile
    colour_print("Running: ", style=styles.BLD, end='')
    colour_print(cmd)

    ret = shell (cmd)
    ret.wait()
    msg = ret.stdout.read()

    if msg:
        finalcolour = None
        if ret.returncode == 0:
            finalcolour = colours.YLW
        else:
            finalcolour = colours.RED
        colour_print(msg, colour=finalcolour)

    return ret.returncode

""" 
    Recursively builds source files in the tree. Basically it's assumed that not
every header will have a source file, but every source file (excluding the main file)
there will be a corresponding header file. isUpdated is a map that tracks what files have been 
visited already, and if they have, what is the latest modify date between it's header file and
its dependencies, useful to track if there are multiple things that depend on the same thing,
will skip re-checking that dependency branch
"""
def build_tree(tree, objectList, isUpdated={}):
    if not tree:
        return False

    # Needed in case multiple files depend on the same thing
    if tree[0] in isUpdated:
        return

    # Makes up source files
    headerFile = tree[0]
    sourceFile = config.SOURCE_DIR + headerFile[len(config.HEADER_DIR):-len(config.HEADER_EXT)] + config.SOURCE_EXT
    objectFile = config.OBJECT_DIR + headerFile[len(config.HEADER_DIR):-len(config.HEADER_EXT)] + config.OBJECT_EXT

    # Gets modified time for header file, or sets to 0 if there's no header
    # (such as the main source file)
    headerFileTime = 0
    if os.path.exists(headerFile):
        headerFileTime = os.path.getmtime(headerFile)

    needsBuilding = False
    lastBuild = 0
    if os.path.exists(sourceFile):
        sourceFileTime = os.path.getmtime(sourceFile)
        # If source file exists then we will be adding a corresponding
        # object file to the file list.
        objectList.append(objectFile)
        # If there's no object file then we will need to make one (lastBuild=0 tells its
        # dependencies that this will be freshly built)
        if os.path.exists(objectFile):
            # Otherwise we need to compare this object file to the header
            # and source files to see if it needs building
            lastBuild = os.path.getmtime(objectFile)
            if lastBuild < sourceFileTime:
                needsBuilding = True
        else:
            needsBuilding = True
            lastBuild = 0

    buildFailed = False
    latestModifyTime = headerFileTime
    for dep in tree[1]:
        # Recursively builds dependencies before building itself.
        buildFailed = buildFailed or build_tree(dep, objectList, isUpdated)
        # If any of the dependencies are newer then mark this for updating
        if isUpdated[dep[0]] > latestModifyTime:
            latestModifyTime = isUpdated[dep[0]]


    if latestModifyTime > lastBuild:
        needsBuilding = True

    # Now tells anyone who checks this map whether it was marked as updated
    isUpdated[headerFile] = latestModifyTime

    if buildFailed:
        colour_print("Skipping (build dependencies failed): " + objectFile, colour=colours.YLW)
        return buildFailed

    if os.path.exists(sourceFile):
        # If this header has a source file, build it if it needs building
        if needsBuilding:
            if build_object(sourceFile, objectFile) != 0:
                buildFailed = True
        else:
            colour_print("Skipping (up to date):                " + objectFile, colour=colours.GRN)

    return buildFailed

if __name__ == "__main__":
    print("")
    colour_print("Configuration", style=styles.BLD)
    colour_print("-------------", style=styles.BLD)

    colour_print("    EXE directory:    ", colour=colours.YLW, style=styles.BLD, end='')
    colour_print(config.EXE_DIR,  colour=colours.YLW)
    colour_print("    EXE file:         ", colour=colours.YLW, style=styles.BLD, end='')
    colour_print(config.EXE_FILE, colour=colours.YLW)

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
    colour_print(config.OTHER_INCLDES, colour=colours.MGT)

    colour_print("    Main source:      ", colour=colours.RED, style=styles.BLD, end='')
    colour_print(config.MAIN_SOURCE, colour=colours.RED)
    colour_print("    Main header:      ", colour=colours.RED, style=styles.BLD, end='')
    colour_print(config.MAIN_HEADER, colour=colours.RED)
    colour_print("    Main object:      ", colour=colours.RED, style=styles.BLD, end='')
    colour_print(config.MAIN_OBJECT, colour=colours.RED)

    target = sys.argv[1]
    colour_print("")
    colour_print("Running target ", colour=colours.WHT, end='')
    colour_print(target, colour=colours.WHT, style=styles.BLD)

    if target == "build":
        build(config.MAIN_SOURCE, config.EXE_FILE)

    elif target == "clean":
        if os.path.exists(config.OBJECT_DIR):
            colour_print("Removing " + config.OBJECT_DIR + "...", colour=colours.MGT)
            shutil.rmtree(config.OBJECT_DIR)
        if os.path.exists(config.EXE_FILE):
            colour_print("Removing " + config.EXE_FILE + "...",   colour=colours.MGT)
            os.remove(config.EXE_FILE)
    
    print("")