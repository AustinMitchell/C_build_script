from subprocess import call, Popen, PIPE, STDOUT
import shutil
import os
import sys

class ansiColors:
    blk = '\033[90m'
    red = '\033[91m'
    grn = '\033[92m'
    ylw = '\033[93m'
    blu = '\033[94m'
    mgt = '\033[95m'
    cyn = '\033[96m'
    wht = '\033[97m'

    end = '\033[0m'
    bold = '\033[1m'
    uline = '\033[4m'

c = ansiColors

flags = "-std=c++11"

exeDir = "./bin"
exeFile = "./bin/run.exe"

sourceDir = "./src/"
sourceExt = ".cc"
headerDir = "./include/"
headerExt = ".h"
objectDir = "./build/"
objectExt = ".o"

otherIncludes = "-I./lib/"

mainSource = sourceDir + "main" + sourceExt
mainHeader = headerDir + mainSource[len(sourceDir):-len(sourceExt)] + headerExt
mainObject = objectDir + mainSource[len(sourceDir):-len(sourceExt)] + objectExt

target = sys.argv[1]

def shell(cmd):
    return Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT)

""" Generates a list of dependencies using g++ -H, only using dependencied from your include
directory. 
"""
def dependencies(filePath):
    cmd = "g++ " + flags + " -H -I" + headerDir + " " + filePath
    deps = [s for s in shell(cmd).stdout.read().split("\n") if len(s)>0 and s[0]=="."]
    deps = [s.strip() for s in deps if headerDir in s]

    filedeps = []
    for d in deps:
        dSplit = d.split(" ")
        if dSplit[0][len(dSplit[0])-1] == ".":
            filedeps.append((len(dSplit[0]), dSplit[1]))

    return filedeps

""" Builds a dependency tree, takes in a headerfile name and makes a tree in order of how
they should be built, using header and source dependencies.
"""
def buildDepTree(depth, headerFile, deps):
    # Basic tree. First item is the dep name, the second is a list, where each item
    # is a tuple where the first item is a name, and the second is a list. Recursive 
    # tree based on a python list.
    tree = [headerFile, []]

    # In this project we assume either header files are stand-alone, or have a 
    # corresponding source file which includes the header file, but may also include
    # things that aren't included in the header file, so that stuff needs to be added
    # to the tree so we can see if the source needs building based on ALL dependencies.
    sourceFile = sourceDir + headerFile[len(headerDir):-len(headerExt)] + sourceExt
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
        tree[1].append(buildDepTree(depth+1, name, deps[depRange[0]:depRange[1]]))

    # Same, but only adds in stuff not found in the header.
    for name in sourceDepSet:
        if not name in headerDepSet and not name == headerFile:
            depRange = sourceDepSet[name]
            tree[1].append(buildDepTree(depth+1, name, sourceDeps[depRange[0]:depRange[1]]))

    return tree

