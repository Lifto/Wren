
from datetime import datetime, timedelta
import json
import os
import pytz
import sqlite3
from uuid import uuid1

from wren import IDMap, log
from exceptions import NotFound


_STORAGE = None
def get_storage():
    """Main persistent data storage (sqlite3)"""
    global _STORAGE
    if _STORAGE is None:
        # See if its already on disk
        # TODO: We don't specify a filename, it's always the default.
        _STORAGE = WrenData.initialize()
    return _STORAGE

_MODEL_ID_MAP = None
def get_model_id_map():
    """Holds singleton Controllers"""
    global _MODEL_ID_MAP
    if _MODEL_ID_MAP is None:
        _MODEL_ID_MAP = IDMap()
    return _MODEL_ID_MAP

def get_model(key):
    """Get id-mapped singleton Model object for the given key"""
    id_map = get_model_id_map()
    model = id_map.get(key)
    if model is None:
        model = WrenModel.load(key)
        id_map.set(key, model)
    return model


epoch = datetime(1970, 1, 1, tzinfo=pytz.utc)
def unix_time(dt):
    delta = dt - epoch
    return int(delta.total_seconds()*10000000)


def from_unix_time(ut):
    return epoch + timedelta(seconds=(ut / 10000000.0))


class WrenData:
    """
    Persistent data storage for Wren

    Implemented with a sqlite3 database. Creates the file 'wren_temp.db' as
    a working default db.

    This is a key-type-value store, it returns a string. Each element has
    to stuff its data into a string (suggest: json, with text uuid as key.)

    """
    def __init__(self, file_name='wren_temp.db'):
        self.conn = sqlite3.connect(file_name)

    @staticmethod
    def initialize(file_name='wren_temp.db'):
        """Creates file if does not exist."""
        if file_name != ':memory' and os.path.isfile(file_name):
            # Assume it is correct, user can delete and recreate if it's not.
            return WrenData(file_name=file_name)
        # Note if you close the connection to a :memory: db it disappears.

        log.info("Creating temp file {file_name}".format(file_name=file_name))

        # This creates the file when it calls conn = sqlite3.connect(file_name)
        wren_data = WrenData(file_name=file_name)

        # Create the database and table
        #conn.execute('CREATE DATABASE ?;', ('main',))
        cmd = """CREATE TABLE kvs (key varchar(100),
                                   kind varchar(100),
                                   value varchar(10000),
                                   PRIMARY KEY (key));"""
        wren_data.conn.execute(cmd)
        return wren_data

    def get(self, key):
        cmd = 'SELECT kind, value FROM kvs WHERE key=?'
        result = self.conn.execute(cmd, (key,)).fetchone()
        if result is None:
            raise NotFound
        return result

    def write(self, key, kind, value):
        cmd = 'REPLACE INTO kvs (key, kind, value) VALUES (?, ?, ?)'
        self.conn.execute(cmd, (key, kind, value))
        self.conn.commit()


class WrenModel:
    """Baseclass for grid model objects that save and load to storage"""
    def __init__(self, key=None):
        """Model creates its own unique key if not supplied."""
        if key is None:
            key = uuid1().hex
        self.key = key
        get_model_id_map().set(key, self)

    def save(self):
        get_storage().write(self.key, type(self).__name__, self.serialize())

    @staticmethod
    def load(key):
        kind, serialized_value = get_storage().get(key)
        cls = eval(kind)
        return cls.deserialize(key, serialized_value)

    def serialize(self):
        raise NotImplementedError

    @staticmethod
    def deserialize(key, serialized_value):
        raise NotImplementedError


class ApplicationModel(WrenModel):
    """Model for top-level elements in Wren."""
    def __init__(self, grids=None, current_grid=None, key=None):
        super().__init__(key=key)
        if grids is None:
            self.grids = set()
        else:
            assert(isinstance(grids, set))
            self.grids = grids
        self.current_grid = current_grid

    @staticmethod
    def deserialize(key, serialized_value):
        key, grids, current_grid = json.loads(serialized_value)
        grids = set(grids)
        return ApplicationModel(key=key,
                                grids=grids,
                                current_grid=current_grid)

    def serialize(self):
        return json.dumps([self.key, list(self.grids), self.current_grid])


class CursorModel(WrenModel):
    def __init__(self, grid_key, x, y, name, key=None):
        super().__init__(key=key)
        self.grid_key = grid_key
        self.x = x
        self.y = y
        self.name = name

    def save(self):
        """Cursors save to their parent grid"""
        get_model(self.grid_key).save()

    @staticmethod
    def deserialize(serialized_value):
        key, grid_key, x, y, name = json.loads(serialized_value)
        return CursorModel(grid_key, x, y, name, key=key)

    def serialize(self):
        return json.dumps([self.key, self.grid_key, self.x, self.y, self.name])


class ClipModel(WrenModel):
    """Key to a datum, x pos and y pos"""
    # Note this is internal to GridModel, as there is no Clip without a grid
    # that it is in, and they have exclusive position within that grid. They
    # may not be present in more than one grid.
    def __init__(self, grid_key, datum_key, absolute_x, absolute_y,
                 edit_cursor_position, key=None):
        super().__init__(key=key)
        self.grid_key = grid_key
        self.datum_key = datum_key
        self.x = absolute_x
        self.y = absolute_y
        self.edit_cursor_position = edit_cursor_position

    def save(self):
        """Clips save to their parent grid"""
        parent_model = get_model(self.grid_key)
        parent_model.save_clip(self)

    @staticmethod
    def deserialize(serialized_value):
        key, grid_key, datum_key, x, y, edit_cursor_position = json.loads(
            serialized_value)
        return ClipModel(grid_key, datum_key, x, y, edit_cursor_position,
                         key=key)

    def serialize(self):
        return json.dumps([self.key, self.grid_key, self.datum_key,
                           self.x, self.y, self.edit_cursor_position])


