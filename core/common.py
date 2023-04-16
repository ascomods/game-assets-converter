import os
from PyQt5.QtCore import QSettings

settings = QSettings("settings.ini", QSettings.IniFormat)
temp_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'temp'))

class_map = {
    b'SPR3': b'SPRP'
}

games = {
    'dbrb': 'DragonBall Raging Blast',
    'dbrb2': 'DragonBall Raging Blast 2',
    'dbut': 'DragonBall Z Ultimate Tenkaichi'
}

platforms = {
    'ps3' : 'PS3',
    'x360' : 'XBOX 360'
}

selected_game = settings.value("Game")
selected_game = 'dbrb2' if (selected_game == None) else selected_game
selected_platform = settings.value("Platform")
selected_platform = 'ps3' if (selected_platform == None) else selected_platform

blender_export = False