Quickpanel is a small popup desktop which supports widgets and desktop icons. When activated, it is shown at the center of screen.

[screenshort](http://hgoldfish.com/static/quickpanel_screenshot.png)

Quickpanel can be run in KDE desktop and windows.

Use it in KDE Desktop:

    $ zypper install python-qt5-devel python-kde5

    $ git clone git@github.com:hgoldfish/quickpanel.git
    $ cd quickpanel
    $ python3 compile_files.py
    $ python3 start_quickpanel.py

After quickpanel started, a system tray icon shown at the right bottom of your desktop. Click it or press Alt + `, shows the quickpanel.

