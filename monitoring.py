"""Classes to run and manage the monitoring software

name: monitoring.py
author: C. D. Burton
email: burton@utexas.edu
date: 7 August 2018
"""

import numpy as np
import matplotlib
matplotlib.use("Qt5Agg")
#matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5 import QtCore, QtWidgets
import Thread
from matplotlib import rcParams
rcParams.update({'figure.autolayout': True})
# rcParams['text.usetex'] = True

class MPLCanvas(FigureCanvasQTAgg):
    """Inherits from generic matplotlib figure."""

    def __init__(self, parent, x, style='', *args, **kwargs):
        """Initialize the plot object over the range given in argument x"""

        # Initialize the Matplotlib object
        self.fig = Figure()
        self.subplot = self.fig.add_subplot(111,**kwargs)
        self.n = len(x)
        self.x = np.array(x)
        self.y = np.zeros(self.n)
        self.style = style
        self.kwargs = kwargs
        self.inflate = self.n==0
        self.newData = True
        self.initialx = self.x
        self.initialy = self.y

        # Integrate with the Qt API
        FigureCanvasQTAgg.__init__(self, self.fig)
        self.setParent(parent)
        FigureCanvasQTAgg.setSizePolicy(self,QtWidgets.QSizePolicy.Expanding,QtWidgets.QSizePolicy.Expanding)
        FigureCanvasQTAgg.updateGeometry(self)

    def updateFigure(self,yPoints=None,xPoints=None):
        """Clears the figure and re-plots"""
        if not self.newData: return
                
        if xPoints is not None:
            self.x = xPoints
        if yPoints is not None:
            self.y = yPoints

        try:
            self.fig.clf()
            self.subplot = self.fig.add_subplot(111,**self.kwargs)
            self.subplot.plot(self.x, self.y, self.style)
            self.subplot.autoscale(enable=True, axis='y')
            self.draw()
        except:
            print('Unable to draw canvas. Please retry.')

    def resetData(self):
        '''Reset data to initial.'''
        self.newData = True
        self.updateFigure(yPoints=self.initialy,xPoints=self.initialx)

class DynamicMPLCanvas(MPLCanvas):
    """A canvas that updates periodicaly with a new plot."""

    def __init__(self, coluta, parent, *args, **kwargs):
        MPLCanvas.__init__(self, parent, *args, **kwargs)
        self.updateFigure()
        self.tick = 1000 # ms
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(lambda:Thread.WrapU(coluta,self.updateFigure,[],[]))
        self.timer.start(self.tick)

    def updateFigure(self,*args,**kwargs):
        super(DynamicMPLCanvas,self).updateFigure(*args,**kwargs)
        self.newData = False

    def updateData(self,value):
        if self.inflate:
            self.y = np.append(self.y,value)
            self.n = len(self.y)
            self.x = np.arange(self.n)
        elif isinstance(value,list):
            for point in value:
                self.updateData(point)
        else:
            self.y = np.append(self.y[1:],value)
            self.x += int(self.tick*.001)
        self.newData = True

class HistogramMPLCanvas(MPLCanvas):
    def __init__(self, coluta, parent, *args, **kwargs):
        DynamicMPLCanvas.__init__(self,coluta,parent,*args,**kwargs)

    def updateFigure(self,*args,**kwargs):
        """Clears the histogram and re-plots"""
        if not self.newData: return
        if len(self.x)==0 or len(self.y)==0: return

        try:
            self.fig.clf()
            self.subplot = self.fig.add_subplot(111,**self.kwargs)
            self.subplot.bar(self.x,self.y)
            self.subplot.set_yscale("log", nonposy='clip')
            self.subplot.autoscale(enable=True, axis='y')
            self.draw()
        except:
            print('Unable to draw histogram. Please retry.')
        self.newData = False

    def updateHistData(self,bins,values):
        self.y = values
        self.x = bins
        self.newData = True

def makeLaTeX(s,it=False,bf=False,size=r'\normalsize'):
    fontSeries = r'\fontseries{Helvetica}'
    selectFont = r'\selectfont'
    text = '{'
    text += size
    if bf:
        text += r'\bfseries'
    if not it:
        text += fontSeries
    elif it:
        s = r'\textit{'+s+'}'
    text += s
    text += '}'
    return text

def saveFFT(psd,freq,QA,fileName):
    nyquist = freq[-1]
    fig, ax = plt.subplots(figsize=(6,6)) # plot object
    ax.plot(freq,psd,'r-')
    
    # tick marks
    fmin,fmax = np.min(freq),np.max(freq)
    smin,smax = np.min(psd),np.max(psd)
    if smin<-999: smin=-999
    yscale = 0.05714285714*smin
    ax.set_ylim([1.1*smin,-0.1*smin])
    ax.tick_params(which='both',top=True,right=True,direction='in',labelsize='large')
    ax.tick_params(which='major', length=10)
    ax.tick_params(which='minor', length=4)
    plt.minorticks_on()
    
    # make figure square
    l = ax.figure.subplotpars.left
    r = ax.figure.subplotpars.right
    t = ax.figure.subplotpars.top
    b = ax.figure.subplotpars.bottom
    figw = float(600)/(r-l)
    figh = float(600)/(t-b)
    r = -figh/figw*nyquist/(1.1*smin+0.1*smin)
    ax.set_aspect(r)

    # text
    fa = freq[np.argmax(psd)]
    xAlign = 1 if fa>nyquist/2 else nyquist/2+1
    text_ATLAS = makeLaTeX('ATLAS ',True,True,r'\LARGE')
    text_Upgrade = makeLaTeX('Upgrade',it=True,size=r'\LARGE')
    text_COLUTA = makeLaTeX('COLUTA V2 ADC',size=r'\large')
    text_ENOB = makeLaTeX('ENOB: {:.2f}'.format(QA['ENOB']))
    text_SINAD = makeLaTeX('SINAD: {:.2f} dB'.format(QA['SINAD']))
    text_SFDR = makeLaTeX('SFDR: {:.2f}'.format(QA['SFDR']))
    text_SNR = makeLaTeX('SNR: {:.2f}'.format(QA['SNR']))
    plt.text(xAlign,yscale*0,text_ATLAS+text_Upgrade)
    plt.text(xAlign,yscale*1,text_COLUTA)
    plt.text(xAlign,yscale*2,text_ENOB)
    plt.text(xAlign,yscale*3,text_SINAD)
    plt.text(xAlign,yscale*4,text_SFDR)
    plt.text(xAlign,yscale*5,text_SNR)

    # axes labels
    text_xlabel = makeLaTeX('Frequency [MHz]',size=r'\Large')
    text_ylabel = makeLaTeX('PSD [dB]',size=r'\Large')
    plt.xlabel(text_xlabel,horizontalalignment='right',x=1)
    plt.ylabel(text_ylabel,horizontalalignment='right',y=1)

    # save
    for fileFormat in ['eps','png']:
        plt.savefig(fileName+fileFormat)
