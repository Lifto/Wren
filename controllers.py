
from datetime import datetime
from inspect import isclass
import math
import pytz

from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtWidgets import QApplication

import model
from wren import IDMap, log, spiral_coords

import torch as th
from torch.autograd import Variable

# --- Start embedding load kludge ---
# This loads the serialization used to sort mammals clips, it could be moved,
# having it here is a bit of a kludge.
_serialization = th.load('mammals.pth')
_size = len(_serialization['objects'])
_dim = 5 # from opts, not sure how to read it out of serialization
from poincare.model import SNEmbedding
_m = SNEmbedding(_size, _dim)
_m.load_state_dict(_serialization['model'])
_lt = th.from_numpy(_m.embedding())
_embedding = Variable(_lt, volatile=True)
_term_to_index = {}
for i, obj in enumerate(_serialization['objects']):
    _term_to_index[obj] = i
# --- End embedding load kludge ---


_CONTROLLER_ID_MAP = None
def get_controller_id_map():
    """Holds singleton Controllers"""
    global _CONTROLLER_ID_MAP
    if _CONTROLLER_ID_MAP is None:
        _CONTROLLER_ID_MAP = IDMap()
    return _CONTROLLER_ID_MAP

# Map of model class name to controller class.
MODEL_TO_CONTROLLER = {}
def get(key, **kwargs):
    if key is None:
        return None
    id_map = get_controller_id_map()
    controller = id_map.get(key)
    if controller is None:
        got_model = model.get_model(key)
        controller_class = MODEL_TO_CONTROLLER[type(got_model).__name__]
        controller = controller_class(got_model)
        id_map.set(key, controller)
        controller.setup(**kwargs)
    return controller


class WrenController(QObject):
    model_class = model.WrenModel

    # Call this to instantiate and put in id-map
    def __init__(self, instance_model):
        super().__init__()
        self.model = instance_model

    # Call this to set up vars, like other controllers.
    # (prevents id-map recursion while setting up sub-controllers that
    # set up calling 'get' on this.)
    def setup(self):
        pass

    @classmethod
    def create(cls, *args, **kwargs):
        # This is a convenience. Don't override b/c want preserve
        # ability to create objects with only knowledge of the Model.
        # This is not a 'new' or '__init__' b/c we may enforce id-map.
        model = cls.model_class(*args, **kwargs)
        model.save()
        return get(model.key)

    def __repr__(self):
        try:
            name = self.model.name
        except AttributeError:
            name = None
        if name:
            return '{0}({1}, {2})'.format(type(self), self.model.key, name)
        else:
            return '{0}({1})'.format(type(self), self.model.key)


class Datum(WrenController):
    """Controller for a Text datum"""
    model_class = model.DatumModel

    def set_data(self, text):
        self.model.data = text
        self.model.last_changed = datetime.now(tz=pytz.utc)
        self.model.save()

    def set_name(self, name):
        self.model.name = name
        self.model.last_changed = datetime.now(tz=pytz.utc)
        self.model.save()


