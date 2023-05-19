import os, sys
from PyQt5.QtCore import QSettings
from PyQt5 import QtCore

settings = QSettings("settings.ini", QSettings.IniFormat)
app_path = os.path.dirname(os.path.realpath(sys.argv[0]))
temp_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'temp'))

class_map = {
    b'SPR3': b'SPRP'
}

ext_map = {
    'SPRP': ['.spr'],
    'STPK': ['.pak', '.stpk'],
    'STPZ': ['.zpak', '.stpz']
}

games = {
    'dbrb': 'DragonBall Raging Blast',
    'dbrb2': 'DragonBall Raging Blast 2',
    'dbut': 'DragonBall Z Ultimate Tenkaichi',
    'dbzb': 'DragonBall Zenkai Battle Royale'
}

platforms = {
    'ps3' : 'PS3',
    'x360' : 'XBOX 360'
}

selected_game = settings.value("Game")
selected_game = 'dbrb2' if (selected_game == None) else selected_game
selected_platform = settings.value("Platform")
selected_platform = 'ps3' if (selected_platform == None) else selected_platform

use_blender = settings.value("Blender")
use_blender = eval(use_blender.title()) if (use_blender != None) else False
use_debug_mode = settings.value("Debug")
use_debug_mode = eval(use_debug_mode.title()) if (use_debug_mode != None) else False

stylesheet = QtCore.QFile(os.path.join("ui", "resources", "app.qss"))
if stylesheet.open(QtCore.QIODevice.ReadOnly):
    stylesheet = stylesheet.readAll().data().decode()