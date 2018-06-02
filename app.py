
import os
import sys

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from exceptions import NotFound
from model import ApplicationModel, DatumModel, GridModel
from views import WrenWindow
from wren import log


_APPLICATION = None
def get_application():
    """Main PyQT5 application object"""
    global _APPLICATION
    if _APPLICATION is None:
        _APPLICATION = WrenApplication()
    return _APPLICATION


class WrenApplication:
    """Main object for the Wren application"""

    def __init__(self):
        self.main_window = None

    def init_data(self):
        # Set up the model if it is new.
        try:
            name_model = DatumModel.load('name_datum')
        except NotFound:
            name_model = DatumModel('0', 'name_datum', key='name_datum')
            name_model.save()
        self.name_model = name_model
        try:
            app_model = ApplicationModel.load('main_app')
        except NotFound:
            app_model = ApplicationModel(key='main_app')
            app_model.save()
        self.app_model = app_model
        try:
            main_grid_model = GridModel.load('main_grid')
        except NotFound:
            main_grid_model = GridModel('main_grid')
            main_grid_model.save()
        if 'main_grid' not in self.app_model.grids:
            self.app_model.grids.add('main_grid')
            self.app_model.save()
        if self.app_model.current_grid is None:
            self.app_model.current_grid = 'main_grid'
            self.app_model.save()

    @staticmethod
    def get():
        return get_application()

    def init_ui(self):
        if not os.path.exists('documents'):
            os.makedirs('documents')

        # Configure PyQT5 Application
        self.app = QApplication(sys.argv)

        # Icon.
        path = os.path.join(
            os.path.dirname(sys.modules[__name__].__file__),
            'assets',
            'wren_icon.png')
        self.app.setWindowIcon(QIcon(path))

        self.init_data()

        self.main_window = WrenWindow()
        self.main_window.setup()
        self.main_window.grid.view.setFocus()

    def run(self):
        return self.app.exec_()

    def get_next_name(self):
        retval = self.name_model.data
        num = int(retval)
        num += 1
        self.name_model.data = str(num)
        self.name_model.save()
        return retval