class Grid(WrenController):
    """Controller for a Grid of Clips"""
    model_class = model.GridModel

    def setup(self, width=None, height=None, status_bar=None):
        super().setup()
        # These are for evaluating the code in the Grid's Clips' Datums.
        self.grid_declarations = {}
        self.at_declarations = {}
        self.datum_declarations = {}

        self.grid_width = width
        self.grid_height = height
        self.status_bar = status_bar

        # Cursors
        self.main_cursor = get(self.model.main_cursor_model.key)
        self.secondary_cursor = get(self.model.secondary_cursor_model.key)

        # Clips
        self.coordinates_to_clip = {}  # Un-offset Clip Grid
        self.min_x = float('inf')
        self.max_x = -float('inf')
        self.y_upper_bounds = {}  # x-> y upper bound lowest valued y (most up)
        self.y_lower_bounds = {}  # x-> y lower bound highest valued y(mst dwn)
        for clip_model in self.model.clip_models:
            clip = get(clip_model.key)
            x = clip_model.x
            y = clip_model.y
            self.max_x = max(self.max_x, x)
            self.min_x = min(self.min_x, x)
            self.y_upper_bounds[x] = min(self.y_upper_bounds.get(x, 0), y)
            self.y_lower_bounds[x] = max(self.y_lower_bounds.get(x, 0), y)
            self.coordinates_to_clip[(x, y)] = clip

        if self.min_x == float('inf'):
            self.min_x = None
        if self.max_x == -float('inf'):
            self.max_x = None

        # Datums
        self.active_datums = set(self.model.active_datums)

        # ctl-l state-machine, center, bottom, top
        self.last_ctrl_l = 'center'  # see: self.do_ctrl_l()

        # Widget
        from views import GridView
        self.view = GridView(self, width, height)

    def get_clip_at(self, screen_x, screen_y):
        """Get the Clip at the given SCREEN coordinates."""
        x = screen_x + self.model.x_offset
        y = screen_y + self.model.y_offset
        try:
            return self.coordinates_to_clip[(x, y)]
        except KeyError:
            return None

    def get_cursor_clip(self):
        """Get the Clip at the main Cursor"""
        # Cursor clip is the selector, it is SCREEN RELATIVE
        m = self.main_cursor.model
        x = m.x
        y = m.y
        return self.get_clip_at(x, y)

    def get_secondary_cursor_clip(self):
        """Get the Clip at the secondary Cursor"""
        # Secondary Cursor is the marker, it is ABSOLUTE
        m = self.secondary_cursor.model
        return self.coordinates_to_clip.get((m.x, m.y))

    def change_offset(self, delta_x, delta_y, description=''):
        """change the current scroll position by the given amount"""
        if description:
            self.status_bar.showMessage('scroll {}'.format(description))
        self.model.x_offset += delta_x
        self.model.y_offset += delta_y
        self.model.save()
        self.view.refresh()
        from app import get_application
        inspector = get_application().main_window.inspector
        inspector.view.refresh()

    def get_clips(self):
        return self.coordinates_to_clip.values()

    def _get_next_coords(self):
        """Return tuple of x, y for next available grid placement."""
        # Make a set to keep track of coordinates already in use.
        used_coords = self.coordinates_to_clip.keys()
        # We'll start from the cursor.
        next_x = self.main_cursor.model.x
        next_y = self.main_cursor.model.y
        for x, y in spiral_coords(next_x, next_y):
            if (x, y) not in used_coords:
                next_x = x
                next_y = y
                break
        return next_x, next_y

    def new_datum_and_clip(self, screen_x, screen_y, text,
                           edit_cursor_position, emit=True):
        datum = Datum.create(text)
        self.active_datums.add(datum.model.key)
        self.model.active_datums.append(datum.model.key)
        self.model.save()
        return self.new_clip(screen_x, screen_y, datum, edit_cursor_position,
                             emit=emit)

    def new_clip(self, screen_x, screen_y, datum, edit_cursor_position,
                 emit=True):
        """Create a new Clip at the given coordinates. Offscreen coords OK."""
        # issue: If this overwrites a Datum's last Clip that Datum is orphaned.
        assert isinstance(datum, Datum)
        assert datum.model.key in self.active_datums, \
            "'{0}' {1} not active".format(datum.model.name, datum.model.key)
        absolute_x = screen_x + self.model.x_offset
        absolute_y = screen_y + self.model.y_offset
        coords = (absolute_x, absolute_y)

        assert coords not in self.coordinates_to_clip

        clip = Clip.create(self.model.key, datum.model.key,
                           absolute_x, absolute_y, edit_cursor_position)
        self.coordinates_to_clip[coords] = clip
        if self.max_x is None:
            self.max_x = absolute_x
        else:
            self.max_x = max(absolute_x, self.max_x)
        if self.min_x is None:
            self.min_x = absolute_x
        else:
            self.min_x = min(absolute_x, self.min_x)
        # max_y is most negative y, negative is 'up'
        max_y = self.y_upper_bounds.get(absolute_x, 100000000)
        self.y_upper_bounds[absolute_x] = min(max_y, absolute_y)
        # min_y is most postivie, positive is 'down'
        min_y = self.y_lower_bounds.get(absolute_x, -100000000)
        self.y_lower_bounds[absolute_x] = max(min_y, absolute_y)

        if emit:
            self.view.clip_changed.emit()
        return clip

    def delete_clip(self):
        self.do_delete_clip()

    def do_delete_clip(self, status=True):
        screen_x = self.main_cursor.model.x
        screen_y = self.main_cursor.model.y

        absolute_x = screen_x + self.model.x_offset
        absolute_y = screen_y + self.model.y_offset
        coords = (absolute_x, absolute_y)

        if coords not in self.coordinates_to_clip:
            if status:
                self.status_bar.showMessage(
                    'Delete Clip fail - No Clip selected')
            return
        clip = self.coordinates_to_clip[coords]
        if status:
            self.status_bar.showMessage(
                'Delete Clip {}'.format(clip.datum.model.name))

        del self.coordinates_to_clip[coords]
        self.model.delete_clip(clip.model)

        # Is it the highest, lowest, last-leftest or last-rightest?
        if absolute_y == self.y_upper_bounds[absolute_x]:
            new_upper_y = None
            for (x, y), clip in self.coordinates_to_clip.items():
                if x == absolute_x:
                    if new_upper_y is None or y < new_upper_y:
                        new_upper_y = y
            if new_upper_y is None:
                del self.y_upper_bounds[absolute_x]
            else:
                self.y_upper_bounds[absolute_x] = new_upper_y

        if absolute_y == self.y_lower_bounds[absolute_x]:
            new_lower_y = None
            for (x, y), clip in self.coordinates_to_clip.items():
                if x == absolute_x:
                    if new_lower_y is None or y > new_lower_y:
                        new_lower_y = y
            if new_lower_y is None:
                del self.y_lower_bounds[absolute_x]
            else:
                self.y_lower_bounds[absolute_x] = new_lower_y

        if absolute_x == self.min_x:
            if absolute_x not in self.y_upper_bounds:
                self.min_x = None
                for (x, y), clip in self.coordinates_to_clip.items():
                    if self.min_x is None or x < self.min_x:
                        self.min_x = x

        if absolute_x == self.max_x:
            if absolute_x not in self.y_upper_bounds:
                self.max_x = None
                for (x, y), clip in self.coordinates_to_clip.items():
                    if self.max_x is None or x > self.max_x:
                        self.max_x = x

        self.view.clip_changed.emit()

    def copy_clip(self):
        clip = self.get_cursor_clip()
        if clip:
            self.status_bar.showMessage('Copy Clip {}'.format(
                clip.datum.model.name))
            self.model.clipboard_datum_key = clip.model.datum_key
            self.model.save()
        else:
            self.status_bar.showMessage('Copy Clip fail - no Clip selected')

    def cut_clip(self):
        clip = self.get_cursor_clip()
        if not clip:
            self.status_bar.showMessage('Cut Clip fail - no Clip selected')
            return
        self.status_bar.showMessage('Cut Clip {}'.format(
            clip.datum.model.name))
        self.model.clipboard_datum_key = clip.model.datum_key
        self.model.save()
        self.do_delete_clip(status=False)

    def paste_clip(self):
        if self.model.clipboard_datum_key is not None:
            self.do_delete_clip(status=False)
            x = self.main_cursor.model.x
            y = self.main_cursor.model.y
            self.new_clip(x, y, get(self.model.clipboard_datum_key), 0)
            self.status_bar.showMessage('Paste Clip {}'.format(get(
                self.model.clipboard_datum_key).model.name))
        else:
            self.status_bar.showMessage('Paste fail - Clipboard empty')

    def delete_cursor_column(self):
        x = self.main_cursor.model.x
        self.delete_column(x)

    def delete_column(self, screen_x):
        absolute_x = screen_x + self.model.x_offset
        self.status_bar.showMessage('Delete Column {}'.format(absolute_x))
        delete_clips = []
        shift_clips = []
        y_bounds_to_change = set()
        for (x, y), clip in self.coordinates_to_clip.items():
            if x == absolute_x:
                delete_clips.append(((x, y), clip))
            elif x < absolute_x:
                y_bounds_to_change.add(x)
                shift_clips.append(((x, y), clip))

        if not delete_clips and not shift_clips:
            return

        if delete_clips:
            del self.y_upper_bounds[absolute_x]
            del self.y_lower_bounds[absolute_x]
        y_bounds_to_change = sorted(y_bounds_to_change, reverse=True)
        for x in y_bounds_to_change:
            self.y_upper_bounds[x+1] = self.y_upper_bounds[x]
            del self.y_upper_bounds[x]
            self.y_lower_bounds[x+1] = self.y_lower_bounds[x]
            del self.y_lower_bounds[x]
        if y_bounds_to_change:
            self.min_x += 1

        removes = set()
        for (x, y), clip in delete_clips:
            del self.coordinates_to_clip[x, y]
            removes.add(clip.model)

        models = [c for c in self.model.clip_models if c not in removes]
        self.model.clip_models = models

        for (x, y), clip in shift_clips:
            del self.coordinates_to_clip[x, y]
        for (x, y), clip in shift_clips:
            clip.model.x = x + 1
            self.coordinates_to_clip[x + 1, y] = clip
        self.model.save()
        self.view.refresh()

    def archive_datum(self):
        clip = self.get_cursor_clip()
        if clip is None:
            self.status_bar.showMessage(
"archive fail - selection is empty, select a Clip to archive its Datum")
            return
        key = clip.model.datum_key
        x_diff = 0  # Number of accumulated column-to-left shifts,
        # this is how leftward you shift every clip you touch based on previous
        # deleted columns.
        y_diff = 0  # Number of accumulated vertical clip up/down shifts
        # this is how up or downward you shift every clip you touch based on
        # previous deleted clips. It resets every top-home and home-to-bottom
        # process.
        #
        for x in range(self.min_x, self.max_x+1):
            if x not in self.y_upper_bounds:
                continue  # Blank column
            y_diff = 0
            # We get the un-offset x when we get, we write to x-x_diff.
            home_clip = self.coordinates_to_clip.get((x, 0))
            min_y = self.y_upper_bounds[x]
            max_y = self.y_lower_bounds[x]
            if home_clip and home_clip.model.datum_key == key:
                # Clear all clips from the column
                for y in range(min_y, max_y+1):
                    c = self.coordinates_to_clip.get((x, y))
                    if c:
                        del self.coordinates_to_clip[(x, y)]
                        self.model.delete_clip(c.model)

                # Clear old bounds-tracking invariants.
                del self.y_upper_bounds[x]
                del self.y_lower_bounds[x]
                x_diff += 1
            else:
                # The home clip is not being archived, so collapse everything
                # else, and copy over to cover deleted columns.
                if min_y < 0:
                    for y in range(1, abs(min_y-1)):
                        y = -y
                        c = self.coordinates_to_clip.get((x, y))
                        if c:
                            if c.model.datum_key == key:
                                y_diff += 1
                                del self.coordinates_to_clip[(x, y)]
                                self.model.delete_clip(c.model)
                            else:
                                # Move the clip.
                                new_x = x-x_diff
                                new_y = y+y_diff  # We're above homerow.
                                if new_x != c.model.x or new_y != c.model.y:
                                    del self.coordinates_to_clip[(x, y)]
                                    c.model.x = new_x
                                    c.model.y = new_y
                                    c.model.save()
                                    new_coords = (new_x, new_y)
                                    self.coordinates_to_clip[new_coords] = c
                self.y_upper_bounds[x-x_diff] = min_y + y_diff
                if max_y > 0:
                    for y in range(0, max_y+1):
                        c = self.coordinates_to_clip.get((x, y))
                        if c:
                            if c.model.datum_key == key:
                                y_diff += 1
                                del self.coordinates_to_clip[(x, y)]
                                self.model.delete_clip(c.model)
                            else:
                                # Move the clip.
                                new_x = x-x_diff
                                new_y = y-y_diff
                                if new_x != c.model.x or new_y != c.model.y:
                                    del self.coordinates_to_clip[(x, y)]
                                    c.model.x = new_x
                                    c.model.y = new_y
                                    c.model.save()
                                    new_coords = (new_x, new_y)
                                    self.coordinates_to_clip[new_coords] = c
                self.y_lower_bounds[x-x_diff] = max_y - y_diff

        self.max_x -= x_diff
        self.active_datums.remove(key)
        self.model.active_datums.remove(key)
        self.model.save()
        self.view.clip_changed.emit()
        self.view.refresh()

    def set_clip_focus(self, screen_x, screen_y):
        """Called when initiating editing of a Clip"""
        self.view.set_focus(screen_x, screen_y)

    def set_cursor_focus(self):
        """Called for Focus on Grid for moving Cursors with arrows."""
        from app import get_application
        inspector = get_application().main_window.inspector
        try:
            inspector.view.text_edit.cursorPositionChanged.disconnect(
                inspector.view.on_cursor_position_change)
        except TypeError:
            log.warn('TypeError in inspector disconnect')
        self.view.set_cursor_focus()

    def insert_column(self, screen_x):
        """Take every Clip at <= screen_x, decrement its x by 1"""
        start_size = len(self.coordinates_to_clip)
        absolute_x = screen_x + self.model.x_offset

        to_change = []
        y_bounds_to_change = set()
        for (x, y), clip in self.coordinates_to_clip.items():
            if x <= absolute_x:
                to_change.append(((x, y), clip))
                y_bounds_to_change.add(x)

        y_bounds_to_change = sorted(y_bounds_to_change)
        for x in y_bounds_to_change:
            self.y_upper_bounds[x-1] = self.y_upper_bounds[x]
            del self.y_upper_bounds[x]
            self.y_lower_bounds[x-1] = self.y_lower_bounds[x]
            del self.y_lower_bounds[x]

        to_change = sorted(to_change, key=lambda x:x[0][0])
        for (x, y), clip in to_change:
            del self.coordinates_to_clip[x, y]
            self.coordinates_to_clip[x-1, y] = clip
            clip.model.x = clip.model.x - 1
            # Clip automatically saves when Grid saves, and Clip save re-saves
            # whole Grid, so we just save the Grid at the end, which serializes
            # all the ClipModels.
        if to_change:
            self.min_x -= 1
            self.model.save()
            self.view.refresh()

        assert len(self.coordinates_to_clip) == start_size

    def refresh_selected_column(self):
        self.refresh_column(self.main_cursor.model.x)

    def refresh_column(self, screen_x):
        self.make_ranked_clips(in_place=True, force_homerow=True)

    def make_ranked_clips_1(self):
        self.make_ranked_clips(lexical=True)

    def make_ranked_clips_2(self):
        self.make_ranked_clips(secondary_cursor=True, lexical=True)

    def make_ranked_clips_3(self):
        self.make_ranked_clips()

    def make_ranked_clips_4(self):
        self.make_ranked_clips(secondary_cursor=True)

    def make_ranked_clips(self, main_cursor=True, secondary_cursor=False,
                          lexical=False, in_place=False, force_homerow=False):
        # If in-place is true it re-sorts / re-creates the current column.
        # Note: This function is old and crusty and poorly documented. At the
        # moment it is the "sort" used when you give the ctrl-enter command,
        # it should make a new column if needed, and position the clips
        # according to our latest rules/thinking on clip-sorting.

        start_time = datetime.now()

        if not main_cursor and not secondary_cursor:
            raise ValueError

        homerow_screen_y = -self.model.y_offset

        clip = None
        if force_homerow:
            # If True, use screen from main cursor and clip from home row only.
            screen_x = self.main_cursor.model.x
            absolute_x = screen_x + self.model.x_offset
            clip = self.coordinates_to_clip.get((absolute_x, 0))
        else:
            if secondary_cursor:
                screen_x = self.secondary_cursor.model.x
                clip = self.get_secondary_cursor_clip()
            if main_cursor:
                screen_x = self.main_cursor.model.x
                clip = self.get_cursor_clip()

        if not clip:
            # If we are on the home-row then this gives a 'null-search'
            if self.main_cursor.model.y == homerow_screen_y:
                self.status_bar.showMessage('Make Ranked Clips - null search')
                positives = []  # list of (score, key) tuples
                negatives = []  # Should be empty, nothing is its own parent.
                unscoreds = []
                for datum_key in self.active_datums:
                    try:
                        score = self.model.relationships[datum_key][datum_key]
                        score = float(score)
                    except (KeyError, ValueError):
                        score = None
                    if score is not None:
                        positives.append((score, datum_key))
                    else:
                        unscoreds.append(datum_key)
                # Sort  by score descending
                positives = [x[1] for x in sorted(positives, reverse=True)]
                negatives = [x[1] for x in sorted(negatives)]
                unscoreds = sorted(unscoreds,
                                   key=lambda x: get(x).model.last_changed)
                self.insert_column(screen_x)
                for i, datum_key in enumerate(positives+[None]+unscoreds):
                    if datum_key is None:
                        continue
                    datum = get(datum_key)
                    self.new_clip(screen_x, homerow_screen_y + i + 1, datum, 0)
                for i, datum_key in enumerate(negatives):
                    datum = get(datum_key)
                    self.new_clip(screen_x, homerow_screen_y - i - 1, datum, 0)
                self.main_cursor.model.y = homerow_screen_y
                self.main_cursor.model.x = screen_x
                self.main_cursor.model.save()
                self.secondary_cursor.model.y = 0
                self.secondary_cursor.model.x = screen_x + self.model.x_offset
                self.secondary_cursor.model.save()
                self.view.refresh()
                # Perhaps someday we will refactor this monstrosity,
                # TODAY IS NOT THAT DAY!
                return
            self.status_bar.showMessage(
                'Make Ranked Clips fail - no Clip selected')
            return
        self.status_bar.showMessage('Make Ranked Clips on Clip {}'.format(
            clip.datum.model.name
        ))
        center_y = math.floor(self.grid_height / 2.0)

        # This moves the Cursor's column and everything to the left of it
        # over one, a blank column remains at screen_x.
        if in_place:
            # Remove the current column.
            absolute_x = screen_x + self.model.x_offset
            if absolute_x in self.y_upper_bounds:
                for absolute_y in range(self.y_upper_bounds[absolute_x],
                                        self.y_lower_bounds[absolute_x]+1):
                    coords = (absolute_x, absolute_y)
                    if coords not in self.coordinates_to_clip:
                        continue
                    c = self.coordinates_to_clip[coords]
                    del self.coordinates_to_clip[coords]
                    self.model.delete_clip(c.model)
                del self.y_upper_bounds[absolute_x]
                del self.y_lower_bounds[absolute_x]
        else:
            self.insert_column(screen_x)
        # Now the Cursor's (former) Clip is at screen_x-1, and screen_x is
        # where the new Clips are going to go.

        # Get the ranked Clips.

        # - - - start old notes - - -
        # These notes are old, it's what I changed when I went to mammals.
        # score is probabilty of the primary conditioned on the secondary.
        # ApBs - prob A given B = .3
        # CpBs - prob C given B = .2
        #
        # Move primary to B, hit ctrl-enter
        #
        # B copies to home row of next column
        # under is A,
        # under is C
        # model.relationships is stort AgivenB, [A][B]
        # Score and Sort is by Primary(A) given Secondary(B)
        # so you look up [P][S]
        # and you sort looking up item given homerow, [I][H]
        # Here we sort
        # ctrl-enter is:
        # probabilty of the sorted conditioned on the homerow
        # - - - end old notes - - -

        clip_datum_key = clip.model.datum_key
        # Map of ITEM datum_key with float-value of P(I|Homerow)
        positives = []
        unscoreds = []

        # find all 'parents' of clip datum key
        # This is now to - do, because mammals is different than parents, it
        # uses a "is a kind of" relationship.
        # We have ideas for using the distance function, but for now, it's
        # nixed.
        # - - - old parent keys - - -
        # parent_keys = []
        # parent_keys_set = set(parent_keys)
        # current_datum_key = clip_datum_key
        # while True:
        #     d = get(current_datum_key)
        #     current_datum_key = d.model.parent
        #     if current_datum_key and current_datum_key not in parent_keys_set:
        #         parent_keys.append(current_datum_key)
        #         parent_keys_set = set(parent_keys)
        #     else:
        #         break
        # - - - end old parent keys - - -

        # This is the new mammal-based code.
        # Get the term_id for the datum text (it is expected to
        # exactly match a term in the mammals set or the score will
        # be 0.0.)
        # Note: Could cache the dist-calculations
        clip_datum_text = get(clip_datum_key).model.data
        clip_term_id = _term_to_index[clip_datum_text]
        s_e = Variable(_lt[clip_term_id].expand_as(_embedding),
                       volatile=True)
        _dists = _m.dist()(s_e, _embedding).data.cpu().numpy().flatten()

        from app import get_application
        progress = get_application().main_window.progress
        old_min_time = progress.minimumDuration()
        progress.setMinimumDuration(
            max(0, old_min_time - (datetime.now()-start_time).seconds*1000))
        num = len(self.active_datums)
        progress.setRange(0, num)
        progress.reset()
        progress.setLabelText('Getting scores for {} datums'.format(num))

        for i, datum_key in enumerate(self.active_datums):
            progress.setValue(i)
            if datum_key == clip_datum_key: # or datum_key in parent_keys_set:
                continue
            try:
                datum_text = get(datum_key).model.data
                datum_term_id = _term_to_index[datum_text]
                score = _dists[datum_term_id]
                score = float(score)
            except (KeyError, ValueError):
                score = None
            if score is not None:
                positives.append((score, datum_key))
            else:
                unscoreds.append(datum_key)

        progress.setRange(0, 2)
        progress.setMinimumDuration(
            max(0, old_min_time - (datetime.now()-start_time).seconds*1000))
        progress.reset()
        progress.setLabelText('Sorting scores')

        # Sort by score ascending (smaller distance, closer match)
        positives = [x[1] for x in sorted(positives)]
        progress.setValue(1)
        #negatives = parent_keys #[x[1] for x in sorted(negatives)]
        unscoreds = sorted(unscoreds,
                           key=lambda x: get(x).model.last_changed)
        progress.setValue(2)
        #self.insert_column(screen_x)  # already done it above if needed

        datums = positives+[None]+unscoreds
        progress.setRange(0, len(datums)-1)
        progress.setMinimumDuration(
            max(0, old_min_time - (datetime.now()-start_time).seconds*1000))
        progress.reset()
        progress.setLabelText(
            'Creating {} Clips'.format(len(datums)))

        self.new_clip(screen_x, homerow_screen_y, clip.datum, 0, emit=False)
        for i, datum_key in enumerate(datums):
            progress.setValue(i+1)
            if datum_key is None:
                continue
            datum = get(datum_key)
            self.new_clip(screen_x, homerow_screen_y + i + 1, datum, 0,
                          emit=False)

        self.view.clip_changed.emit()
        #for i, datum_key in enumerate(negatives):
        #    datum = get(datum_key)
        #    self.new_clip(screen_x, homerow_screen_y - i - 1, datum, 0)
        self.main_cursor.model.y = homerow_screen_y
        self.main_cursor.model.x = screen_x
        self.main_cursor.model.save()
        self.secondary_cursor.model.y = 0
        self.secondary_cursor.model.x = screen_x + self.model.x_offset
        self.secondary_cursor.model.save()
        self._scroll_cursor(1, 1)
        progress.setMinimumDuration(old_min_time)
        progress.reset()
        self.view.refresh()

    def do_find(self):
        from PyQt5.QtWidgets import QInputDialog, QLineEdit
        text, okPressed = QInputDialog.getText(self.view,
                                               "Get text",
                                               "Your name:",
                                               QLineEdit.Normal, "")
        found = None
        if okPressed and text != '':
            for datum_key in self.active_datums:
                datum = get(datum_key)
                datum_text = datum.model.data
                log.debug(datum_text)
                if text == datum_text:
                    found = datum
                    break
        for (x, y), clip in self.coordinates_to_clip.items():
            if clip.datum == found:
                # scroll to this Clip.
                self.scroll_to_clip(clip)
                return clip
        return None

    def scroll_to_clip(self, clip):
        # Scroll so the given clip is at screen 2, 2
        self.main_cursor.model.x = 2
        self.main_cursor.model.y = 2
        self.model.x_offset = clip.model.x - 2
        self.model.y_offset = clip.model.y - 2
        self.model.save()
        self.view.refresh()

    def _scroll_cursor(self, screen_x, screen_y):
        # Change the offset so that the Cursor's current Clip is at coords.
        cursor_x = self.main_cursor.model.x
        cursor_y = self.main_cursor.model.y
        # Distance to center
        delta_x = cursor_x - screen_x
        delta_y = cursor_y - screen_y
        self.model.x_offset += delta_x
        self.model.y_offset += delta_y
        self.model.save()
        self.main_cursor.model.x = screen_x
        self.main_cursor.model.y = screen_y
        self.main_cursor.model.save()
        self.view.refresh()

    def scroll_cursor_right(self):
        # Change the offset so that the Cursor's current Clip is center right.
        right_x = self.grid_width - 1
        center_y = math.floor(self.grid_height / 2)
        self._scroll_cursor(right_x, center_y)
        return

    def scroll_cursor_center(self):
        center_x = math.floor(self.grid_width / 2)
        center_y = math.floor(self.grid_height / 2)
        self._scroll_cursor(center_x, center_y)

    def scroll_cursor_left(self):
        # Change the offset so that the Cursor's current Clip is center left.
        left_x = 0
        center_y = math.floor(self.grid_height / 2)
        self._scroll_cursor(left_x, center_y)

    def do_column_scroll(self):
        # ctl-l state-machine, center, bottom, top
        screen_x = self.main_cursor.model.x
        if self.last_ctrl_l == 'center':
            # Change offset so homerow is third from top
            self.model.y_offset = -2
            self.model.save()
            self.last_ctrl_l = 'bottom'
            self.status_bar.showMessage('Column Scroll - Bottom')
        elif self.last_ctrl_l == 'bottom':
            abs_x = self.model.x_offset + screen_x
            abs_y = self.y_lower_bounds.get(abs_x, 0)
            self.model.y_offset = -2 + abs_y
            self.model.save()
            self.last_ctrl_l = 'top'
            self.status_bar.showMessage('Column Scroll - Top')
        elif self.last_ctrl_l == 'top':
            abs_x = self.model.x_offset + screen_x
            abs_y = self.y_upper_bounds.get(abs_x, 0)
            self.model.y_offset = -2 + abs_y
            self.model.save()
            self.last_ctrl_l = 'center'
            self.status_bar.showMessage('Column Scroll - Home Row')
        self.view.refresh()

    def do_cycle_parentage(self):
        """Rotate current selection marker thru parentage choices"""
        selection_clip = self.get_cursor_clip()
        marker_clip = self.get_secondary_cursor_clip()
        if not (selection_clip and marker_clip):
            self.status_bar.showMessage(
                'Set Parentage fail - put Selector and Marker on Clips')
            return
        selection_parent_key = selection_clip.datum.model.parent
        marker_key = marker_clip.datum.model.key
        if selection_parent_key == marker_key:
            self.status_bar.showMessage(
                'Set Parentage - Selection ({}) now has no Parent'.format(
                    selection_clip.datum.model.name
                ))
            selection_clip.datum.model.parent = None
        else:
            self.status_bar.showMessage(
"Set Parentage - Marker ({}) is now Selection's ({}) Parent".format(
                marker_clip.datum.model.name, selection_clip.datum.model.name))
            selection_clip.datum.model.parent = marker_key
        selection_clip.datum.model.save()
        self.view.clip_changed.emit()


