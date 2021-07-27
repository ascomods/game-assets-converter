import core.utils as ut
import os, glob
from io import BytesIO
from core.STPK import STPK
import ui.handlers.ViewHandler as vh
from handlers.ModelHandler import ModelHandler
from handlers.TextureHandler import TextureHandler
from handlers.MaterialHandler import MaterialHandler

class MainHandler():
    def __init__(self, view_handler = None):
        self.paths = {}
        if view_handler != None:
            self.view_handler = view_handler
        else:
            self.view_handler = vh.ViewHandler()
        self.view_handler.addObservers({
            'MainWindowHandler': {
                'notifyModelEditAction': self.modelEditAction,
                'notifyTextureEditAction': self.textureEditAction,
                'notifyMaterialEditAction': self.materialEditAction
            }
        })
        if not hasattr(self.view_handler, 'parent'):
            callbacks = {
                'self.loadWindow': ("MainWindowHandler")
            }
            self.view_handler.init(callbacks)
        else:
            self.view_handler.loadWindow('MainWindowHandler')

    def modelEditAction(self, observed, args):
        self.view_handler.resetWindow()
        ModelHandler()

    def textureEditAction(self, observed, args):
        self.view_handler.resetWindow()
        TextureHandler()

    def materialEditAction(self, observed, args):
        self.view_handler.resetWindow()
        MaterialHandler()