# Starts off the building process
def build(mainSource, exeFile):
    global mainHeader
    mainHeader = headerDir + mainSource[len(sourceDir):-len(sourceExt)] + headerExt

    #   Builds dependency tree. Adding (0, mainHeader) guarantees that the list follows
    # the rules specified in the function documentation
    print c.blu+c.bold + "\nGenerating dependency tree for " + mainSource + "..." + c.end
    tree = []
    if (os.path.exists(mainHeader)):
        tree = buildDepTree(0, mainHeader, dependencies(mainHeader))
    else:
        tree = buildDepTree(0, mainHeader, dependencies(mainSource))

    objectList = []
    buildFailed = buildTree(tree, objectList, {})

    if buildFailed:
        print c.ylw+c.bold + "\nBuilding failed!" + c.end
        print c.ylw+c.bold + "Skipping executable generation" + c.end
        print c.ylw        + "------------------------------" + c.end
    else:
        print ""
        needsCompiling = False
        if not os.path.exists(exeFile):
            needsCompiling = True
            print c.mgt+c.bold + "The file " + exeFile + " doesn't exist" + c.end
        else:
            for obj in objectList:
                if os.path.getmtime(obj) > os.path.getmtime(exeFile):
                    needsCompiling = True
                    print c.mgt+c.bold + "The file " + exeFile + " out of date" + c.end
                    break

        if needsCompiling:
            if not os.path.exists(exeDir):
                os.makedirs(exeDir)
            # Again, assumes that g++ standard is C++ 11
            print c.cyn+c.bold + "Generating executable... " + c.end
            cmd = ("g++ " + flags + " -o " + exeFile + " " + " ".join(objectList))
            print c.cyn+c.bold + "Running: " + c.end + c.cyn + cmd + c.end
            print ""
            ret = shell (cmd)
            ret.wait()
            msg = ret.stdout.read()
            if len(msg) > 0:
                color = ''
                if ret.returncode == 0:
                    print c.ylw + msg + c.end
                    print c.ylw+c.bold + "Compilation finished with warnings" + c.end
                    print c.ylw        + "----------------------------------" + c.end
                else:
                    print c.red + msg + c.end
                    print c.red+c.bold + "Compilation failed" + c.end
                    print c.red        + "------------------" + c.end
            else:
                print c.blu+c.bold + "Compilation succeeded" + c.end
                print c.blu        + "---------------------" + c.end



        else:
            # Skips building if nothing was updated.
            print c.grn+c.bold + "\nEverything up to date!" + c.end
            print c.grn+c.bold + "Skipping executable generation" + c.end
            print c.grn        + "------------------------------" + c.end

"""
    Calls 'g++ -c' on the given source file and directs it to the given object file location.
Assumes project standard will be C++ 11. If the path for the object file doesn't exist, a new
directory structure will be created for it.
"""
def buildObject(sourceFile, objectFile):
    buildDir = "/".join(objectFile.split("/")[:-1])
    if not os.path.exists(buildDir):
        os.makedirs(buildDir)
    cmd = "g++ " + flags + " -c -I" + headerDir + " " + otherIncludes + " " + sourceFile + " -o " + objectFile
    print c.bold + "Running: " + c.end + cmd
    ret = shell (cmd)
    ret.wait()
    msg = ret.stdout.read()
    if len(msg) > 0:
        color = ''
        if ret.returncode == 0:
            color = c.ylw
        else:
            color = c.red
        print color + msg + c.end
    return ret.returncode

""" 
    Recursively builds source files in the tree. Basically it's assumed that not
every header will have a source file, but every source file (excluding the main file)
there will be a corresponding header file. isUpdated is a map that tracks what files have been 
visited already, and if they have, what is the latest modify date between it's header file and
its dependencies, useful to track if there are multiple things that depend on the same thing,
will skip re-checking that dependency branch
"""
def buildTree(tree, objectList, isUpdated={}):
    if not tree:
        return False

    # Needed in case multiple files depend on the same thing
    if tree[0] in isUpdated:
        return

    # Makes up source files
    headerFile = tree[0]
    sourceFile = sourceDir + headerFile[len(headerDir):-len(headerExt)] + sourceExt
    objectFile = objectDir + headerFile[len(headerDir):-len(headerExt)] + objectExt

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
        buildFailed = buildFailed or buildTree(dep, objectList, isUpdated)
        # If any of the dependencies are newer then mark this for updating
        if isUpdated[dep[0]] > latestModifyTime:
            latestModifyTime = isUpdated[dep[0]]


    if latestModifyTime > lastBuild:
        needsBuilding = True

    # Now tells anyone who checks this map whether it was marked as updated
    isUpdated[headerFile] = latestModifyTime

    if buildFailed:
        print c.ylw + "Skipping (build dependencies failed): " + objectFile + c.end
        return buildFailed

    if os.path.exists(sourceFile):
        # If this header has a source file, build it if it needs building
        if needsBuilding:
            if buildObject(sourceFile, objectFile) != 0:
                buildFailed = True
        else:
            print c.grn + "Skipping (up to date):                " + objectFile + c.end

    return buildFailed

if target == "build":
    build(mainSource, exeFile)

elif target == "clean":
    if os.path.exists(objectDir):
        print c.mgt + "Removing " + objectDir + "..." + c.end
        shutil.rmtree(objectDir)
    if os.path.exists(exeFile):
        print c.mgt + "Removing " + exeFile + "..." + c.end
        os.remove(exeFile)