class Cursor(WrenController):
    model_class = model.CursorModel

    def setup(self):
        super().setup()
        self.grid = get(self.model.grid_key)
        from app import get_application
        get_application().main_window.key_pressed.connect(self.on_key_press)

    def on_key_press(self, event):
        from app import get_application
        if self.grid != get_application().main_window.grid:
            # Not this cursor.
            return
        modifiers = QApplication.keyboardModifiers()
        # Note modifiers can be OR'd together to check for combos.
        shift = modifiers & Qt.ShiftModifier
        ctrl = modifiers & Qt.ControlModifier
        if ctrl:
            return
        meant_for_us = (self.model.name == 'main' and not shift) or \
                       (self.model.name == 'secondary' and shift)
        if not meant_for_us:
            return

        key = event.key()
        if key == Qt.Key_Right:
            self.move_right()
        elif key == Qt.Key_Left:
            self.move_left()
        elif key == Qt.Key_Up:
            self.move_up()
        elif key == Qt.Key_Down:
            self.move_down()
        elif key == Qt.Key_Return and not shift and not ctrl:
            # Set Focus on the cursor's Clip.
            self.grid.status_bar.showMessage('Editing Clip')
            self.grid.set_clip_focus(self.model.x, self.model.y)
        elif key == Qt.Key_Escape:
            self.grid.status_bar.showMessage('Edit Clip complete')
            self.grid.set_cursor_focus()
            self.grid.view.clip_changed.emit()

    def _move(self, direction):
        # Note the Main cursor is screen coords and the secondary is absolute.
        x = self.model.x
        y = self.model.y
        is_main = self.model.name == 'main'
        if is_main:
            name = 'Selection'
        else:
            name = 'Marker'
        self.grid.status_bar.showMessage('{} {}'.format(name, direction))
        if 'right' == direction:
            if x == (self.grid.grid_width - 1) and is_main:
                self.grid.model.x_offset += 1
                self.grid.model.save()
            else:
                self.model.x = x + 1
                self.model.save()
        elif 'left' == direction:
            if x == 0 and is_main:
                self.grid.model.x_offset -= 1
                self.grid.model.save()
            else:
                self.model.x = x - 1
                self.model.save()
        elif 'up' == direction:
            if y == 0 and is_main:
                self.grid.model.y_offset -= 1
                self.grid.model.save()
            else:
                self.model.y = y - 1
                self.model.save()
        elif 'down' == direction:
            if y == (self.grid.grid_height - 1) and is_main:
                self.grid.model.y_offset += 1
                self.grid.model.save()
            else:
                self.model.y = y + 1
                self.model.save()

        self.grid.view.cursor_changed.emit()

    def move_right(self):
        self._move('right')

    def move_left(self):
        self._move('left')

    def move_up(self):
        self._move('up')

    def move_down(self):
        self._move('down')


