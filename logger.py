'''@package COLUTA65
Low-level logging for coluta operation

name: logging.py
author: D. Panchal
email: dpanchal@utexas.edu
date: 27 February 2019
'''
import ColutaGUI
import colutaMod
import serialMod
import Thread
from PyQt5 import QtCore
from datetime import datetime
import os

class Logging():
    '''
    Logger for low-level logging of coluta operations. 
    The class keeps the log entries of failed I2C, DAC, histogram commands
    Need more documentation...
    '''
    def __init__(self,coluta):
        self.coluta = coluta
        self.isRadiationRun = False
        self.logs = []
        self.tracebackList = []
        self.nLogFiles = 2 # log file indexing starts from 2

        if self.isRadiationRun:
            self.logFile = coluta.outputDataParser.radiationRunDirectory+'RR.log'
        else:
            self.logFile = coluta.outputDataParser.outputDirectory+'coluta.log'
        
        self.colutaOptions = "GUI loaded with the options: \n"
        for arg,opt in vars(self.coluta.pOptions).items():
            self.colutaOptions+= "{0}: {1} \n".format(arg,opt)

        self.preamble = True
        self.newEntry = True
        self.log()
        self.tick = 10000 # ms
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(lambda:Thread.WrapU(self.coluta,self.log,[],[]))
        self.timer.start(self.tick)

    def log(self):
        '''Save log entry to file at the timer tick'''
        if not self.newEntry: return

        self.isRadiationRun = self.coluta.outputDataParser.isRadiationRun
        # If file size greater than 100 KB, create a new log file
        if os.path.exists(self.logFile) and os.path.getsize(self.logFile)>100e3:   
            self.preamble = True         
            directory = self.logFile.split('/')[:-1]
            if self.isRadiationRun:
                self.logFile = "{0}/RR{1}.log".format("/".join(directory),self.nLogFiles)
            else:
                self.logFile = "{0}/coluta{1}.log".format("/".join(directory),self.nLogFiles)
            self.nLogFiles += 1

        self.addPreamble()
        with open(self.logFile,'a',newline='\n') as lg:
            # Use the list as queue
            for pos in range(len(self.logs)):
                lg.write(self.logs.pop(0))

        self.newEntry = False


    def addPreamble(self):
        '''Make the header for each log file'''
        if not self.preamble: return

        chipId = "Chip ID: {0} \n".format(self.coluta.boardConfigFileBox.currentText().upper())
        optionsList = self.colutaOptions.split('\n')
        optionsList.reverse()
        for setting in optionsList:
            self.logs.insert(0,setting+'\n')
        self.logs.insert(0,chipId)

        self.preamble = False

    def addEntry(self,level,commandName):
        '''Create log entry'''
        timestamp = datetime.now().strftime("%y_%m_%d_%H_%M_%S.%f")
        logEntry  = ''
        if level=='ERROR':
            logEntry = '[{0}] {1}: {2} \n'.format(timestamp,level,commandName)
            traceback = self.tracebackList
            for command in traceback:
                logEntry += '[{0}] {1}: {2} : {3} \n'.format(timestamp,level,commandName,command)  
        else:
            logEntry = '[{0}] {1}: {2} \n'.format(timestamp,level,commandName)   

        self.newEntry = True
        self.tracebackList.clear()
        self.logs.append(logEntry)
        
    def addTraceback(self,command):
        '''Append the last command(s) to the traceback list'''
        if command in self.tracebackList:
            return
        else:
            self.tracebackList.append(command)


    def clearLog(self):
        self.newEntry = False
        self.nLogFiles = 2
        self.logs.clear()
