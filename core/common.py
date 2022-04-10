import os

temp_path = os.path.abspath(os.path.dirname(__file__) + '/../temp')

class_map = {
    b'SPR3': b'SPRP'
}

games = {
    'dbrb': 'DragonBall Raging Blast',
    'dbrb2': 'DragonBall Raging Blast 2'
}

platforms = {
    'ps3' : 'PS3',
    'x360' : 'XBOX 360'
}

selected_game = 'dbrb2'
selected_platform = 'ps3'

keep_normals = False