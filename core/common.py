import os

temp_path = os.path.split(os.path.realpath(__file__))[0] + "/../temp/"

class_map = {
    b'SPR3': b'SPRP'
}

games = {
    'dbrb2': 'DragonBall Raging Blast 2'
}

platforms = {
    'ps3' : 'PS3'
}

selected_game = 'dbrb2'
selected_platform = 'ps3'

keep_normals = False