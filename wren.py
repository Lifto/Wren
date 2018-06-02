
"""Wren - An interface for examining data and its relationships in a grid."""

from io import BytesIO
import logging
import os
import sys

from PyQt5.QtGui import QImage, QPixmap


# -- Globals ------------------------------------------------------------------

log = logging.getLogger('wren')
log.setLevel(logging.DEBUG)
if not log.handlers:
    log.addHandler(logging.StreamHandler())
    log.info(__doc__)

SELECTION_COLOR = {
    1: 'red',  # Cursor
    2: 'blue',  # Selection 1
    3: 'green'  # Selection 2
}

# GRID_WIDTH and GRID_HEIGHT set to None will be calculated.
GRID_WIDTH = None#4#12  # Number of clips
GRID_HEIGHT = None# 4#7  # Number of clips
CLIP_WIDTH = 192  # Pixels
CLIP_HEIGHT = 150  # Pixels
GRID_BACKGROUND = '#999'
GRID_BACKGROUND_HOMEROW = '#777'
CLIP_BACKGROUND = '#ff0'
CLIP_BACKGROUND_HOMEROW = '#cc0'

# -- Miscellaneous ------------------------------------------------------------

def render_equation_to_pixmap(text):
    import matplotlib.pyplot as plt
    plt.text(0.2, 0.6, r"$%s$" % text, fontsize=100)

    # hide axes
    fig = plt.gca()
    fig.axes.get_xaxis().set_visible(False)
    fig.axes.get_yaxis().set_visible(False)

    buffer = BytesIO()
    plt.savefig(buffer, bbox_inches='tight', frameon=False, transparent=True)
    plt.close()
    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue())
    buffer.close()
    return pixmap

def render_equation_to_label(label, text):
    pixmap = render_equation_to_pixmap(text)
    # Not full size so cursor can still appear
    pixmap = pixmap.scaled(CLIP_WIDTH * 0.85, CLIP_HEIGHT * 0.85)
    label.setPixmap(pixmap)
    label.adjustSize()

def render_equation_to_image(text):
    return QImage(render_equation_to_pixmap(text))

def spiral_coords(start_x, start_y):
    """A spiraling iteration of coordinates"""
    yield(start_x, start_y)

    level = 1
    x = start_x - level
    y = start_y - level
    area = 'top'

    while True:
        yield(x, y)
        if area == 'top':
            if x == start_x + level:
                y += 1
                area = 'right'
            else:
                x += 1
        elif area == 'right':
            if y == start_y + level:
                x -= 1
                area = 'bottom'
            else:
                y += 1
        elif area == 'bottom':
            if x == start_x - level:
                y -= 1
                area = 'left'
            else:
                x -= 1
        elif area == 'left':
            if y == (start_y - level) + 1:
                level += 1
                x = start_x - level
                y = start_y - level
                area = 'top'
            else:
                y -= 1


class StyleSheet:
    def __init__(self, selector):
        self.selector = selector
        self.sheet = {}

    def render(self):
        result = ["{0}{{".format(self.selector)]
        for element, value in self.sheet.items():
            result.append('{0}: {1};'.format(element, value))
        result.append('}')
        return ''.join(result)

    def set(self, element, value):
        self.sheet[element] = value

    def remove(self, element):
        del self.sheet[element]


class IDMap:
    """Map of datum key to its Controller"""
    def __init__(self):
        # Map of key to object.
        self.id_map = {}

    def get(self, key):
        return self.id_map.get(key)

    def set(self, key, obj):
        self.id_map[key] = obj

    def _reset(self):
        """Reset map for testing purposes only"""
        self.id_map = {}


# -- Main ---------------------------------------------------------------------

if __name__ == '__main__':
    # Confirm data storage is initialized (need: user to name the session.)
    from app import get_application
    wren = get_application()  # Creates application if does not exist.
    wren.init_ui()
    sys.exit(wren.run())
