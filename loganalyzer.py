#!/usr/bin/env python3

import requests
import json
import argparse
import textwrap


RED     = "\033[1;31m"  
GREEN   = "\033[0;32m"
YELLOW  = "\033[0;33m"
BLUE    = "\033[1;34m"
MAGENTA = "\033[1;35m"
CYAN    = "\033[1;36m"
RESET   = "\033[0;0m"
BOLD    = "\033[;1m"
REVERSE = "\033[;7m"

#error levels:
# 1 = info
# 2 = warning
# 3 = critical


API_URL = "https://api.github.com"
messages =[]

def getGist(inputUrl):
    gistId=inputUrl.rsplit('/', 1)[-1]
    return requests.get('{0}/gists/{1}'.format(API_URL,gistId)).json()

def getLines(gistObject):
    files = [(v,k) for (k,v) in gistObject['files'].items()]
    return files[0][0]['content'].split('\n')

def search(term, lines):
    return [ s for s in lines if term in s ]

def searchRange(term, lines, lower, higher):
    res = []
    for i in range(lower, higher+1):
        if term in lines[i]:
            res.append(lines[i])

    return res

def checkDual(lines):
    if(len(search('Warning: OBS is already running!',lines))>0):
        messages.append([3, "TWO INSTANCES", "Two instances of OBS are running. They will likely interfere with each other and consume exessive ressources. Stop one of them. Check task manager for stray OBS processes if you can't find the other one."])

def checkAutoconfig(lines):
    if(len(search('Auto-config wizard', lines))>0):
        messages.append([3, "AUTOCONFIG WIZARD","The log contains an Auto-config wizard run. Results of this analysis are therefore inaccurate. Please post a link to a clean log file. To make a clean log file, first restart OBS, then start your stream/recording for ~30 seconds and stop it again. Make sure you replicate any issues as best you can, which means having any games/apps open and captured, etc. When you're done select Help > Log Files > Upload Current Log File. Copy the URL and paste it here."])

def checkCPU(lines):
    cpu = search('CPU Name', lines)
    if(('APU' in cpu[0]) or ('Pentium' in cpu[0]) or ('Celeron' in cpu[0])):
        messages.append([3, "INSUFFICIENT HARDWARE", "Your system is below minimum specs for obs ro run and too weak to do livestreaming. There are no settings which will save you from that lack of processing power. Replace your PC or Laptop."])

def checkGPU(lines):
    adapters = search('Adapter 1', lines)
    try:
        adapters.append(search('Adapter 2', lines)[0])
    except IndexError:
        print("only one gpu")
    d3dAdapter = search('Loading up D3D11', lines)
    if(len(adapters)==2 and ('Intel' in d3dAdapter[0])):
        messages.append([3, "WRONG GPU", "Your Laptop has two GPUs. OBS is running on the weak integrated Intel GPU. For better rerformance as well as game capture being available you should run OBS on the dedicated GPU. Check the laptop trpubleshooting guide here: https://obsproject.com/wiki/Laptop-Performance-Issues"])

def checkNVENC(lines):
    #TODO wait for kurufu
    if(1==0):
        messages.append([2, "NVIDIA DRIVERS", "NVENC fails to start up because your GPU drivers are out of date. You can perform a clean driver installation for your GPU by following the instructions at http://obsproject.com/forum/resources/performing-a-clean-gpu-driver-installation.65/"])

def checkKiller(lines):
    if(len(search('Interface: Killer',lines))>0):
        messages.append([1, "KILLER NIC", "Killer's Firewall is known for it's poor performance and issues when trying to stream. Please download the driver pack from http://www.killernetworking.com/driver-downloads/category/other-downloads , completely uninstall all Killer NIC items and install their Driver only package."])

def checkWifi(lines):
    if(len(search('802.11',lines))>0):
        messages.append([2, "WIFI STREAMING", "In many cases, wireless connections can cause issues because of their unstable nature. Streaming really requires a stable connection. Often wireless connections are fine, but if you have problems, then we are going to be very unlikely to be able to help you diagnose it if you're on a wireless just because it adds yet another variable. We recommend streaming on wired connections."])

def checkAdmin(lines):
    l = search('Running as administrator', lines)
    if(l[0].split()[-1]=='false'):
        messages.append([1, "NOT ADMIN", "OBS is not running as administrator. This can lead to obs not being able to gamecapture certain games"])

def checkMP4(lines):
    writtenFiles = search('Writing file ', lines)
    mp4 = search('.mp4', writtenFiles)
    if(len(mp4)>0):
        messages.append([3, "MP4 RECORDING","If you record to MP4 and the recording is interrupted, the file will be corrupted and unrecoverable. If you require MP4 files for some other purpose like editing, remux them afterwards by selecting File > Remux Recordings in the main OBS Studio window."])