class Inspector(WrenController):

    def setup(self, grid):
        super().setup()
        from views import InspectorView
        self.grid = grid
        self.view = InspectorView(inspector=self)

    def set_focus(self):
        self.view.text_edit.cursorPositionChanged.connect(
            self.view.on_cursor_position_change)
        self.view.text_edit.setEnabled(True)
        clip = self.grid.get_cursor_clip()
        if clip:
            # Set the Cursor as specified in the model.
            cursor = self.view.text_edit.textCursor()
            cursor.setPosition(clip.model.edit_cursor_position)
            self.view.text_edit.setTextCursor(cursor)
        self.view.text_edit.setFocus()

    def refresh(self):
        # This try block was a kludge, assuming its need bc startup issues.
        try:
            self.view.set_clip(self.clip)
        except AttributeError:
            pass


class Clip(WrenController):
    """Controller for a Text Datum living in a Grid as a Clip."""
    model_class = model.ClipModel

    needs_refresh = pyqtSignal(name='needs_refresh')

    def setup(self):
        super().setup()
        self.datum = get(self.model.datum_key)
        self.grid = get(self.model.grid_key)
        self.is_blank = False

    def set_datum_name(self, datum_name):
        self.datum.set_name(datum_name)

    def set_datum_data(self, datum_data):
        self.datum.set_data(datum_data)

    def refresh(self):
        self.needs_refresh.emit()


def _init_model_to_controller_map():
    for name in globals():
        cls = eval(name)
        if isclass(cls):
            if issubclass(cls, WrenController):
                MODEL_TO_CONTROLLER[cls.model_class.__name__] = cls
_init_model_to_controller_map()
