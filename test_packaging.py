"""Tests for the deployment files: the PyInstaller recipe and the launcher.

Neither can be checked by starting the app, and a broken recipe or launcher
only fails later on the machine that tries to use it. These tests read the
files as text and evaluate the spec against stub build steps, so a
flattened or hand-edited recipe fails here instead.
"""

import sys
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent
SPEC = ROOT / "portfoliox.spec"
LAUNCHER = ROOT / "start.bat"
BUILD_REQUIREMENTS = ROOT / "requirements-build.txt"

# Folders that hold the live database and personal material. Shipping them
# inside a build would publish them.
PRIVATE_FOLDERS = {"data", "backups", "exports", "referance"}

CALLS = {}


class _Block:
    """Stand-in for a PyInstaller build step: records how it was called."""

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.pure = []
        self.scripts = []
        self.binaries = []
        self.datas = []
        CALLS[type(self).__name__] = self


class _Analysis(_Block):
    pass


class _PYZ(_Block):
    pass


class _EXE(_Block):
    pass


class _COLLECT(_Block):
    pass


def _fake_pyinstaller():
    """Just enough of PyInstaller's hooks module to execute the spec."""

    hooks = types.ModuleType("PyInstaller.utils.hooks")
    hooks.collect_data_files = lambda package: [("theme.json", package)]
    hooks.collect_submodules = lambda package: [f"{package}.Windows"]

    utils = types.ModuleType("PyInstaller.utils")
    utils.hooks = hooks

    root = types.ModuleType("PyInstaller")
    root.utils = utils

    return {
        "PyInstaller": root,
        "PyInstaller.utils": utils,
        "PyInstaller.utils.hooks": hooks,
    }


def build_spec():
    """Execute the spec with stubbed build steps and return their calls."""

    CALLS.clear()
    namespace = {
        "Analysis": _Analysis,
        "PYZ": _PYZ,
        "EXE": _EXE,
        "COLLECT": _COLLECT,
    }
    source = SPEC.read_text(encoding="utf-8")

    with mock.patch.dict(sys.modules, _fake_pyinstaller()):
        exec(compile(source, str(SPEC), "exec"), namespace)

    return dict(CALLS)


class SpecTest(unittest.TestCase):
    def setUp(self):
        calls = build_spec()
        self.analysis_call = calls["_Analysis"]
        self.analysis = calls["_Analysis"].kwargs
        self.exe = calls["_EXE"].kwargs
        self.collect = calls["_COLLECT"].kwargs

    def test_entry_point_is_app_py(self):
        self.assertEqual(self.analysis_call.args[0], ["app.py"])

    def test_private_folders_are_not_bundled(self):
        destinations = {destination for _, destination in self.analysis["datas"]}

        self.assertEqual(destinations & PRIVATE_FOLDERS, set())

    def test_assets_are_bundled(self):
        self.assertIn(("assets", "assets"), self.analysis["datas"])
        # Git does not store empty directories, so the folder must carry a
        # tracked file or a fresh clone cannot run the build recipe.
        self.assertTrue((ROOT / "assets").is_dir())
        self.assertTrue(any((ROOT / "assets").iterdir()))

    def test_build_is_a_folder_without_a_console_window(self):
        self.assertTrue(self.exe["exclude_binaries"])
        self.assertFalse(self.exe["console"])

    def test_executable_and_folder_share_the_name(self):
        self.assertEqual(self.exe["name"], "PortfolioX")
        self.assertEqual(self.collect["name"], "PortfolioX")

    def test_heavy_optional_libraries_stay_out(self):
        for name in ("yfinance", "pandas", "numpy"):
            self.assertIn(name, self.analysis["excludes"])

    def test_dynamic_imports_are_declared(self):
        for name in ("customtkinter", "pypdf", "sqlite3"):
            self.assertIn(name, self.analysis["hiddenimports"])

        # Keyring picks its backend at runtime, so the collector must supply it.
        self.assertIn("keyring.backends.Windows", self.analysis["hiddenimports"])

    def test_recipe_is_not_a_flattened_artifact(self):
        source = SPEC.read_text(encoding="utf-8")

        # The previous recipe had been flattened into one line by a tool: it
        # kept a stale Python 3.13 TOC reference and a string block cipher.
        self.assertNotIn("py313", source)
        self.assertNotIn('block_cipher = "aes"', source)


class LauncherTest(unittest.TestCase):
    def setUp(self):
        # ASCII decoding also proves the file has no non-ASCII bytes, which
        # cmd.exe would render as mojibake.
        self.source = LAUNCHER.read_text(encoding="ascii")
        self.raw = LAUNCHER.read_bytes()

    def test_runs_from_its_own_folder(self):
        self.assertIn('cd /d "%~dp0"', self.source)

    def test_does_not_hardcode_an_install_path(self):
        self.assertNotRegex(self.source.lower(), r'cd /d "[a-z]:')

    def test_uses_the_virtual_environment_beside_it(self):
        self.assertIn(r"%~dp0.venv\Scripts\python.exe", self.source)
        self.assertIn("app.py", self.source)

    def test_explains_how_to_create_a_missing_environment(self):
        self.assertIn("python -m venv .venv", self.source)
        self.assertIn("pause", self.source)

    def test_uses_windows_line_endings(self):
        self.assertNotIn(b"\n", self.raw.replace(b"\r\n", b""))

    def test_has_no_byte_order_mark(self):
        self.assertFalse(self.raw.startswith(b"\xef\xbb\xbf"))


class BuildRequirementsTest(unittest.TestCase):
    def test_pins_pyinstaller_and_includes_runtime_requirements(self):
        text = BUILD_REQUIREMENTS.read_text(encoding="utf-8").lower()

        self.assertIn("pyinstaller==", text)
        self.assertIn("-r requirements.txt", text)


if __name__ == "__main__":
    unittest.main()