def checkAttempt(lines):
    recordingStarts = search('== Recording Start ==', lines)
    streamingStarts = search('== Streaming Start ==', lines)
    if( len(recordingStarts) + len(streamingStarts) == 0):
        messages.append([1, "EMPTY LOG", "Your log contains no recording or streaming session. Results of this log analysis are limited. Please post a link to a clean log file. To make a clean log file, first restart OBS, then start your stream/recording for ~30 seconds and stop it again. Make sure you replicate any issues as best you can, which means having any games/apps open and captured, etc. When you're done select Help > Log Files > Upload Current Log File. Copy the URL and paste it here."])

def checkPreset(lines):
    encoderLines = search('x264 encoder:', lines)
    presets = search('preset: ',lines)
    sensiblePreset=True
    for l in presets:
        if (not ('veryfast' in l) or ('superfast' in l) or ('ultrafast' in l)):
            sensiblePreset=False

    if((len(encoderLines) >0)and (not sensiblePreset)):
        messages.append([2, "WRONG PRESET","A slower x264 preset than 'veryfast' is in use. It is recommended to leave this value on veryfast, as there are significant diminishing returns to setting it lower."])

def checkMulti(lines):
    mem = search('user is forcing shared memory', lines)
    if(len(mem)>0):
        messages.append([1, "MEMORY CAPTURE","Shared memory capture is very slow only to be used on SLI & Crossfire systems. Don't enable it anywhere else."])
    
def checkDrop(lines):
    drops = search('insufficient bandwidth', lines)
    val = 0
    for drop in drops:
        v = float(drop[drop.find("(")+1:drop.find(")")].strip('%'))
        if(v > val):
            val=v
    if(val!=0):
        if(val>=15): 
            severity=3
        elif(15>val and val >=5): 
            severity=2
        else:
            severity=1
        messages.append([severity, "FRAMEDROPS","Your log contains streaming sessions with dropped frames. This can only be caused by a failure in your internet connection or your networking hardware. It is not caused by OBS. Follow the troubleshooting steps at: https://obsproject.com/wiki/Dropped-Frames-and-General-Connection-Issues"])

def checkRendering(lines):
    drops = search('rendering lag', lines)
    val = 0
    for drop in drops:
        v = float(drop[drop.find("(")+1:drop.find(")")].strip('%'))
        if(v > val):
            val=v
    if(val!=0):
        if(val>=15): 
            severity=3
        elif(15>val and val >=5): 
            severity=2
        else:
            severity=1
        messages.append([severity, "RENDERING LAG", "Your GPU is maxed out and OBS can't render scenes fast enough. Running a game without vertical sync or a frame rate limiter will frequently cause performance issues with OBS because your GPU will be maxed out. Enable vsync or set a reasonable frame rate limit that your GPU can handle without hitting 100% usage. If that's not enough you may also need to turn down some of the video quality options in the game."])

def checkEncoding(lines):
    drops = search('skipped frames', lines)
    val = 0
    for drop in drops:
        v = float(drop[drop.find("(")+1:drop.find(")")].strip('%'))
        if(v > val):
            val=v
    if(val!=0):
        if(val>=15): 
            severity=3
        elif(15>val and val >=5): 
            severity=2
        else:
            severity=1
        messages.append([severity, "CPU OVERLOAD","The encoder is skipping frames because of CPU overload. Read https://obsproject.com/wiki/General-Performance-and-Encoding-Issues"])

def checkStreamSettingsX264(lines):
    streamingSessions = []
    for i,s in enumerate(lines):
        if "[x264 encoder: 'simple_h264_stream'] settings:" in s:
            streamingSessions.append(i)

    if(len(streamingSessions)>0):
        bitrate = float(lines[streamingSessions[-1]+2].split()[-1])
        fps_num = float(lines[streamingSessions[-1]+5].split()[-1])
        fps_den = float(lines[streamingSessions[-1]+6].split()[-1])
        width   = float(lines[streamingSessions[-1]+7].split()[-1])
        height  = float(lines[streamingSessions[-1]+8].split()[-1])
        
        bitrateEstimate = (width*height*fps_num/fps_den)/20000
        #print("{} {} {} {} {} {} ".format(bitrate,fps_num,fps_den,width,height,bitrateEstimate))
        if(bitrate < bitrateEstimate):
            messages.append([1, "LOW STREAM BANDWITH","Your stream encoder is set to a too low video bitrate. This will lower picture quality especially in high motion scenes like fast paced games. Use the autoconfig wizard to adjust your settings to the optimum for your situation. It can be accessed from the Tools menu in OBS, and then just follow the on-screen directions."])

