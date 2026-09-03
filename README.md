Quickpanel is a small popup desktop which supports widgets and desktop icons. When activated, it is shown at the center of screen.

![screenshot](images/screenshot.jpg)

Quickpanel can be run in KDE desktop and windows.

Use it in KDE Desktop:

    $ zypper install python-qt5

    $ git clone git@github.com:hgoldfish/quickpanel.git
    $ cd quickpanel
    $ python3 compile_files.py
    $ python3 start_quickpanel.py

After quickpanel started, a system tray icon shown at the right bottom of your desktop. Click it or press Alt + `, shows the quickpanel.

## Windows 7 / PyStand packaging

[PyStand](https://github.com/skywind3000/PyStand) is a tiny launcher which
deploys a Python app together with an Embedded Python runtime. Build a
standalone QuickPanel directory which runs on Windows 7 (SP1) without any
Python installation:

    $ python3 build_pystand.py            # build dist/QuickPanel/
    $ python3 build_pystand.py --zip      # also pack a zip archive

The script downloads the ready-made environment package published by the
PyStand author (`PyStand-py38-pyqt5-lite`, a 32-bit Python 3.8.10 embedded
runtime + PyQt5/Qt 5.15 lite, so it runs on both 32-bit and 64-bit Windows 7),
copies the QuickPanel sources into it and renames the launcher to
`QuickPanel.exe`. Copy `dist/QuickPanel/` to the Windows 7 machine and
double-click `QuickPanel.exe`.

If Windows reports a missing `vcruntime140.dll`/`msvcp140.dll`, install the
"Microsoft Visual C++ 2015-2022 Redistributable" once.

