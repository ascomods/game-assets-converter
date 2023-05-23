# Game Assets Converter

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

*Copyright © 2021-2023 Ascomods*

## Description

Game Assets Converter is an open-source tool that aims at converting
some custom proprietary assets formats to the FBX format, and vice-versa.

Game Compatibility List (PS3 | XBOX 360):
```
DragonBall Raging Blast 1
DragonBall Raging Blast 2
DragonBall Z Ultimate Tenkaichi
DragonBall Zenkai Battle Royale
```

Credits to revel8n, adsl14, SamuelDoesStuff, HiroTex, Olganix and to the rest of the RB modding community for their contributions.

## Building

Python version: `3.7.9`

Dependencies:
```
natsort: 7.1.1
numpy: 1.20.0
observed: 0.5.3
PyQt5: 5.10.1
QtAwesome: 1.1.0
lxml: 4.9.2
colorama: 0.4.6
FBX Python SDK: 2020.2.1 (provided in the libs folder)
Wine for linux support (tested with 8.1, might work with earlier versions)
```
Install libraries using pip:
```
pip install -r requirements.txt
```
Build using PyInstaller:
```
pyinstaller app.spec
```

## Usage

Check out the Blender tutorial [here](https://www.youtube.com/watch?v=pRkBQ4UaKCI)
Check out the 3ds max tutorial [here](https://www.youtube.com/watch?v=HiU3i0ZZn2I&list=PL1zfdnvxzp12kg2b_ubdOqmoTyLLE3gcY)