def checkStreamSettingsNVENC(lines):
    streamingSessions = []
    for i,s in enumerate(lines):
        if "[NVENC encoder: 'streaming_h264'] settings:" in s:
            streamingSessions.append(i)
    if(len(streamingSessions)>0):
        bitrate = float(lines[streamingSessions[-1]+2].split()[-1])
        fps_num = float(lines[streamingSessions[-1]+4].split()[-1])/2
        width   = float(lines[streamingSessions[-1]+8].split()[-1])
        height  = float(lines[streamingSessions[-1]+9].split()[-1])
        
        bitrateEstimate = (width*height*fps_num)/20000
        if(bitrate < bitrateEstimate):
            messages.append([1, "LOW STREAM BANDWITH","Your stream encoder is set to a too low video bitrate. This will lower picture quality especially in high motion scenes like fast paced games. Use the autoconfig wizard to adjust your settings to the optimum for your situation. It can be accessed from the Tools menu in OBS, and then just follow the on-screen directions."])



def getScenes(lines):
    scenePos = []
    for i,s in enumerate(lines):
        if '- scene' in s:
            scenePos.append(i)
    return scenePos

def getSections(lines):
    sectPos = []
    for i,s in enumerate(lines):
        if '------------------------------------------------' in s:
            sectPos.append(i)
    return sectPos

def getNextPos(old, lst):
    for new in lst:
        if(new>old):
            return new

def checkSources(lower, higher, lines):
    monitor = searchRange('monitor_capture', lines, lower, higher)
    game = searchRange('game_capture', lines, lower, higher)
    if(len(monitor)>0 and len(game)>0):
        messages.append([1,"SOURCES NOT OPTIMIZED", "Monitor and Game Capture Sources interfere with each other. Never put them in the same scene"])
    if(len(game)>1):
        messages.append([1,"SOURCES NOT OPTIMIZED", "Multiple Game Capture sources are usually not needed, and can sometimes interfere with each other. You can use the same Game Capture for all your games! If you change games often, try out the hotkey mode, which lets you press a key to select your active game. If you play games in fullscreen, use 'Capture any fullscreen application' mode."])

def parseScenes(lines):
    sceneLines = getScenes(lines)
    if(len(sceneLines)>0):
        sections = getSections(lines)
        higher = 0
        for s in sceneLines:
            if(s != sceneLines[-1]):
                higher = getNextPos(s, sceneLines)-1
            else:
                higher = getNextPos(s,sections)-1
            checkSources(s, higher, lines)
    else:
        messages.append([1,"NO SCENES/SOURCES","There are neither scenes nor sources added to OBS. You won't be able to record anything but a black screen without adding soueces to your scenes. If you're new to OBS Studio, the community has created some resources for you to use. Check out our Overview Guide at https://goo.gl/zyMvr1 and Nerd or Die's video guide at http://goo.gl/dGcPZ3"])

def textOutput(string):
    dedented_text = textwrap.dedent(string).strip()
    print(textwrap.fill(dedented_text,initial_indent=' ' * 4, subsequent_indent=' ' * 4, width=80, ))


def printResults(messages):
    critical = ""
    warning = ""
    info = ""
    score = 0
    for i in messages:
        if(i[0]==3):
            critical = critical + i[1] +", "
        elif(i[0]==2):
            warning = warning + i[1] +", "
        elif(i[0]==1):
            info = info + i[1] +", "
        score = score + i[0]

    print("Log Score {} ".format(score))
    print("{}Critical: {} ".format(RED,critical))
    print("{}Warning:  {} ".format(YELLOW,warning))
    print("{}Info   :  {} ".format(CYAN,info))
    print("{}--------------------------------------".format(RESET))
    print(" ")
    print("Details")
    print("Critical:")
    for i in messages:
        if(i[0]==3):
            print("{}{}".format(RED,i[1]))
            textOutput(i[2])

    print("{} ".format(RESET))
    print("Warning:")
    for i in messages:
        if(i[0]==2):
            print("{}{}".format(YELLOW,i[1]))
            textOutput(i[2])

    print("{} ".format(RESET))
    print("Info:")
    for i in messages:
        if(i[0]==1):
            print("{}{}".format(CYAN,i[1]))
            textOutput(i[2])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url",'-u',dest='url',
            default="", help="url of gist", required=True)
    flags = parser.parse_args()
    gistObject = getGist(flags.url)
    print(gistObject['description'])
    logLines=getLines(gistObject)

    checkDual(logLines)
    checkAutoconfig(logLines)
    checkCPU(logLines)
    checkGPU(logLines)
    checkNVENC(logLines)
    checkKiller(logLines)
    checkWifi(logLines)
    checkAdmin(logLines)
    checkAttempt(logLines)
    checkMP4(logLines)
    checkPreset(logLines)
    checkDrop(logLines)
    checkRendering(logLines)
    checkEncoding(logLines)
    checkMulti(logLines)
    checkStreamSettingsX264(logLines)
    checkStreamSettingsNVENC(logLines)
    parseScenes(logLines)
    printResults(messages)

if __name__ == "__main__":
    main()
