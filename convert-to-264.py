import sys, getopt, os, subprocess, logging, pexpect

from os import listdir
from os.path import isfile, join
from datetime import datetime, timedelta

###########################################
#	USAGE
#	python3.8 convert-to-264.py --source path/to/directory --destination path/to/save/folder --preset path/to//plex.json --codecs hevc --extensions .mkv,.mp4,.avi --debug yes --stopCopy yes
#	
#
#	--source 
#	--destination 
#	--preset
#	--codecs
#	--extensions
#	--debug
#	--stopcopy
#	
#	install: python3.8 
# 	install: pip3.8 
#		package: pexpect
# 
#	install: ffprobe/ffmpeg
#	install: HandBrakeCLI (case-sensitive)
# 	
###########################################

def error(msg):
	print("Error: " + msg)
	logging.error(msg)
	
def info (msg):
	print("Info: " + msg)
	logging.info(msg)
	
def debug (msg, debugMode):
	if(debugMode is True):
		print("Debug: " + msg)
	logging.debug(msg)
	
def header (msg):
	print("Info: " + msg)
	logging.info("======= " + msg + " =======")

def touch(path):
	info("Touching " + path)
	with open(path, 'a'):
		os.utime(path, None)
	info("Touched " + path)	

def videoType(pathAndFile):	
	cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries","stream=codec_name", "-of", "default=noprint_wrappers=1:nokey=1", pathAndFile]
	info("running ffprobe: " + " ".join(cmd))
	result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	vidFormat = result.stdout.decode("utf-8").rstrip()

	return vidFormat
		
