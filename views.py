
from datetime import datetime

from PyQt5 import QtCore
from PyQt5.QtCore import QCoreApplication, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QFont, QImage, QKeyEvent
from PyQt5.QtWidgets import QAction, QApplication, QDesktopWidget, \
    QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, \
    QLCDNumber, QLineEdit, QMainWindow, QProgressDialog, QPushButton, \
    QSizePolicy, QTextEdit, QVBoxLayout, QWidget

from controllers import Clip, get
from parse import get_text_and_commands
from util import pluralize
from wren import CLIP_BACKGROUND, CLIP_BACKGROUND_HOMEROW, CLIP_HEIGHT, \
    CLIP_WIDTH, GRID_BACKGROUND, GRID_BACKGROUND_HOMEROW, log, \
    render_equation_to_pixmap, StyleSheet


class WrenWindow(QMainWindow):
    """Main window of Wren application"""
    key_pressed = pyqtSignal(QKeyEvent, name='key_pressed')

    def __init__(self, *args, **kwargs):
        super(WrenWindow, self).__init__(*args, **kwargs)
        self.installEventFilter(self)

    def setup(self):
        log.info('MainWindow setup')
        from app import get_application
        # Menu setup
        exit_action = QAction('&Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('Quit Wren')
        exit_action.triggered.connect(QCoreApplication.instance().quit)#qApp.quit)

        import_action = QAction('&Import', self)
        import_action.setShortcut('Ctrl+I')
        import_action.setStatusTip('Import notes')
        import_action.triggered.connect(self.show_import_dialog)

        # Position, resize and decorate the window
        self.center()

        # Set to a large size in the desktop.
        log.info("getting window geometry...")
        geo = get_application().app.primaryScreen().size()
        #geo = QDesktopWidget().availableGeometry()
        log.info("... got {0} x {1}".format(geo.width(), geo.height()))
        x = geo.width() * 0.07
        width = geo.width() - (2 * x)
        y = geo.height() * 0.04 + 50
        height = geo.height() - (2 * y)
        log.info("setGeometry({0}, {1}, {2}, {3})".format(x, y, width,
                                                          height))
        self.setGeometry(x, y, width, height)

        import wren
        import math
        grid_width = max(1, math.floor(width * .72 / wren.CLIP_WIDTH))
        grid_height = max(1, math.floor(height / wren.CLIP_HEIGHT))
        if wren.GRID_WIDTH is not None:
            grid_width = wren.GRID_WIDTH
        if wren.GRID_HEIGHT is not None:
            grid_height = wren.GRID_HEIGHT
        log.info('gridwidth {0}, gridheight {1}'.format(grid_width,
                                                        grid_height))

        # This is accessed by other widgets when they need a progress bar.
        # see import mammals, and make_ranked_clips
        self.progress = QProgressDialog(self)
        self.progress.setModal(True)
        self.progress.setRange(0, 220)
        self.progress.setMinimumDuration(250)
        #self.progress.canceled.connect(self.thread.requestInterruption)
        self.progress.reset()

        self.setWindowTitle('Wren')
        log.info("creating Grid and Inspector")
        self.h_box = QHBoxLayout()
        self.grid = get(get_application().app_model.current_grid,
                        width=grid_width, height=grid_height,
                        status_bar=self.statusBar())
        import controllers
        self.inspector = controllers.Inspector(None)
        controllers.get_controller_id_map().set('main_inspector', self.inspector)
        self.inspector.setup(self.grid)

        self.h_box.addWidget(self.grid.view)
        self.h_box.addWidget(self.inspector.view)

        self.grid.view.clip_changed.connect(self.inspector.view.refresh)
        self.grid.view.cursor_changed.connect(self.inspector.view.refresh)
        self.grid.view.secondary_cursor_changed.connect(
            self.inspector.view.refresh)

        w = QWidget(self)
        w.setLayout(self.h_box)
        self.setCentralWidget(w)

        delete_column_action = QAction('Delete Column', self)
        delete_column_action.setShortcut('Ctrl+W')
        delete_column_action.setStatusTip('Delete Column')
        delete_column_action.triggered.connect(self.grid.delete_cursor_column)

        make_ranked_clips_action = QAction('Ranked Column', self)
        make_ranked_clips_action.setShortcut('Ctrl+Return')
        make_ranked_clips_action.setStatusTip(
            'Insert new column sorted by rank relative to selection')
        make_ranked_clips_action.triggered.connect(
            self.grid.make_ranked_clips_1)

        find_clip_action = QAction('Find', self)
        find_clip_action.setShortcut('Ctrl+S')  # F is navigational atm.
        find_clip_action.setStatusTip('Find Clip closest matching string')
        find_clip_action.triggered.connect(self.grid.do_find)

        delete_clip_action = QAction('Delete Clip', self)
        delete_clip_action.setShortcut('Ctrl+Backspace')
        delete_clip_action.setStatusTip('Delete Clip (but not its Datum)')
        delete_clip_action.triggered.connect(self.grid.delete_clip)

        copy_clip_action = QAction('Copy Clip', self)
        copy_clip_action.setShortcut('Ctrl+C')
        copy_clip_action.setStatusTip("Copy current Clip's Datum to clipboard")
        copy_clip_action.triggered.connect(self.grid.copy_clip)

        cut_clip_action = QAction('Cut Clip', self)
        cut_clip_action.setShortcut('Ctrl+X')
        cut_clip_action.setStatusTip("Cut current Clip's Datum to clipboard")
        cut_clip_action.triggered.connect(self.grid.cut_clip)

        paste_clip_action = QAction('Paste Clip', self)
        paste_clip_action.setShortcut('Ctrl+V')
        paste_clip_action.setStatusTip("Make new Clip from clipboard Datum")
        paste_clip_action.triggered.connect(self.grid.paste_clip)

        archive_datum_action = QAction('Archive Datum', self)
        archive_datum_action.setShortcut('Ctrl+Delete')
        archive_datum_action.setStatusTip('Remove Datum from Grid')
        archive_datum_action.triggered.connect(self.grid.archive_datum)

        refresh_column_action = QAction('Refresh Column', self)
        refresh_column_action.setShortcut('Ctrl+R')
        refresh_column_action.setStatusTip('Re-sort the current column')
        refresh_column_action.triggered.connect(
            self.grid.refresh_selected_column)

        scroll_cursor_right_action = QAction('Scroll Cursor Right', self)
        scroll_cursor_right_action.setShortcut('Ctrl+G')
        scroll_cursor_right_action.setStatusTip(
            "Scroll such that Selection's current Clip is center right")
        scroll_cursor_right_action.triggered.connect(
            self.grid.scroll_cursor_right)

        scroll_cursor_center_action = QAction('Scroll Cursor Center', self)
        scroll_cursor_center_action.setShortcut('Ctrl+F')
        scroll_cursor_center_action.setStatusTip(
            "Scroll such that Selection's current Clip is center center")
        scroll_cursor_center_action.triggered.connect(
            self.grid.scroll_cursor_center)

        scroll_cursor_left_action = QAction('Scroll Cursor Left', self)
        scroll_cursor_left_action.setShortcut('Ctrl+D')
        scroll_cursor_left_action.setStatusTip(
            "Scroll such that Selection's current Clip is center left")
        scroll_cursor_left_action.triggered.connect(
            self.grid.scroll_cursor_left)

        scroll_column_action = QAction('Scroll Column', self)
        scroll_column_action.setShortcut('Ctrl+L')
        scroll_column_action.setStatusTip(
            "Scroll to Column top, home or bottom (cyclic)")
        scroll_column_action.triggered.connect(
            self.grid.do_column_scroll)

        cycle_parentage_action = QAction('Cycle Parentage', self)
        cycle_parentage_action.setShortcut('Ctrl+P')
        cycle_parentage_action.setStatusTip(
            "Cycle through parentage choices between Selection and Marker")
        cycle_parentage_action.triggered.connect(
            self.grid.do_cycle_parentage)

        import_algebra_action = QAction('Import Tensor Algebra Notes', self)
        import_algebra_action.setShortcut('Ctrl+A')
        import_algebra_action.setStatusTip("Import documents/tensors.txt")
        import_algebra_action.triggered.connect(
            self.grid.view.import_algebra_notes)

        import_mammals_action = QAction('Import Mammals Closure', self)
        import_mammals_action.setShortcut('Ctrl+M')
        import_mammals_action.setStatusTip("Import mammals.pth")
        import_mammals_action.triggered.connect(
            self.grid.view.import_mammals_closure)

        menubar = self.menuBar()
        menubar.setNativeMenuBar(False)  # For in-window menu on a Mac
        file_menu = menubar.addMenu('&File')
        file_menu.addAction(import_action)
        file_menu.addAction(exit_action)

        grid_menu = menubar.addMenu('&Grid')
        grid_menu.addAction(import_mammals_action)
        grid_menu.addAction(import_algebra_action)
        grid_menu.addAction(delete_column_action)
        grid_menu.addAction(make_ranked_clips_action)
        grid_menu.addAction(find_clip_action)
        grid_menu.addAction(delete_clip_action)
        grid_menu.addAction(copy_clip_action)
        grid_menu.addAction(cut_clip_action)
        grid_menu.addAction(paste_clip_action)
        grid_menu.addAction(archive_datum_action)
        grid_menu.addAction(refresh_column_action)
        grid_menu.addAction(scroll_cursor_right_action)
        grid_menu.addAction(scroll_cursor_center_action)
        grid_menu.addAction(scroll_cursor_left_action)
        grid_menu.addAction(scroll_column_action)
        grid_menu.addAction(cycle_parentage_action)

        # Statusbar setup
        self.statusBar().showMessage('Ready')

        # Toolbar setup
        self.toolbar = self.addToolBar('Exit')
        self.toolbar.addAction(exit_action)
        self.toolbar.addAction(import_action)

        self.toolbar.addAction(import_algebra_action)
        self.toolbar.addAction(import_mammals_action)
        self.toolbar.addAction(delete_column_action)
        self.toolbar.addAction(make_ranked_clips_action)
        self.toolbar.addAction(delete_clip_action)
        self.toolbar.addAction(copy_clip_action)
        self.toolbar.addAction(cut_clip_action)
        self.toolbar.addAction(paste_clip_action)
        self.toolbar.addAction(archive_datum_action)
        self.toolbar.addAction(refresh_column_action)
        self.toolbar.addAction(scroll_cursor_right_action)
        self.toolbar.addAction(scroll_cursor_center_action)
        self.toolbar.addAction(scroll_cursor_left_action)
        self.toolbar.addAction(scroll_column_action)
        self.toolbar.addAction(cycle_parentage_action)
        self.show()

    def show_import_dialog(self):
        ImportDialog.show_import_dialog(self.grid, self)

    def center(self):
        window_geo = self.frameGeometry()
        center = QDesktopWidget().availableGeometry().center()
        window_geo.moveCenter(center)
        self.move(window_geo.topLeft())

    def keyPressEvent(self, event):
        super(WrenWindow, self).keyPressEvent(event)
        self.key_pressed.emit(event)


class ImportDialog(QDialog):

    def __init__(self, grid, parent=None):
        super().__init__(parent)
        self.grid = grid
        self.files = [] # Files selected for import
        self.datums = [] # Content of Datums they would create
        self.setWindowTitle('Import')
        self.setGeometry(300, 400, 600, 300)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel('Import a file, notes separated by ---------', self))
        self.files_label = QLineEdit(self)
        layout.addWidget(self.files_label)
        self.output = QTextEdit(self)
        self.output.setFocusPolicy(Qt.NoFocus)
        layout.addWidget(self.output)
        self.select_file_button = QPushButton('Files', self)
        layout.addWidget(self.select_file_button)
        self.select_file_button.clicked.connect(self.open_file_name_dialog)
        self.button = QPushButton('Import', self)
        self.button.clicked.connect(self.do_import)
        layout.addWidget(self.button)

    def open_file_name_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Text Files for Import")
        self.files = files
        self.datums = []
        self.file_name = ', '.join(files)
        for file_name in files:
            self.grid.status_bar.showMessage(
                'Reading file {}'.format(file_name))
            with open(file_name) as f:
                text = f.read()
            self.datums += list(filter(lambda y: y != '', text.split('-')))
        self.grid.status_bar.showMessage('Prepare to Import {}'.format(
            pluralize(self.datums, 'Datum')
        ))
        self.output.setPlainText('\n'.join(self.datums))

    def do_import(self):
        count = 0
        for datum_text in self.datums:
            count += 1
            self.grid.status_bar.showMessage(
                'Importing {}'.format(pluralize(count, 'Datum')))
            x, y = self.grid._get_next_coords()
            self.grid.new_datum_and_clip(x - self.grid.model.x_offset,
                                         y - self.grid.model.y_offset,
                                         datum_text, 0, emit=False)
        self.grid.view.clip_changed.emit()
        self.grid.status_bar.showMessage(
            'Import file {} complete - {} imported'.format(
                self.file_name, pluralize(count, 'Datum')))

    @staticmethod
    def show_import_dialog(grid, parent=None):
        grid.status_bar.showMessage('Open Import file dialog')
        dialog = ImportDialog(grid, parent)
        result = dialog.exec_()
        return result == QDialog.Accepted


