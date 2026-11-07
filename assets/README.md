# Bundled assets

Anything in this folder is copied into the built app by `portfoliox.spec`
(`datas = [("assets", "assets")]`). The app currently draws its whole theme
from `ui/theme.py`, so the folder only needs to exist for the build recipe;
add icons, images or theme files here as they are needed.

The `.gitkeep` file keeps the folder in a fresh clone — Git does not store
empty directories, and without it a clone has no `assets/` for PyInstaller
to bundle.