def main(argv):

	#var init
	src =  ""
	destination = "" 
	presetFile = ""
	convertCodecs = []
	convertFileTypes = []
	stopCopy = False
	debugMode = False
	
	#sets log file
	log = os.path.dirname(__file__ ) + "/script-conversion.log"
	
	#get options & args
	try:
		opts, args = getopt.getopt(argv, "s:d:p:c:e:", ["source=","destination=", "preset=", "codecs=" , "extensions=", "debug=", "stopcopy=" ])
	except getopt.GetoptError:
		error("something didn't work...")
		sys.exit(2)

	for opt, arg in opts:
		if opt in ( "-s", "--source"):
			src = arg
		elif opt in ( "-d", "--destination"):
			destination = arg
		elif opt in ( "-p", "--preset"):
			presetFile = arg	
		elif opt in ( "-c", "--codecs"):
			convertCodecs = arg.split(",")
		elif opt in ( "-e", "--extensions"):
			convertFileTypes = arg.split(",")
		elif opt in ("--debug"):
			debugMode = True
		elif opt in ("--stopcopy"):
			stopCopy = True
	
	#opens loggger
	if debugMode:
		logging.basicConfig(filename= log, level = logging.DEBUG, filemode="a", format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")	
	else:
		logging.basicConfig(filename= log, level = logging.INFO, filemode="a", format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")	
	
	#context for log file
	header("Starting new execution from " +  os.path.dirname(__file__ ))
	header("Arguments are: " + " ".join(argv))
	header("Log file is: " +  log)	
	header("Running from " + __file__)
	info ("Source is					: " +  src)
	info ("Destination is 				: "  + destination)
	info ("Preset file is 				: "  + presetFile)
	info ("Extensions to watch for are 	: " + ",".join(convertFileTypes))
	info ("Will convert codec types  	: " + ",".join(convertCodecs))
	debug("DEBUG is on", debugMode) if debugMode else info("DEBUG is off")
	info ("Script " + ( "won't" if stopCopy  else "will" ) + " copy valid files")
	
	if debugMode:
		result = subprocess.run(["pwd"], stdout=subprocess.PIPE)
		debug("pwd " + result.stdout.decode("utf-8").rstrip(), debugMode)
				
	try:
		
		debug ("Scanning source directory 	: " +  src, debugMode)
		files = [f for f in listdir(src) if isfile(join(src, f))] #files in given dir

		for file in files:
			debug("File: " + file, debugMode)
			extension = os.path.splitext(file)[1]
			conversionCompleteFile = (src + "/" + os.path.splitext(file)[0] + ".completed")
			
			if extension in convertFileTypes: #if we're monitoring this extention (includes .)
				pathAndFile = src + "/" + file
				vidFormat = videoType(pathAndFile) #calls ffprove to get vid codec
				
				info("Video " + file + " is of format: " + vidFormat)
				
				if vidFormat in convertCodecs : #if we care to convert this code
					savePathAndFile = destination + "/" + os.path.splitext(file)[0] + ".m4v"
					info("Found file to convert in: " + pathAndFile)
					
					debug("Checking if target file is already there: " + savePathAndFile, debugMode)		
					if(videoType(savePathAndFile) == "h264"):
						info("There's already a valid video there, moving on..." + savePathAndFile)
						break #get outta here
					
					debug("Checking if conversion file exists: " + conversionCompleteFile, debugMode)
					if(os.path.isfile(conversionCompleteFile)):
						info("File has been converted already, moving on..." + savePathAndFile)
						break #get outta here
					
					#preparing handbrake
					cmd = "HandBrakeCLI -i " + pathAndFile.replace(" ", "\ ") + " -o " + savePathAndFile.replace(" ", "\ ") + " --preset-import-file " + presetFile
					info("Invoking HandBrake with params: " + " " + cmd)
					
					#start new thread
					thread = pexpect.spawn(cmd)
					info("Subprocess started")
					
					#regex to extract console output from handbrake (%%) 
					cpl = thread.compile_pattern_list([pexpect.EOF,  '((.+ \d+ of \d+), .* (\d{2}.\d{2} %))|((.+ \d+ of \d+), (\d{0,3}.\d{2} %))'])
					now = datetime.now() 
					once = False
					
					while True:
						debug ("Checking for subprocess output", debugMode) 
						try:
							#try to read input
							i = thread.expect_list(cpl, timeout=2)
							if i == 0: # EOF
								info ("Subrocess exited")
								break
							elif i == 1:
								secondTimeStamp = datetime.now()
								tdelta =  secondTimeStamp - now
								#spit out progress in log file every two mins or the first loop
								if((tdelta.seconds > (10) or once is False) or debugMode):
									info ("Regex result: + " + thread.match.group(0).decode("utf-8").rstrip())
									now = datetime.now()
									once = True
									
						except pexpect.exceptions.TIMEOUT:
							debug ("No input found, checking again...", debugMode) 
						
					thread.close()
					
					#creates completion file if target saved properly
					if(videoType(savePathAndFile) == "h264"):
						touch(conversionCompleteFile)
	
					info("Subprocess done")
				else:
				
					#if flag is set not to care about valid (h264 files)... move on
					if stopCopy is False:
						info("Found file to copy in: " + pathAndFile) 
						destinationFile = destination + "/" + file
						
						debug("Checking if conversion file exists: " + conversionCompleteFile, debugMode)
						if(os.path.isfile(conversionCompleteFile)):
							info("File has been moved already, moving on..." + destinationFile)	
							
						debug("Checking is there's aready a file there: " + destinationFile, debugMode)
						if(os.path.isfile(destinationFile)):
							info("File exist, not copying again: " + destinationFile)
						else:
							info("No file found...")
							#preparing rsync
							cmd = "rsync --info=progress2 -rltgoDv " + pathAndFile.replace(" ", "\ ") + " " + destinationFile.replace(" ", "\ ")
							info("Invoking rsync with params: " + " " + cmd)
							
							#start new thread
							thread = pexpect.spawn(cmd)
							info("Subprocess started")
							
							cpl = thread.compile_pattern_list([pexpect.EOF, '.+(\d\d{1,2}%).+'])
							now = datetime.now() 
							once = False
							
							while True:
								debug ("Checking for subprocess output", debugMode) 
								try:
									i = thread.expect_list(cpl, timeout=2)
									if i == 0: # EOF
										info ("Subrocess exited")
										break
									elif i == 1:
										secondTimeStamp = datetime.now()
										tdelta =  secondTimeStamp - now
										#spit out progress in log file every 0.5 mins or the first loop
										if((tdelta.seconds > (0.5 * 60) or once is False) or debugMode is True):
											info ("Regex result: + " + thread.match.group(0).decode("utf-8").rstrip())
											now = datetime.now()
											once = True 
											
								except pexpect.exceptions.TIMEOUT:
									debug ("No input, checking again...", debugMode) 
								
							thread.close()
							
							#creates completion file if target saved properly
							if(videoType(destinationFile) == "h264"):
								touch(conversionCompleteFile)
							
	except FileNotFoundError:
		debug("Unexpected FileNotFoundError: "  + src, debugMode)
		error("Please enter a valid directory " + src)
		
	except NotADirectoryError:
		debug("Unexpected NotADirectoryError "  + src, debugMode)
		error("Please enter a valid directory " + src)
		
	header("Done execution")
if __name__ == "__main__":
	main(sys.argv[1:])


