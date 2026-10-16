# -*- mode: python ; coding: utf-8 -*-
# Slim build: the cats are drawn with QPainter (raster), so OpenGL/ANGLE,
# QML/Quick and translations are not needed. QtMultimedia (+QtNetwork) plays the standoff sound.
DROP = ('opengl32sw', 'd3dcompiler', 'libglesv2', 'libegl', 'qt5quick', 'qt5qml',
        'qt5dbus', 'qt5websockets', 'qwebgl', 'qminimal', 'qoffscreen', 'libssl', '_ssl')

a = Analysis(['src/companion.py'], pathex=['src'], datas=[('images', 'images'), ('sounds', 'sounds')],
             hiddenimports=['PyQt5.QtMultimedia'],
             excludes=['ssl', 'PyQt5.QtQml', 'PyQt5.QtQuick', 'tkinter', 'unittest', 'pydoc'])
a.binaries = [b for b in a.binaries if not any(d in b[0].lower().replace('\\', '/').split('/')[-1] for d in DROP)]
a.datas = [d for d in a.datas if 'translations' not in d[0].lower()]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='JianzhouCat', debug=False, strip=False,
          upx=False, runtime_tmpdir=None, console=False, icon=['images/cat.ico'])