class GridView(QWidget):
    cursor_changed = pyqtSignal(name='cursor_changed')
    secondary_cursor_changed = pyqtSignal(name='secondary_cursor_changed')
    clip_changed = pyqtSignal(name='clip_changed')
    secondary_clip_changed = pyqtSignal(Clip, name='secondary_clip_changed')

    def __init__(self, grid, width, height):
        super().__init__()
        self.grid_layout = None
        self.grid = grid
        self.grid_width = width
        self.grid_height = height
        from app import get_application
        self.window = get_application().main_window
        self.coordinates_to_clip = {}  # Screen Coordinates.

        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(0)
        self.setLayout(self.grid_layout)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFocusPolicy(Qt.TabFocus)
        for screen_x in range(self.grid_width):
            for screen_y in range(self.grid_height):
                clip_view = ClipView(self, None, self.grid,
                                     screen_x, screen_y)
                # Note addWidget is y, x
                self.grid_layout.addWidget(clip_view, screen_y, screen_x)
                self.coordinates_to_clip[screen_x, screen_y] = clip_view
                self.clip_changed.connect(clip_view.refresh)
        self.installEventFilter(self)
        self.clip_changed.connect(self.refresh)
        self.window.key_pressed.connect(self.on_key_press)
        self.refresh()


    def refresh(self):
        for screen_x in range(self.grid_width):
            for screen_y in range(self.grid_height):
                self.coordinates_to_clip[screen_x, screen_y].refresh()

    def sizeHint(self):
        return QSize(self.grid_width*CLIP_WIDTH, self.grid_height*CLIP_HEIGHT)

    def set_focus(self, screen_x, screen_y):
        """Edit given location, creating Clip and Datum if needed."""
        clip_view = self.coordinates_to_clip[screen_x, screen_y]
        # minor kludge, until you create a clip it doesn't show the background.
        clip_view.background = CLIP_BACKGROUND
        clip_view.style_sheet.set('background', clip_view.background)
        clip_view.setStyleSheet(clip_view.style_sheet.render())
        from app import get_application
        inspector = get_application().main_window.inspector
        inspector.set_focus()

    def set_cursor_focus(self):
        self.setFocus()

    def import_algebra_notes(self):
        # Kind of a kludge to put this here, but it has to go somewhere.
        start = datetime.now()
        with open('./documents/tensors.txt') as f:
            text = f.read()
        datums_text = list(filter(lambda y: y != '', text.split('-')))
        for datum_text in datums_text:
            x, y = self.grid._get_next_coords()
            self.grid.new_datum_and_clip(x - self.grid.model.x_offset,
                                         y - self.grid.model.y_offset,
                                         datum_text, 0, emit=False)
        self.clip_changed.emit()
        log.info("import took %s seconds" % (datetime.now() - start).seconds)

    def import_mammals_closure(self):
        start_time = datetime.now()

        tsv = 'mammal_closure.tsv'
        # Get the word count for the tsv so we can have a nice progress bar.
        import subprocess
        cmd = ['wc', '-l', tsv]
        output = subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()[0]
        count = int(output.strip().split(b' ')[0])

        from app import get_application
        progress = get_application().main_window.progress
        old_min_time = progress.minimumDuration()
        progress.setMinimumDuration(
            max(0, old_min_time - (datetime.now()-start_time).seconds*1000))
        progress.setRange(0, count)
        progress.reset()
        progress.setLabelText('Getting {} lines from {}'.format(count, tsv))

        from poincare.data import slurp
        idx, objects = slurp('mammal_closure.tsv', progress=progress)

        # We use slurp because it will read the parentage out of the closure.
        from collections import defaultdict as ddict
        adjacency = ddict(set)
        count = len(idx)
        progress.setMinimumDuration(
            max(0, old_min_time - (datetime.now()-start_time).seconds*1000))
        progress.setLabelText('Making Adjacency of {} edges'.format(count))
        progress.setRange(0, count+1)
        progress.reset()
        for i in range(len(idx)):
            progress.setValue(i+1)
            s, o, _ = idx[i]
            adjacency[s].add(o)
        adjacency = dict(adjacency)
        progress.setValue(count+1)
        # This is a map of number (objects index) to "is a kind of" indexes

        import torch as th
        serialization = th.load('mammals.pth')
        datums_text = serialization['objects']
        count = 0
        text_to_index = {}
        text_to_clip = {}
        progress.setLabelText('Making {} Clips'.format(len(datums_text)))
        progress.setMinimumDuration(
            max(0, old_min_time - (datetime.now()-start_time).seconds*1000))
        progress.setRange(0, len(datums_text))
        progress.reset()

        # Sort these by distance from 'mammal'

        from torch.autograd import Variable
        from controllers import _lt, _embedding, _term_to_index, _m

        # Mammal is term 29.
        s_e = Variable(_lt[29].expand_as(_embedding), volatile=True)
        _dists = _m.dist()(s_e, _embedding).data.cpu().numpy().flatten()

        positives = []
        for i, datum_text in enumerate(datums_text):
            progress.setValue(i)
            term_id = _term_to_index[datum_text]
            score = _dists[term_id]
            score = float(score)
            positives.append((score, datum_text))

        datums_text = [x[1] for x in sorted(positives)]

        for i, datum_text in enumerate(datums_text):
            progress.setValue(i+1)
            text_to_index[datum_text] = i
            count += 1
            #x, y = self.grid._get_next_coords()
            x = 0
            y = i
            clip = self.grid.new_datum_and_clip(x - self.grid.model.x_offset,
                                                y - self.grid.model.y_offset,
                                                datum_text, 0, emit=False)
            text_to_clip[datum_text] = clip
            self.grid.status_bar.showMessage('new clips {}'.format(count))

        # Set the parentage
        progress.setLabelText('Setting {} Parentages'.format(len(adjacency)))
        progress.setMinimumDuration(
            max(0, old_min_time - (datetime.now()-start_time).seconds*1000))
        progress.setRange(0, len(adjacency))
        progress.reset()
        for i, (parent, children) in enumerate(adjacency.items()):
            progress.setValue(i)
            parent_text = objects[parent]
            parent_clip = text_to_clip[parent_text]
            parent_key = parent_clip.datum.model.key
            for child in children:
                child_text = objects[child]
                child_clip = text_to_clip[child_text]
                child_clip.datum.model.parent = parent_key
                child_clip.datum.model.save()

        self.clip_changed.emit()
        msg = "import took %s seconds" % (datetime.now() - start_time).seconds
        log.info(msg)
        self.grid.status_bar.showMessage(msg)
        progress.setMinimumDuration(old_min_time)
        progress.reset()

    def on_key_press(self, event):
        modifiers = QApplication.keyboardModifiers()
        # Note modifiers can be OR'd together to check for combos.
        key = event.key()
        shift = modifiers & Qt.ShiftModifier
        ctrl = modifiers & Qt.ControlModifier
        if ctrl:
            if key == Qt.Key_Right:
                self.grid.change_offset(1, 0, 'right')
            elif key == Qt.Key_Left:
                self.grid.change_offset(-1, 0,'left')
            elif key == Qt.Key_Down:
                self.grid.change_offset(0, 1, 'down')
            elif key == Qt.Key_Up:
                self.grid.change_offset(0, -1, 'up')
        else:
            # Lets you type numbers when Grid has focus and it sets the score
            # in the number input and gives focus to the number input.
            num = {
                    Qt.Key_Period: '.',
                    Qt.Key_0: '0',
                    Qt.Key_1: '1',
                    Qt.Key_2: '2',
                    Qt.Key_3: '3',
                    Qt.Key_4: '4',
                    Qt.Key_5: '5',
                    Qt.Key_6: '6',
                    Qt.Key_7: '7',
                    Qt.Key_8: '8',
                    Qt.Key_9: '9'
            }
            try:
                c = num[key]
            except KeyError:
                return
            from app import get_application
            inspector = get_application().main_window.inspector
            if inspector.view.number_text_edit.isEnabled():
                line_edit = inspector.view.number_text_edit
                line_edit.setFocus(True)
                line_edit.setText(c)

    def __repr__(self):
        return 'GridView({0})<{1}>'.format(self.grid.model.key, id(self))

