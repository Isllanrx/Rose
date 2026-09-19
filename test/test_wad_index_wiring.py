"""The WAD index build hooked into InjectionManager's background init.

The index is a convenience: injection has always worked without it. So the wiring
is only correct if it can never raise, never block and never take precedence over
initialisation. These tests pin exactly that.
"""

import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from injection.compat import wad_index as wi
from injection.core.manager import InjectionManager

MODULE = "injection.core.manager"


def make_manager(game_dir=None, injector_game_dir=None):
    """A manager with its heavy collaborators stubbed out."""
    with mock.patch(f"{MODULE}.ThresholdManager"), mock.patch(f"{MODULE}.GameMonitor"):
        manager = InjectionManager(game_dir=game_dir)
    if injector_game_dir is not None:
        manager.injector = mock.Mock(game_dir=injector_game_dir)
    return manager


class IndexBuildNeverBreaksInitialisation(unittest.TestCase):
    def test_build_failure_does_not_raise(self):
        manager = make_manager(game_dir=Path("C:/nao-existe"))
        with mock.patch(f"{MODULE}.ensure_index_built", return_value=False):
            manager._prepare_wad_index()  # must simply return

    def test_unexpected_exception_is_swallowed(self):
        manager = make_manager(game_dir=Path("C:/qualquer"))
        with mock.patch(f"{MODULE}.ensure_index_built", side_effect=RuntimeError("boom")):
            manager._prepare_wad_index()

    def test_default_index_path_failure_is_swallowed(self):
        manager = make_manager(game_dir=Path("C:/qualquer"))
        with mock.patch(f"{MODULE}.default_index_path", side_effect=OSError("sem disco")):
            manager._prepare_wad_index()

    def test_unknown_game_folder_skips_the_build(self):
        manager = make_manager(game_dir=None)
        with mock.patch(f"{MODULE}.ensure_index_built") as build:
            manager._prepare_wad_index()
        build.assert_not_called()

    def test_missing_injector_attribute_is_tolerated(self):
        """Initialisation can fail before self.injector is ever assigned."""
        manager = make_manager(game_dir=Path("C:/jogo"))
        del manager.injector
        with mock.patch(f"{MODULE}.ensure_index_built", return_value=True) as build:
            manager._prepare_wad_index()
        build.assert_called_once()


class IndexBuildUsesTheDetectedGameFolder(unittest.TestCase):
    def test_injector_game_dir_wins_over_the_constructor_argument(self):
        manager = make_manager(game_dir=Path("C:/informado"),
                               injector_game_dir=Path("D:/detectado"))
        with mock.patch(f"{MODULE}.ensure_index_built", return_value=True) as build:
            manager._prepare_wad_index()
        self.assertEqual(build.call_args.args[0], Path("D:/detectado"))

    def test_falls_back_to_the_constructor_argument(self):
        manager = make_manager(game_dir=Path("C:/informado"))
        manager.injector = mock.Mock(game_dir=None)
        with mock.patch(f"{MODULE}.ensure_index_built", return_value=True) as build:
            manager._prepare_wad_index()
        self.assertEqual(build.call_args.args[0], Path("C:/informado"))


class BackgroundInitAlwaysReachesTheIndex(unittest.TestCase):
    def test_index_is_prepared_even_when_initialisation_raises(self):
        manager = make_manager(game_dir=Path("C:/jogo"))
        manager._initialized = False
        done = threading.Event()

        with mock.patch.object(manager, "_ensure_initialized",
                               side_effect=RuntimeError("init falhou")), \
             mock.patch.object(manager, "_prepare_wad_index",
                               side_effect=lambda: done.set()):
            manager.initialize_when_ready()
            self.assertTrue(done.wait(timeout=5), "index build was never reached")

    def test_the_background_thread_is_named_and_daemonised(self):
        manager = make_manager(game_dir=Path("C:/jogo"))
        manager._initialized = False
        captured = {}

        real_thread = threading.Thread

        def capture(*args, **kwargs):
            thread = real_thread(*args, **kwargs)
            captured["name"] = kwargs.get("name")
            captured["daemon"] = kwargs.get("daemon")
            return thread

        with mock.patch.object(manager, "_ensure_initialized"), \
             mock.patch.object(manager, "_prepare_wad_index"), \
             mock.patch("threading.Thread", side_effect=capture):
            manager.initialize_when_ready()

        self.assertEqual(captured.get("name"), "InjectionInit")
        self.assertTrue(captured.get("daemon"))


class IndexLivesOutsideTheGameFolder(unittest.TestCase):
    def test_default_path_is_under_the_state_directory(self):
        with mock.patch("utils.core.paths.get_state_dir",
                        return_value=Path("C:/estado")) as state_dir:
            path = wi.default_index_path()
        state_dir.assert_called_once()
        self.assertEqual(path, Path("C:/estado") / "wad_index.bin")

    def test_ensure_index_built_leaves_no_open_handle(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            game = root / "Game"
            game.mkdir()
            (game / wi._CONTENT_METADATA).write_text('{"version": "16.18.1"}', encoding="utf-8")

            from test.test_wad_index import make_wad
            make_wad(game / "a.wad.client", [1, 2, 3])
            index_path = root / "wad_index.bin"

            self.assertTrue(wi.ensure_index_built(game, index_path))
            # Windows refuses to replace a file that is still mapped or open.
            self.assertTrue(wi.ensure_index_built(game, index_path))
            index_path.unlink()

    def test_ensure_index_built_reports_failure_without_raising(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertFalse(wi.ensure_index_built(root / "sem-jogo", root / "idx.bin"))


if __name__ == "__main__":
    unittest.main()
