
import unittest

from wren import log

# Note: This are old and not used so they may not work anymore.

class BaseTestCase(unittest.TestCase):

    def setUp(self):
        import model
        model._STORAGE = model.WrenData.initialize(file_name=':memory:')
        model.get_model_id_map()._reset()
        import controllers
        controllers.get_controller_id_map()._reset()
        import app
        app._APPLICATION = None
        app.get_application().init_data()

    def tearDown(self):
        import controllers
        controllers.get_controller_id_map()._reset()
        import model
        model.get_model_id_map()._reset()
        import app
        app._APPLICATION = None
        app.get_application().init_data()

    def test_clip_grid_init_save_and_load(self):
        from model import GridModel

        grid_model = GridModel()
        self.assertIsNotNone(grid_model.key)
        self.assertEqual(0, len(grid_model.clip_models))
        key = grid_model.key

        grid_model.save()

        grid_model_2 = GridModel.load(key)

        self.assertEqual(key, grid_model_2.key)
        self.assertEqual(0, len(grid_model_2.clip_models))


    def test_clip_grid_add(self):
        from model import ClipModel, GridModel, TextModel

        grid_model = GridModel()
        self.assertIsNotNone(grid_model.key)
        self.assertEqual(0, len(grid_model.clip_models))
        key = grid_model.key

        grid_model.save()
        # temp
        grid_model.load(key)

        x = 1
        y = 2
        datum_model = TextModel('testtext1')
        datum_model.save()
        datum_key = datum_model.key
        clip_model = ClipModel(key, datum_key, x, y)

        # This is how the Clip controller saves.
        # Normally you call clip_model.save(), this is clearbox.
        grid_model.save_clip(clip_model)
        self.assertEqual(1, len(grid_model.clip_models))
        clip_model_1 = grid_model.clip_models[0]
        self.assertEqual(datum_key, clip_model_1.datum_key)
        self.assertEqual(x, clip_model_1.x)
        self.assertEqual(y, clip_model_1.y)

        grid_model_2 = GridModel.load(key)
        self.assertEqual(1, len(grid_model_2.clip_models))
        clip_model_1 = grid_model_2.clip_models[0]
        self.assertEqual(datum_key, clip_model_1.datum_key)
        self.assertEqual(x, clip_model_1.x)
        self.assertEqual(y, clip_model_1.y)

        x_2 = 3
        y_2 = 12
        datum_2_model = TextModel('testtext1')
        datum_2_model.save()
        datum_2_key = datum_2_model.key
        clip_2_model = ClipModel(key, datum_2_key, x, y)
#        with self.assertRaises(ValueError):
#            grid_model.save_clip(clip_2_model)

        clip_2_model = ClipModel(key, datum_2_key, x_2, y_2)
        grid_model.save_clip(clip_2_model)
        self.assertEqual(2, len(grid_model.clip_models))
        clip_model_2 = grid_model.clip_models[1]
        self.assertEqual(datum_2_key, clip_model_2.datum_key)

        grid_model_2 = GridModel.load(key)
        self.assertEqual(2, len(grid_model_2.clip_models))
        clip_model_2 = grid_model_2.clip_models[1]
        self.assertEqual(datum_2_key, clip_model_2.datum_key)

        self.assertDictEqual({}, grid_model_2.relationships)
        datum_a = TextModel('a')
        datum_a.save()
        datum_b = TextModel('b')
        datum_b.save()
        datum_c = TextModel('c')
        datum_c.save()
        grid_model_2.relationships[datum_a.key] = {
            datum_b.key: 42
        }
        grid_model_2.save()

        grid_model_3 = GridModel.load(key)
        self.assertDictEqual(
            {datum_a.key: {datum_b.key: 42}},
            grid_model_3.relationships
        )



    def test_storage_remembers_type(self):
        from model import TextModel, EquationModel, ImageModel, WrenModel
        text_model = TextModel('text1')
        text_model.save()
        equation_model = EquationModel('equation1')
        equation_model.save()
        image_model = ImageModel('image1')
        image_model.save()

        self.assertIsInstance(WrenModel.load(text_model.key),
                              TextModel)
        self.assertIsInstance(WrenModel.load(equation_model.key),
                              EquationModel)
        self.assertIsInstance(WrenModel.load(image_model.key),
                              ImageModel)

    def test_failed_load(self):
        from model import GridModel, NotFound
        with self.assertRaises(NotFound):
            GridModel.load('key_that_does_not_exist')

    def test_create_save_and_load_of_application(self):
        from controllers import get, get_controller_id_map, Grid
        from model import NotFound, get_model_id_map, GridModel

        # Note: Don't use 'get' or Model.create (which calls get) unless you
        # create a PyQt5 Application, which we are avoiding in tests at the
        # moment.
        model = GridModel.load('main_grid')
        self.assertIsInstance(model, GridModel)

    def test_get(self):
        from app import get_application
        app = get_application()
        app.init_ui()
        self.assertIsNotNone(app)

        from controllers import get
        grid = get('main_grid')

    def test_get_text_and_commands(self):
        from parse import get_text_and_commands
        expect = [('text', '')]
        cmd = ''
        self.assertEqual(expect, get_text_and_commands(cmd))

        expect = [('declaration', ('a', 'foo'))]
        cmd = '#a:foo'
        self.assertEqual(expect, get_text_and_commands(cmd))

        expect = [('declaration', ('bar', 'foo+&foo'))]
        cmd = '#bar:foo+&foo'
        self.assertEqual(expect, get_text_and_commands(cmd))

        #expect = [('equation', 'x=y^3')]
        #cmd = '#e|x=y^3'
        #self.assertEqual(expect, get_text_and_commands(cmd))