# Note the number of ClipViews is fixed at the Grid size, they update from an
# infinite Grid of underlying Clips.
class ClipView(QFrame):

    def __init__(self, parent, clip, grid, screen_x, screen_y):
        super().__init__(parent)
        self.clip = clip
        self.grid = grid
        self.screen_x = screen_x
        self.screen_y = screen_y
        self.style_sheet = StyleSheet('ClipView')
        if self.clip:
            self.clip.needs_refresh.connect(self.refresh)
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout()
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.scores = QWidget()
        # Helpful for debugging background issues.
        #self.scores.setStyleSheet("background: 'red'")
        self.scores_layout = QHBoxLayout()
        self.scores_layout.setSpacing(0)
        self.scores_layout.setContentsMargins(0, 0, 0, 0)
        self.scores.setLayout(self.scores_layout)
        self.left_score = QLCDNumber(8)
        self.scores_layout.addWidget(self.left_score)
        self.right_score = QLCDNumber(8)
        self.scores_layout.addWidget(self.right_score)
        self.layout.addWidget(self.scores)

        self.title_label = QLineEdit()
        font = QFont()
        font.setBold(True)
        self.title_label.setFont(font)
        self.title_label.setStyleSheet("background: rgba(0,0,0,0%)")
        self.title_label.setFocusPolicy(Qt.NoFocus)
        self.title_label.textChanged.connect(self.on_name_change)
        self.layout.addWidget(self.title_label)

        self.text_edit = QTextEdit(self)
        # Set the TextEdit background to transparent
        self.text_edit.setStyleSheet("background: rgba(0,0,0,0%)")
        # Put this connect back if we once again edit in the GridView
        #self.text_edit.textChanged.connect(self.on_data_change)
        self.text_edit.setFocusPolicy(Qt.NoFocus)
        # self.text_edit.setText()
        self.layout.addWidget(self.text_edit)

        self.setLayout(self.layout)
        self.refresh()

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        grid_view = self.parentWidget()
        grid_view.cursor_changed.connect(self.refresh)
        grid_view.secondary_cursor_changed.connect(self.refresh)

        self.refresh()

    def refresh(self):
        self.clip = self.grid.get_clip_at(self.screen_x, self.screen_y)
        if self.clip:
            name = self.clip.datum.model.name
            data = self.clip.datum.model.data
        else:
            name = ''
            data = ''
        offset_y = self.screen_y + self.grid.model.y_offset
        is_home_row = offset_y == 0
        if data or name:
            if is_home_row:
                self.background = CLIP_BACKGROUND_HOMEROW
            else:
                self.background = CLIP_BACKGROUND
        else:
            if is_home_row:
                self.background = GRID_BACKGROUND_HOMEROW
            else:
                self.background = GRID_BACKGROUND
        self.style_sheet.set('background', self.background)

        main_cursor = self.grid.main_cursor
        secondary_cursor = self.grid.secondary_cursor
        # Screen coordinates
        m_x = main_cursor.model.x
        m_y = main_cursor.model.y
        # Absolute coordinates
        s_x = secondary_cursor.model.x - self.grid.model.x_offset
        s_y = secondary_cursor.model.y - self.grid.model.y_offset
        main_on = m_x == self.screen_x and m_y == self.screen_y
        secondary_on = s_x == self.screen_x and s_y == self.screen_y
        # Taking this out for a moment -- REMOVE TO PUT 2nd CURSOR BACK
        secondary_on = False
        if main_on and secondary_on:
            self.style_sheet.set('border', '2px dashed purple')
        elif main_on:
            self.style_sheet.set('border', '2px dashed red')
        elif secondary_on:
            self.style_sheet.set('border', '2px dashed blue')
        else:
            self.style_sheet.set(
                'border',
                '2px solid {0}'.format(self.background))
        self.setStyleSheet(self.style_sheet.render())
        if data != self.text_edit.toPlainText():
            self.text_edit.setText(data)
        if name != self.title_label.text():
            self.title_label.setText(name)

        if not self.clip:
            self.left_score.setStyleSheet("background: rgba(0,0,0,0%)")
            self.left_score.display('')
            self.right_score.setStyleSheet("background: rgba(0,0,0,0%)")
            self.right_score.display('')
            return

        from controllers import _m, _term_to_index, _embedding, _lt
        from torch.autograd import Variable
        clip_datum_key = self.clip.model.datum_key
        clip_datum_text = get(clip_datum_key).model.data
        clip_term_id = _term_to_index[clip_datum_text]
        # Left side is distance from this to selection
        selection_score = None
        selection_clip = self.grid.get_cursor_clip()
        if selection_clip:
            selection_datum_key = selection_clip.model.datum_key
            selection_datum_text = get(selection_datum_key).model.data
            selection_term_id = _term_to_index[selection_datum_text]
            s_e = Variable(_lt[selection_term_id].expand_as(_embedding),
                   volatile=True)
            _dists = _m.dist()(s_e, _embedding).data.cpu().numpy().flatten()
            selection_score = round(float(_dists[clip_term_id]), 5)
        if selection_score is None:
            left_score_text = ''
        else:
            left_score_text = str(selection_score)
        if selection_score is None:
            self.left_score.setStyleSheet("background: rgba(0,0,0,0%)")
        else:
            self.left_score.setStyleSheet("background: 'red'")
        self.left_score.display(left_score_text)

        # Right side is distance from this to home
        home_score = None
        # remember this is a clip.view, not a clip... we need to lookup in
        # absolute.
        absolute_x = self.screen_x + self.grid.model.x_offset
        coords = (absolute_x, 0)
        home_clip = self.grid.coordinates_to_clip[coords]

        if home_clip:
            home_datum_key = home_clip.model.datum_key
            home_datum_text = get(home_datum_key).model.data
            home_term_id = _term_to_index[home_datum_text]
            s_e = Variable(_lt[home_term_id].expand_as(_embedding),
                   volatile=True)
            _dists = _m.dist()(s_e, _embedding).data.cpu().numpy().flatten()
            home_score = round(float(_dists[clip_term_id]), 5)
        if home_score is None:
            right_score_text = ''
        else:
            right_score_text = str(home_score)
        if home_score is None:
            self.right_score.setStyleSheet("background: rgba(0,0,0,0%)")
        else:
            self.right_score.setStyleSheet(
                "background: '{}'".format(GRID_BACKGROUND_HOMEROW))
        self.right_score.display(right_score_text)

    def set_clip(self, clip):
        self.clip = clip
        self.refresh()
        self.refresh_cursor()

    def on_name_change(self):
        text = self.title_label.text()
        if not self.clip:
            assert text == ''
            return
        assert text != ''
        self.clip.set_datum_name(text)

    def sizeHint(self):
        return QSize(CLIP_WIDTH, CLIP_HEIGHT)


