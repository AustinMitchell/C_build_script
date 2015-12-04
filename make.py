from subprocess import call, Popen, PIPE, STDOUT
import shutil
import os
import sys

exeFile = "./bin/run.exe"

sourceDir = "./src/"
sourceExt = ".cc"
headerDir = "./include/"
headerExt = ".h"
objectDir = "./build/"
objectExt = ".o"

mainSource = sourceDir + "main" + sourceExt
mainHeader = headerDir + mainSource[len(sourceDir):-len(sourceExt)] + headerExt
mainObject = objectDir + mainSource[len(sourceDir):-len(sourceExt)] + objectExt

target = sys.argv[1]

def shell(cmd):
	return Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)

# Generates a list of dependencies using g++ -H
def dependencies(filePath):
	deps = [s.strip() for s in shell("g++ -H -I" + headerDir + " " + filePath).stdout.read().split("\n") if headerDir in s or sourceDir in s]
	return [d for d in deps if len(d.split(" ")[0])*"." == d.split(" ")[0]]

# Builds a dependency tree, takes in (depth, dependency) pairs and makes a tree in order of how
# they should be built 
def buildDepTree(deps):
	#print "Current deps: ", deps
	if not deps:
		return None
	if len(deps) == 1:
		return (deps[0][1], [])

	tree = (deps[0][1], [])
	treeDepth = deps[0][0]

	branchStart = 1
	i = 2
	for d in deps[i:]:
		depth = d[0]
		if depth <= treeDepth+1:
			tree[1].append(buildDepTree(deps[branchStart:i]))
			branchStart = i
		i += 1
	tree[1].append(buildDepTree(deps[branchStart:]))

	return tree

# Starts off the building process
def build():
	deps = dependencies(mainSource)
	deps = [d.split(" ") for d in deps]
	deps = [(len(depth), path) for depth, path in deps]

	tree = buildDepTree([(0, mainHeader)] + deps)


	objectList = []
	# isUpdated = {}
	buildFailed = buildTree(tree, objectList)

	# if not mainObject in objectList:
	# 	buildMain = False
	# 	if os.path.exists(mainObject):
	# 		if os.path.getmtime(mainSource) > os.path.getmtime(mainObject):
	# 			buildMain = True
	# 		else:
	# 			for d in 
	# 	else:
	# 		buildMain = True

	# 	if buildMain:
	# 		objectList.append(mainObject)
	# 		if buildObject(mainSource, mainObject) != 0:
	# 			buildFailed = True
	# 	else:
	# 		print mainObject + " is up to date, skipping build"

	if buildFailed:
		print "\nBuilding failed!"
		print "Skipping executable generation"
	elif not objectList:
		print "\nEverything up to date!"
		print "Skipping executable generation"
	else:
		print "\nGenerating executable... "
		cmd = "g++ -std=c++11 -o " + exeFile +  " " + " ".join(objectList)
		print "Running: " + cmd
		call(cmd.split(" "))

# Calls g++ linker on source file
def buildObject(sourceFile, objectFile):
	buildDir = "/".join(objectFile.split("/")[:-1])
	if not os.path.exists(buildDir):
		os.makedirs(buildDir)
	cmd = "g++ -std=c++11 -c -I" + headerDir + " " + sourceFile + " -o " + objectFile
	print "Running: " + cmd
	ret = shell (cmd)
	ret.wait()
	msg = ret.stdout.read()
	if len(msg) > 0:
		print msg
	return ret.returncode

# Recursively builds source files in the tree
def buildTree(tree, objectList, isUpdated={}, lastBuild=0):
	if not tree:
		return False

	if tree[0] in isUpdated and not tree[0] == mainHeader:
		return
	isUpdated[tree[0]] = False

	headerFile = tree[0]
	sourceFile = sourceDir + headerFile[len(headerDir):-len(headerExt)] + sourceExt
	objectFile = objectDir + headerFile[len(headerDir):-len(headerExt)] + objectExt

	headerFileTime = 0
	if os.path.exists(headerFile):
		headerFileTime = os.path.getmtime(headerFile)

	buildFailed = False
	needsBuilding = False
	if os.path.exists(sourceFile):
		sourceFileTime = os.path.getmtime(sourceFile)
		objectList.append(objectFile)
		if not os.path.exists(objectFile):
			lastBuild = 0
			needsBuilding = True
		else:
			lastBuild = os.path.getmtime(objectFile)
			if lastBuild < sourceFileTime or lastBuild < headerFileTime:
				needsBuilding = True
	else:
		if lastBuild < headerFileTime:
			needsBuilding = True


	for dep in tree[1]:
		buildFailed = buildFailed or buildTree(dep, objectList, isUpdated, lastBuild)
		needsBuilding = needsBuilding or isUpdated[dep[0]]


	isUpdated[headerFile] = needsBuilding
	
	if os.path.exists(sourceFile):
		if needsBuilding:
			if buildObject(sourceFile, objectFile) != 0:
				buildFailed = True
		else:
			print objectFile + " is up to date, skipping build"

	return buildFailed


if target == "build":
	build()

elif target == "clean":
	if os.path.exists(objectDir):
		shutil.rmtree(objectDir)