"""Launches the COLUTA GUI.

name: coluta.py
author: C. D. Burton
email: burton@utexas.edu
date: 7 August 2018
"""

import sys,optparse
from PyQt5 import QtWidgets,QtGui
import testBoardGUI

if __name__ == "__main__":
    parser = optparse.OptionParser(usage='Usage: %prog [options]')
    parser.add_option('-n','--no-connect',action='store_true',
                      help='For testing without a board.')
    parser.add_option('-d','--debug',action='store_true',
                      help='Enter debug mode.')
    parser.add_option('-i','--instruments',action='store_true',
                      help='Connect and control instrumentation.')
    options, args = parser.parse_args()
    # Start a Qt Application, forward command line arguments
    app = QtWidgets.QApplication(sys.argv)
    # Create the interface
    window = testBoardGUI.testBoardGUI(app,options,args)
    app.setWindowIcon(QtGui.QIcon('./images/texas.png'))
    window.show()
    # Launch Qt event manager and retrieve status upon exit
    sys.exit(app.exec_())