class KeyPressLineEdit(QLineEdit):
    def keyPressEvent(self,  event):
        if event.key() in {Qt.Key_Right, Qt.Key_Left,
                           Qt.Key_Up, Qt.Key_Down}:
            # Focus to Grid
            from app import get_application
            grid = get_application().main_window.grid
            grid.view.setFocus(True)

            # Re-emit the event (or equivalent)
            get_application().main_window.key_pressed.emit(event)
            # Do not let the QLineEdit handle the key press.
            return

        super(KeyPressLineEdit, self).keyPressEvent(event)


class InspectorView(QWidget):
    def __init__(self, inspector):
        super().__init__()
        self.inspector = inspector
        self.clip = None
        self.text = ''

        self.layout = QVBoxLayout(self)

        self.eq_label = QLabel(self)
        self.eq_label.setText('render')
        self.layout.addWidget(self.eq_label)
        self.eq_text_edit = QTextEdit(self)
        #self.text_edit.setReadOnly(True)
        self.eq_text_edit.setFocusPolicy(Qt.NoFocus)
        self.layout.addWidget(self.eq_text_edit)

        self.marker_label = QLabel(self)
        self.marker_label.setText(
            '<span style="color:{};">home row</span>'.format(
                GRID_BACKGROUND_HOMEROW))
        self.layout.addWidget(self.marker_label)

        self.marker_parent_label = QLabel(self)
        self.marker_parent_label.setText('parent: <none>')
        self.layout.addWidget(self.marker_parent_label)

        self.marker_edit = QTextEdit(self)
        # if we put the marker back in, we put this
        #self.marker_edit.setStyleSheet("border: 2px dashed blue")
        #self.text_edit.setReadOnly(True)
        self.marker_edit.setFocusPolicy(Qt.NoFocus)
        #self.text_edit.textChanged.connect(self.on_datum_data_change)
        self.layout.addWidget(self.marker_edit)

        self.parent_label = QLabel(self)
        self.parent_label.setText('hierarchy: ▲ unrelated ▼')
        self.layout.addWidget(self.parent_label)

        self.label = QLabel(self)
        self.label.setText('<span style="color:#ff0000;">selection</span>')
        self.layout.addWidget(self.label)

        self.selection_parent_label = QLabel(self)
        self.selection_parent_label.setText('parent: <none>')
        self.layout.addWidget(self.selection_parent_label)

        self.text_edit = QTextEdit(self)
        self.text_edit.setStyleSheet("border: 2px dashed red")
        #self.text_edit.setReadOnly(True)
        self.text_edit.setFocusPolicy(Qt.NoFocus)
        self.text_edit.textChanged.connect(self.on_datum_data_change)
        self.layout.addWidget(self.text_edit)

        numbers_widget = QWidget()
        numbers_layout = QHBoxLayout(numbers_widget)
        self.number_label = QLabel(self)
        self.number_label.setText(
  'p( <span style="color:#ff0000;">selection</span> | <span style="color:{};">home row</span> )'.format(GRID_BACKGROUND_HOMEROW))
        numbers_layout.addWidget(self.number_label)
        self.number_text_edit = KeyPressLineEdit(self)
        #self.number_text_edit.setReadOnly(True)
        #self.number_text_edit.setFocusPolicy(Qt.NoFocus)
        #self.layout.addWidget(self.number_text_edit)
        numbers_layout.addWidget(self.number_text_edit)
        self.setFocusProxy(self.number_text_edit)

        self.other_number_label = QLabel(self)
        self.other_number_label.setText(
'p( <span style="color:#0000ff;">marker</span> | <span style="color:#ff0000;">selection</span> )')
        numbers_layout.addWidget(self.other_number_label)
        self.other_number_text_edit = QLineEdit(self)
        self.other_number_text_edit.setReadOnly(True)
        self.other_number_text_edit.setFocusPolicy(Qt.NoFocus)
        numbers_layout.addWidget(self.other_number_text_edit)
        numbers_widget.setLayout(numbers_layout)
        self.layout.addWidget(numbers_widget)

        # A box of status-trackers
        self.status_layout = QGridLayout()
        w = QWidget()
        w.setLayout(self.status_layout)
        self.layout.addWidget(w)

        self.last_focus_name = ''
        self.focus_label = QLabel(self)
