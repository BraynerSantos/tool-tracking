# PyInstaller spec — run from repo root: pyinstaller tooldb.spec
a = Analysis(
    ["app/main.py"],
    pathex=["."],
    binaries=[],
    datas=[("client/dist", "client/dist")],
    hiddenimports=["uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
                   "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
                   "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
                   "uvicorn.lifespan", "uvicorn.lifespan.on"],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ToolDB",
          console=False, disable_windowed_traceback=False)  # windowed: no terminal
coll = COLLECT(exe, a.binaries, a.datas, name="ToolDB")
