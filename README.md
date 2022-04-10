# Game Assets Converter

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

*Copyright © 2021-2022 Ascomods*

## Description

Game Assets Converter is an open-source tool that aims at converting
some custom proprietary assets formats to the FBX format, and vice-versa.

Game Compatibility List:
```
DragonBall Raging Blast 2 (PS3)
```

Credits to revel8n, adsl14, SamuelDoesStuff, HiroTex and to the rest of the RB modding community for their contributions.

## Building

Python version: `3.7.9`

Dependencies:
```
natsort: 7.1.1
numpy: 1.20.0
observed: 0.5.3
PyQt5: 5.15.4
QtAwesome: 1.1.0
FBX Python SDK: 2020.0.1
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

Check out the tutorial [here](https://www.youtube.com/watch?v=HiU3i0ZZn2I&list=PL1zfdnvxzp12kg2b_ubdOqmoTyLLE3gcY)