#        self.focus_label.setText('focus: ')
        self.status_layout.addWidget(self.focus_label, 0, 0)

        self.scroll_x_label = QLabel(self)
 #       self.scroll_x_label.setText('scroll: ')
        self.status_layout.addWidget(self.scroll_x_label, 0, 1)

        self.setLayout(self.layout)
        self.number_text_edit.textChanged.connect(
            self.on_selection_given_marker_change)
        self.other_number_text_edit.textChanged.connect(
            self.on_maker_giver_selection_change)
        self.refresh()

    def refresh(self):
        grid = self.inspector.grid
        selection_clip = grid.get_cursor_clip()
        self.clip = selection_clip
        marker_clip = grid.get_secondary_cursor_clip()
        value = ''

        # Set the score inputs, or disable them.
        if not (selection_clip and marker_clip):
            # Clear and disable the inputs.
            self.number_text_edit.setEnabled(False)
            self.number_text_edit.setText('')
            self.other_number_text_edit.setEnabled(False)
            self.other_number_text_edit.setText('')
        else:
            # Lookup values and set them in enabled inputs
            selection_key = selection_clip.datum.model.key
            marker_key = marker_clip.datum.model.key
            relationships = grid.model.relationships
            s_g_m = relationships.get(selection_key, {}).get(marker_key, '')
            m_g_s = relationships.get(marker_key, {}).get(selection_key, '')
            self.number_text_edit.setEnabled(True)
            self.number_text_edit.setText(s_g_m)
            self.other_number_text_edit.setEnabled(True)
            self.other_number_text_edit.setText(m_g_s)

        if selection_clip:
            pos = selection_clip.model.edit_cursor_position
            # Note that doing this changes the cursor, and triggers
            # the cursor changing thing... we need to disconnect and then
            # connect to eliminate this bounce, for now a hack.
            self.text_edit.setText(selection_clip.datum.model.data)
            #self.eq_text_edit.setText(selection_clip.datum.model.data)
            cursor = self.text_edit.textCursor()
            cursor.setPosition(pos)
            self.text_edit.setTextCursor(cursor)

            whole_text = selection_clip.datum.model.data
            self.eq_text_edit.clear()
            cursor = self.eq_text_edit.textCursor()
            for kind, text in get_text_and_commands(whole_text):
                if kind == 'text':
                    cursor.insertText(text)
                elif kind == 'equation':
                    pixmap = render_equation_to_pixmap(text)
                    width = 200 #self.text_edit.width()
                    pixmap = pixmap.scaled(width, width,
                                           Qt.KeepAspectRatio)
                    image = QImage(pixmap)
                    cursor.insertImage(image)
        else:
            self.text_edit.setText('')
            self.eq_text_edit.setText('')

        if marker_clip:
            pos = marker_clip.model.edit_cursor_position
            self.marker_edit.setText(marker_clip.datum.model.data)
            cursor = self.marker_edit.textCursor()
            cursor.setPosition(pos)
            self.marker_edit.setTextCursor(cursor)
        else:
            self.marker_edit.setText('')

        self.focus_label.setText('focus: {0}'.format(self.last_focus_name))
        m = self.inspector.grid.model
        self.scroll_x_label.setText('scroll: {0}, {1}'.format(m.x_offset,
                                                              m.y_offset))
        # These coordinates are screen relative
        m = self.inspector.grid.main_cursor.model
        self.label.setText(
'<span style="color:#ff0000;">selection</span>: {}, {}'.format(
    m.x + self.inspector.grid.model.x_offset,
    m.y + self.inspector.grid.model.y_offset))
        # These coordinates are already absolute
        m = self.inspector.grid.secondary_cursor.model
        self.marker_label.setText(
'<span style="color:{};">home row</span>: {}, {}'.format(
            GRID_BACKGROUND_HOMEROW, m.x, m.y))

        # Set the hierarchy labels.
        parent_texts = []
        selection_parent_name = '<none>'
        if selection_clip:
            parent_key = selection_clip.datum.model.parent
            if parent_key:
                selection_parent_name = get(parent_key).model.name
            if parent_key and marker_clip:
                if marker_clip.datum.model.key == parent_key:
                    parent_texts.append('▲ parent of ▼')
        self.selection_parent_label.setText('parent: {0}'.format(
            selection_parent_name))
        marker_parent_name = '<none>'
        if marker_clip:
            parent_key = marker_clip.datum.model.parent
            if parent_key:
                marker_parent_name = get(parent_key).model.name
            if parent_key and selection_clip:
                if selection_clip.datum.model.key == parent_key:
                    parent_texts.append('▼ parent of ▲')
        self.marker_parent_label.setText('parent: {0}'.format(
            marker_parent_name))

        if parent_texts:
            self.parent_label.setText('hierarchy: ' + ', '.join(parent_texts))
        else:
            self.parent_label.setText('hierarchy: ▲ unrelated ▼')

    def on_cursor_position_change(self):
        # Note this is unsubscribed before removing Focus or it is called with
        # a cursor position of 0 (defeating the point of saving the position.)
        clip = self.inspector.grid.get_cursor_clip()
        if clip:
            cursor = self.text_edit.textCursor()
            clip.model.edit_cursor_position = cursor.position()
            clip.model.save()

    def on_datum_data_change(self):
        text = self.text_edit.toPlainText()
        screen_x = self.inspector.grid.main_cursor.model.x
        screen_y = self.inspector.grid.main_cursor.model.y
        clip = self.inspector.grid.get_cursor_clip()
        if clip is None:
            if text:
                # We need to create a new Datum and a Clip to go with it.
                clip = self.inspector.grid.new_datum_and_clip(
                    screen_x,
                    screen_y,
                    text,
                    self.text_edit.textCursor().position())
            else:
                # Clip is None and text is blank, do nothing.
                return
        else:
            clip.set_datum_data(text)
        self.inspector.grid.view.refresh()

    def on_selection_given_marker_change(self):
        self.on_data_change('selection_given_marker')

    def on_maker_giver_selection_change(self):
        self.on_data_change('marker_given_selection')

    def on_data_change(self, edited):
        """Called when you type in the Inspector score editor"""
        grid = self.inspector.grid
        selection_clip = grid.get_cursor_clip()
        marker_clip = grid.get_secondary_cursor_clip()
        selection_given_marker = self.number_text_edit.text()
        marker_given_selection = self.other_number_text_edit.text()
        assert edited in ['selection_given_marker', 'marker_given_selection']
        if 'selection_given_marker' == edited:
            a = selection_clip
            a_text = selection_given_marker
            b = marker_clip
            b_text = marker_given_selection
        else:
            a = marker_clip
            a_text = marker_given_selection
            b = selection_clip
            b_text = selection_given_marker
        if None in [a, b]:
            return

        relationships = grid.model.relationships
        try:
            c1 = relationships[a.datum.model.key]
        except KeyError:
            c1 = {}
            relationships[a.datum.model.key] = c1
        c1[b.datum.model.key] = a_text

        if a is not b:
            try:
                c1 = relationships[b.datum.model.key]
            except KeyError:
                c1 = {}
                relationships[b.datum.model.key] = c1
            # This code only set the other value if it was empty
            # Policy is to always set the other value same as first.
            #if a.datum.model.key not in c1:
            #    c1[a.datum.model.key] = b_text
            c1[a.datum.model.key] = a_text  # same as 'a'

        grid.model.save()

        a.refresh()
        b.refresh()
        self.refresh()

    def set_clip(self, clip):
        # What we need is notification when the Cursor or Cursor2 changes.
        self.clip = clip
        clip1 = clip.grid.get_cursor_clip()
        clip2 = clip.grid.get_secondary_cursor_clip()
        relationships = clip.grid.model.relationships
        if clip1 and clip2:
            value = relationships.get(clip1.datum.model.key, {}).get(
                clip2.datum.model.key)
            if value is not None:
                self.number_text_edit.setText(value)
            else:
                self.number_text_edit.setText('')

    def sizeHint(self):
        return QSize(100, 100)