class GridModel(WrenModel):
    """Model for a grid of individual datums"""
    # Note this is implemented as if the entire grid is just a single row
    # in the database. We may want something a little bit more integrated with
    # the database for queries, but this is good for now.
    def __init__(self, key=None, clip_models=(), cursor_models=None,
                 relationships=None, x_offset=None, y_offset=None,
                 active_datums=None,
                 clipboard_datum_key=None):
        super().__init__(key=key)
        self.clip_models = clip_models
        if cursor_models is None:
            cursor_models = {}
        if 'main' in cursor_models:
            self.main_cursor_model = cursor_models['main']
        else:
            self.main_cursor_model = CursorModel(self.key, 2, 2, 'main')
        if 'secondary' in cursor_models:
            self.secondary_cursor_model = cursor_models['secondary']
        else:
            self.secondary_cursor_model = CursorModel(self.key, 2, 2,
                                                      'secondary')
        if relationships is None:
            relationships = {}
        self.relationships = relationships

        if x_offset is None:
            x_offset = 0
        if y_offset is None:
            y_offset = -2
        self.x_offset = x_offset
        self.y_offset = y_offset
        if active_datums is None:
            active_datums = []
        self.active_datums = active_datums  # datum_keys
        self.clipboard_datum_key = clipboard_datum_key

    @staticmethod
    def deserialize(key, serialized_value):
        s_clips, cursor_models, relationships, x_offset, y_offset,\
            active_datums, clipboard_datum_key = json.loads(
            serialized_value)
        clip_models = [ClipModel.deserialize(c) for c in s_clips]
        main_cursor_model = CursorModel.deserialize(cursor_models['main'])
        secondary_cursor_model = CursorModel.deserialize(cursor_models[
                                                             'secondary'])
        return GridModel(key=key,
                         clip_models=tuple(clip_models),
                         cursor_models={
                             'main': main_cursor_model,
                             'secondary': secondary_cursor_model
                         },
                         relationships=relationships,
                         x_offset=x_offset,
                         y_offset=y_offset,
                         active_datums=active_datums,
                         clipboard_datum_key=clipboard_datum_key)

    def serialize(self):
        return json.dumps([[c_m.serialize() for c_m in self.clip_models],
                           {
                               'main': self.main_cursor_model.serialize(),
                               'secondary':
                                   self.secondary_cursor_model.serialize()
                           },
                           self.relationships,
                           self.x_offset, self.y_offset,
                           self.active_datums,
                           self.clipboard_datum_key])

    def save_clip(self, clip_model):
        assert isinstance(clip_model, ClipModel)
        # remove existing data on this clip if it exists
        index = None
        for i, existing_clip_model in enumerate(self.clip_models):
            if existing_clip_model.key == clip_model.key:
                index = i
                break
        if index is not None:
            assert isinstance(self.clip_models, tuple)
            self.clip_models = self.clip_models[:index] + self.clip_models[
                index + 1:]
            # Same as: del self.clip_models[index] would be on a list.
        # Add this clip to the model and save.
        self.clip_models = self.clip_models + (clip_model,)
        self.save()

    def delete_clip(self, clip_model):
        assert isinstance(clip_model, ClipModel)
        # remove existing data on this clip if it exists
        index = None
        for i, existing_clip_model in enumerate(self.clip_models):
            if existing_clip_model.key == clip_model.key:
                index = i
                break
        if index is not None:
            assert isinstance(self.clip_models, tuple)
            self.clip_models = self.clip_models[:index] + self.clip_models[
                index + 1:]
            # Same as: del self.clip_models[index] would be on a list.
        # Don't add this clip to the model and save.
        # self.clip_models = self.clip_models + (clip_model,)
        self.save()


class DatumModel(WrenModel):
    """Model for multimedia datum, Wren's primitive"""
    def __init__(self, data, name=None, key=None, last_changed=None,
                 parent=None):
        super().__init__(key=key)
        if name is None:
            from app import get_application
            name = get_application().get_next_name()
        self.name = name
        self.data = data
        if last_changed is None:
            last_changed = datetime.now(tz=pytz.utc)
        self.last_changed = last_changed
        self.parent = parent

    def serialize(self):
        return json.dumps([self.data, self.name,
                           unix_time(self.last_changed),
                           self.parent])

    @classmethod
    def deserialize(cls, key, serialized_value):
        data, name, last_changed, parent = json.loads(serialized_value)
        return cls(data, name=name, key=key,
                   last_changed=from_unix_time(last_changed),
                   parent=parent)


def get_datum_by_name(name):
    # A hack, we look up a Text, which descends from Datum.
    kind = DatumModel.__name__
    cmd = 'SELECT key, value FROM kvs WHERE kind=?'
    #cmd = 'SELECT key, kind, value FROM kvs'
    for key, value in get_storage().conn.execute(cmd, (kind,)).fetchall():
    #for key, kind, value in get_storage().conn.execute(cmd).fetchall():
        datum_model = DatumModel.deserialize(key, value)
        if datum_model.name == name:
            return datum_model
    return None