#        expect = [('image', 'foo')]
#        cmd = '#i|foo'
#        self.assertEqual(expect, get_text_and_commands(cmd))

        #expect = [('probability', '.5')]
        #cmd = '#p=.5'
        #self.assertEqual(expect, get_text_and_commands(cmd))

        # from model import TextModel
        # datum = TextModel('', key='key2', name='key2')
        # datum.save()
        # expect = [('conditional_probability', ('key2', '.25'))]
        # cmd = '#p|key2=.25'
        # self.assertEqual(expect, get_text_and_commands(cmd))
        #
        # expect = [('flag', 'customflag')]
        # cmd = '#customflag'
        # self.assertEqual(expect, get_text_and_commands(cmd))

    def test_evaluator_errors(self):
        from app import get_application
        get_application().init_ui()

        from controllers import BlankClip, get, Text, TextClip
        from model import GridModel
        grid_model = GridModel(key='test_grid')
        grid_model.save()
        grid = get('test_grid')
        self.assertIsNotNone(grid)

        grid.eval_declarations()
        for y in range(2):
            for x in range(5):
                text = Text.create('')

                # This is a hack to avoid some UI stuff during tests.
                clip = TextClip.create(grid.model.key, text.model.key, x, y)
                grid.coordinates_to_clip[(x, y)] = clip
                #grid.add_text(text, x, y)
        grid.eval_declarations()

        # Declare an attribute on all Datums
        cmd = '#*foo:22'
        star_declaration = grid.coordinates_to_clip[(1, 0)]
        star_declaration.datum.model.data = cmd
        star_declaration.datum.model.save()
        grid.eval_declarations()
        self.assertEqual({'foo': '22'}, grid.grid_declarations)
        self.assertEqual({}, grid.declarations_by_clip)

        # Test error handling
        def _check_subcommands(cmd, clip):
            for i in range(len(cmd)):
                subcmd = cmd[:i+1]
                clip.datum.model.data = subcmd
                clip.datum.model.save()
                #log.info('---check subcommand {0}'.format(subcmd))
                grid.eval_declarations()

        clip = grid.coordinates_to_clip[(4, 0)]
        cmd = '#*bar:22'
        _check_subcommands(cmd, clip)
        cmd = '#*bar:22\n#bar+bar'
        _check_subcommands(cmd, clip)

        self.assertEqual({'foo': '22', 'bar': '22'}, grid.grid_declarations)
        self.assertEqual({}, grid.declarations_by_clip)

    def test_evaluator(self):
        from app import get_application
        get_application().init_ui()

        from controllers import BlankClip, get, Text, TextClip
        from model import GridModel
        grid_model = GridModel(key='test_grid')
        grid_model.save()
        grid = get('test_grid')
        self.assertIsNotNone(grid)

        grid.eval_declarations()
        for y in range(2):
            for x in range(5):
                text = Text.create('')

                # This is a hack to avoid some UI stuff during tests.
                clip = TextClip.create(grid.model.key, text.model.key, x, y)
                grid.coordinates_to_clip[(x, y)] = clip
                # grid.add_text(text, x, y)
        grid.eval_declarations()

        cmd1 = '#*foo:22\n#*bar:foo+&foo'
        cmd2 = '#foo\n#bar\n#foo:42'

        cursor_clip = grid.get_cursor_clip()
        self.assertIsInstance(cursor_clip, BlankClip)
        secondary_cursor_clip = grid.get_secondary_cursor_clip()
        self.assertIsInstance(secondary_cursor_clip, BlankClip)

        cmd1_x = 2
        cmd1_y = 0
        cmd2_x = 4
        cmd2_y = 1
        grid.main_cursor.model.x = cmd2_x
        grid.main_cursor.model.y = cmd2_y
        grid.main_cursor.model.save()
        grid.secondary_cursor.model.x = cmd1_x
        grid.secondary_cursor.model.y = cmd1_y
        grid.secondary_cursor.model.save()

        cmd1_clip = grid.coordinates_to_clip[(cmd1_x, cmd1_y)]
        cmd1_clip.datum.model.data = cmd1
        cmd1_clip.datum.model.save()
        cmd2_clip = grid.coordinates_to_clip[(cmd2_x, cmd2_y)]
        cmd2_clip.datum.model.data = cmd2
        cmd2_clip.datum.model.save()

        self.assertIs(cmd2_clip, grid.get_cursor_clip())
        self.assertIs(cmd1_clip, grid.get_secondary_cursor_clip())

        grid.eval_declarations()
        self.assertEqual({'foo': '22', 'bar': 'foo+&foo'},
                         grid.grid_declarations)
        self.assertEqual({cmd2_clip.datum.model.name: {'foo': '42'}},
                         grid.declarations_by_clip)

        # This simulates what the inspector does, which is request a parse
        # of the text of a datum into 'text' and various code snippets,
        # and then evaluating the code one-by-one.

        from parse import get_text_and_commands
        tac = get_text_and_commands(cmd2)
        self.assertEqual(
            [('evaluation', 'foo'),
             ('evaluation', 'bar'),
             ('declaration', ('foo', '42'))], tac)

        from parse import evaluate
        result = evaluate(tac[0][1], grid, clip=cmd2_clip)
        self.assertEqual([('value', 42)], result)
        result = evaluate(tac[1][1], grid, clip=cmd2_clip)
        self.assertEqual([('value', 64)], result)
        # for kind, text in get_text_and_commands(cmd2):
        #     if kind == 'text':
        #         cursor.insertText(text)
        #     elif kind == 'declaration':
        #         # TODO: Get \ns from the original text
        #         cursor.insertText('{0}: {1}\n'.format(*text))
        #     elif kind == 'star_declaration':
        #         cursor.insertText('*{0}: {1}\n'.format(*text))
        #     elif kind == 'evaluation':
        #         from parse import evaluate
        #         got = evaluate(text, clip.grid, clip=clip)
        #         if len(got) == 1 and \
        #                         len(got[0]) == 2 and \
        #                         got[0][0] == 'value':
        #             cursor.insertText('{0}\n'.format(str(got[0][1])))
        #         else:
        #             cursor.insertText(text)
        #     else:  # Unknown
        #         pass


                #     star_datum.set_data('#foo:.2')
        # Declare a specific value on one Datum
        # Declare no value on another Datum
        # Test: Lookup the value on all Datums
        # Declare a foo+1 function on all Datums
        # Declare a specific function on one Datum
        # Declare no function on another Datum
        # Test: Test the function on all Datums
        # Declare a @foo+&bar+1 function on all Datums
        # Declare a specific function on one Datum
        # Declare no function on another Datum
        # Test: Test the function on all Datums, using other Datums as the
        # cursor.




