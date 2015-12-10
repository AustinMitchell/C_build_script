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

def printc(col, msg):
	print col + msg + c.end

def shell(cmd):
	return Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)

""" Generates a list of dependencies using g++ -H, only using dependencied from your include
directory. 
"""
def dependencies(filePath):
	deps = [s.strip() for s in shell("g++ -H -I" + headerDir + " " + otherIncludes + " " + filePath).stdout.read().split("\n") if headerDir in s]
	return [d for d in deps if len(d.split(" ")[0])*"." == d.split(" ")[0]]

# Builds a dependency tree, takes in (depth, dependency) pairs and makes a tree in order of how
# they should be built 
""" Here's how it works.
	It takes in a list of pairs. The first iterm is how deep the item is in the dependency
chain, and the second is the filename for the dependency. The expected input is basically
what comes out when you run g++ -H and take away system libraries, where the amount of dots
before the dependency represent the depth.
	The input follows two rules:
		for a given list 'a' that represents the depths of the list:
			for n > 0: a[0] < a[n]
			for n >= 0: if a[i] < a[i+1]: a[i+1] = a[i] + 1
	This list for instance follows these rules.
	-(1, dep1)
	-(2, dep2)
	-(3, dep3)
	-(3, dep4)
	-(2, dep5)
	We pull out the first item in this list and store it as the root of our tree. Then we
go through the rest of the list, and run the function again on each sublist that represents
another branch. If we take our last example, we get this:
	-root: (1, dep1)

	-branch 1:	(2, dep2)
				(3, dep3)
				(3, dep4)

	-branch 2:	(2, dep5)

	We don't need the depth anymore, so we store the root simply as the dependency. The
result for our example would look like this:
           dep1
          /    \
        dep2   dep5
       /    \
     dep3  dep4

	This produces a binary tree, but for any given node we can have as many branches as
we need.
"""
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
	# Converts each line of raw string data into a list of depth and dependency pairs
	deps = dependencies(mainSource)
	deps = [d.split(" ") for d in deps]
	deps = [(len(depth), path) for depth, path in deps]

	#   Builds dependency tree. Adding (0, mainHeader) guarantees that the list follows
	# the rules specified in the function documentation
	tree = buildDepTree([(0, mainHeader)] + deps)

	objectList = []
	buildFailed = buildTree(tree, objectList)

	if buildFailed:
		printc(c.ylw+c.bold, "\nBuilding failed!")
		printc(c.ylw+c.bold, "Skipping executable generation")
	else:
		needsCompiling = False
		if not os.path.exists(exeFile):
			needsCompiling = True
		elif os.path.getmtime(mainObject) > os.path.getmtime(exeFile):
			needsCompiling = True

		if needsCompiling:
			if not os.path.exists(exeDir):
				os.path.makedirs(exeDir)
			# Again, assumes that g++ standard is C++ 11
			printc(c.cyn+c.bold, "\nGenerating executable... ")
			cmd = "g++ " + flags + " -o " + exeFile +  " " + " ".join(objectList)
			printc(c.cyn+c.bold, "Running: " + cmd)
			call(cmd.split(" "))
		else:
			# Skips building if nothing was updated.
			printc (c.grn+c.bold, "\nEverything up to date!")
			printc (c.grn+c.bold, "Skipping executable generation")

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
	printc (c.bold, "Running: " + cmd)
	ret = shell (cmd)
	ret.wait()
	msg = ret.stdout.read()
	if len(msg) > 0:
		color = ''
		if ret.returncode == 0:
			color = c.ylw
		else:
			color = c.red
		printc(color, msg)
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

	""" 
		This check is important in case mainHeader is listed twice in a row, which is the case
	if a header file for main actually exists (go look at the build() function for the why), if
	there isn't a main header in the include folder then this won't matter.
	"""
	if tree[0] == mainHeader:
		foundHeader = False
		for dep in tree[1]:
			if dep[0] == mainHeader:
				foundHeader = True
				break
		if foundHeader:
			buildFailed = False
			for dep in tree[1]:
				buildFailed = buildFailed or buildTree(dep, objectList, isUpdated, lastBuild)
			return buildFailed

	# Needed in case multiple files depend on the same thing
	if tree[0] in isUpdated:
		return

	# Makes up source files 
	headerFile = tree[0]
	sourceFile = sourceDir + headerFile[len(headerDir):-len(headerExt)] + sourceExt
	objectFile = objectDir + headerFile[len(headerDir):-len(headerExt)] + objectExt

	# Gets modified time for header file, or sets to 0 if there's no header (such as for main source file)
	headerFileTime = 0
	if os.path.exists(headerFile):
		headerFileTime = os.path.getmtime(headerFile)

	needsBuilding = False
	lastBuild = 0
	if os.path.exists(sourceFile):
		sourceFileTime = os.path.getmtime(sourceFile)
		# If source file exists then we will be adding a corresponding object file to the file list.
		objectList.append(objectFile)
		# If there's no object file then we will need to make one (lastBuild=0 tells its dependencies that this will be freshly built)
		if os.path.exists(objectFile):
			# Otherwise we need to compare this object file to the header and source files to see if it needs building
			lastBuild = os.path.getmtime(objectFile)
			if lastBuild < sourceFileTime:
				needsBuilding = True
		else:
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
		printc(c.ylw, "Skipping (build dependencies failed): " + objectFile)
		return buildFailed

	if os.path.exists(sourceFile):
		# If this header has a source file, build it if it needs building
		if needsBuilding:
			if buildObject(sourceFile, objectFile) != 0:
				buildFailed = True
		else:
			printc(c.grn, "Skipping (up to date):                " + objectFile)

	return buildFailed


if target == "build":
	build()

elif target == "clean":
	if os.path.exists(objectDir):
		shutil.rmtree(objectDir)
	if os.path.exists(exeFile):
		os.remove(exeFile)