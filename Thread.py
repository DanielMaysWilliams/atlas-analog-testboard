"""@package COLUTA65
Class definition for multithreading

Processes such as taking data can be sent to a background thread to avoid locking up the
GUI during this step. This will allow users to access other tabs. This is especially 
useful when using the monitoring tab during long data-taking runs.

name: Thread.py
author: J. Konchady, C. D. Burton
email: burton@utexas.edu
date: 2 February 2019
"""

from PyQt5.QtCore import QThread, pyqtSignal, QMutex

class UnlockedThread(QThread):
    '''Subclass QThread for passing GUI work to a background thread.

    Thread is given some function to run and a list of args and kwargs to pass to that 
    function. 
    '''
    signal = pyqtSignal()
    mutex = QMutex()

    def __init__(self, coluta, work, pre, post, *args, **kwargs):
        super(QThread,self).__init__(coluta)
        self.coluta = coluta
        self.work = work
        self.post = post
        self.args = args
        self.kwargs = kwargs
        for preItr in pre:
            preItr()
    
    def run(self):
        '''Runs when thread is opened.'''
        self.work(*self.args,**self.kwargs)
        self.quit()
        self.signal.emit() # objects attached to this signal are called here

    def finalize(self):
        '''Runs at the completion of a LockedThread.'''
        for postItr in self.post:
            postItr()
        self.coluta.threads.remove(self)

    def isLocked(self):
        triedLock = self.mutex.tryLock(-1)
        if triedLock:
            self.mutex.unlock()
        return not triedLock

    def isUnlocked(self):
        return not self.isLocked()

class LockedThread(UnlockedThread):
    '''Subclass UnlockedThread for passing GUI work to a locked background thread.

    This subclass only overrides the run() function, locking the thread's mutex before
    and after the work function is called.
    '''

    def isLocked(self):
        triedLock = self.mutex.tryLock(2000)
        if triedLock:
            self.mutex.unlock()
        return not triedLock

    def run(self):
        self.mutex.lock()
        self.work(*self.args,**self.kwargs)
        self.quit()
        self.signal.emit()
        self.mutex.unlock()

def WrapU(coluta, work, pre, post, *args, **kwargs):
    '''Wrapper function for instantiating and starting a thread.
    
    CDB: add detailed documentation
    '''
    thread = UnlockedThread(coluta,work,pre,post,*args,**kwargs)
    thread.signal.connect(lambda:thread.finalize())
    coluta.threads.append(thread)
    thread.start()

def WrapL(coluta, work, pre, post, *args, **kwargs):
    '''Wrapper function for instantiating and starting a locked thread.'''
    if any([isinstance(existing,LockedThread) for existing in coluta.threads]):
        print('Existing locked thread. Cannot accept new thread.')
        return
    thread = LockedThread(coluta,work,pre,post,*args,**kwargs)
    thread.signal.connect(lambda:thread.finalize())
    coluta.threads.append(thread)
    thread.start()

def block(blockedHere=None):
    '''Handles interactions between threads at sensitive locations.
    
    Initial call should give no argument. Initiates a blocked piece of code. To end the
    block, pass the response of the first call back to the function. This will release
    that piece for other threads to use.
    '''
    currentThread = QThread.currentThread()
    if blockedHere is None:
        if isinstance(currentThread, LockedThread):
            return False
        elif isinstance(currentThread, UnlockedThread) and currentThread.isUnlocked():
            currentThread.mutex.lock()
            return True
        elif isinstance(currentThread, QThread):
            return False
    elif isinstance(blockedHere,bool):
        if isinstance(currentThread,UnlockedThread) and blockedHere:
            currentThread.mutex.unlock()
        return
    else:
        return
