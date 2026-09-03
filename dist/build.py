#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
QuickPanel 的 PyStand 打包脚本（面向 Windows 7）。

直接使用韦易笑（skywind3000）在 PyStand 项目发布好的现成环境包：

    PyStand-py38-pyqt5-lite.7z
    https://github.com/skywind3000/PyStand/releases/download/1.1.4/PyStand-py38-pyqt5-lite.7z

该包内含：PyStand 启动器 + Python 3.8.10 Embedded（最后支持 Win7 的
Python）+ PyQt5/Qt 5.15 精简运行环境。压缩 15MB、解压 48MB。整套是
32 位（Win32），32 位与 64 位的 Windows 7 都能直接运行，无需区分架构，
也不用另外准备 Python 或 PyQt5。

用法（脚本与 upload.py 同放在 dist/ 并已纳入版本库）：
    cd dist
    python3 build.py                       # 制作 QuickPanel/
    python3 build.py --zip                 # 顺带压成 QuickPanel-win7.zip
    python3 build.py --keep                # 不清除旧产物，直接覆盖组装
    python3 build.py --cache DIR           # 自定义下载缓存目录
    python3 dist/build.py                  # 也可在仓库根直接调用

下载的 7z 环境包缓存到 <out>/cache/（默认 dist/cache/）。构建只重建
QuickPanel/ 产物目录，从不删除缓存；缓存校验通过后再次构建直接复用，
无需重新下载。dist/cache/、dist/QuickPanel/、dist/*.zip 已写入
.gitignore / .hgignore（缓存保留在本地但不入库）。

产物目录（默认输出到本脚本所在目录，即 dist/）：

    QuickPanel/
    ├── QuickPanel.exe        PyStand 启动器（由 PyStand.exe 改名而来）
    ├── QuickPanel.int        入口：import start_quickpanel 并运行 main()
    ├── runtime/              Python 3.8.10 Embedded（来自官方环境包）
    ├── site-packages/        PyQt5 精简版（来自官方环境包）
    ├── start_quickpanel.py / quickpanel_rc.py / tetrix.py / background.png
    ├── besteam/              QuickPanel 依赖源码
    ├── license.txt           程序许可证
    └── QuickPanel-README.txt 给最终用户的中文说明

把整个 QuickPanel 目录拷贝到 Windows 7（SP1）上，双击 QuickPanel.exe
即可运行，无需安装 Python。若系统提示缺少 msvcp140.dll 等运行库，请先
安装一次 "Microsoft Visual C++ 2015-2022 Redistributable (x86)"。
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

# PyStand 现成环境包（32 位 py3.8 + PyQt5 lite，Win7 32/64 通吃）
PYSTAND_LITE_URL = ("https://github.com/skywind3000/PyStand/releases/download/"
                    "1.1.4/PyStand-py38-pyqt5-lite.7z")
PYSTAND_LITE_SHA256 = "a7d3554c2f94c60ab37549e27e13409fed5779a077c36700a48f7e77d61d2c88"
APP_NAME = "QuickPanel"

# QuickPanel.int 模板。PyStand 会把本文件作为 __main__ 执行。
# 说明：PyStand 在 C 层就把 exe 同级的 '.'、'site-packages' 等目录加进了
# sys.path，并设置环境变量 PYSTAND / PYSTAND_HOME / PYSTAND_RUNTIME。
INT_TEMPLATE = '''# -*- coding: utf-8 -*-
# QuickPanel.int - PyStand 入口（由仓库根目录 build_pystand.py 生成）。
# PyStand 会把本文件当作 __main__ 执行；把本文件改名复制为
# _pystand_static.int 可令 exe 随意改名（PyStand 优先加载静态入口）。
import os
import sys


def _home():
    """返回 QuickPanel.exe 所在目录。"""
    home = os.environ.get("PYSTAND_HOME")
    if home:
        return os.path.abspath(home)
    return os.path.dirname(os.path.abspath(__file__))


def _setup_logging(home):
    """双击运行时没有控制台：把日志同时写到 quickpanel.log 方便排错。"""
    import logging
    handlers = []
    try:
        handlers.append(logging.FileHandler(
            os.path.join(home, "quickpanel.log"), encoding="utf-8"))
    except Exception:
        pass
    try:
        handlers.append(logging.StreamHandler())  # 从 cmd 运行时可见
    except Exception:
        pass
    if handlers:
        logging.basicConfig(level=logging.DEBUG, handlers=handlers,
                            format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main():
    home = _home()
    os.chdir(home)
    if home not in sys.path:
        sys.path.insert(0, home)
    _setup_logging(home)
    argv0 = os.environ.get("PYSTAND") or os.path.join(home, "QuickPanel.exe")
    sys.argv = [argv0] + sys.argv[1:]
    import start_quickpanel
    return start_quickpanel.main()


if __name__ == "__main__":
    sys.exit(main())
'''


def log(msg):
    print(msg, flush=True)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def download(url, dest, sha256sum=None, retries=5):
    """下载 url 到 dest；已存在且校验通过则跳过。失败按退避间隔重试。"""
    if os.path.exists(dest):
        if sha256sum is None or sha256_file(dest) == sha256sum:
            log("  [cache] %s" % os.path.basename(dest))
            return
    tmp = dest + ".part"
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            log("  [fetch] %s -> %s" % (url, os.path.basename(dest)))
            req = urllib.request.Request(url, headers={"User-Agent": "quickpanel-build/1.0"})
            with urllib.request.urlopen(req, timeout=300) as resp:
                with open(tmp, "wb") as f:
                    total = int(resp.headers.get("Content-Length") or 0)
                    done = 0
                    while True:
                        chunk = resp.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
                        if total:
                            print("    %d / %d KB" % (done // 1024, total // 1024),
                                  end="\r", flush=True)
            print()
            os.replace(tmp, dest)
            if sha256sum is not None and sha256_file(dest) != sha256sum:
                raise RuntimeError("sha256 校验失败: %s" % os.path.basename(dest))
            return
        except Exception as e:  # noqa: BLE001 - 退避重试直到次数用尽
            last_err = e
            if attempt < retries:
                wait = 3 * attempt  # 3s, 6s, 9s, 12s
                log("  [retry %d/%d] %s（%ds 后重试）" % (attempt, retries, e, wait))
                time.sleep(wait)
            else:
                log("  [retry %d/%d] %s" % (attempt, retries, e))
    raise RuntimeError("下载失败 %s: %s" % (url, last_err))


def _find_7z():
    """返回可用的 7z 可执行文件；找不到返回 None。"""
    for name in ("7z", "7za", "7zr", "7zz", "7za.exe", "7z.exe"):
        p = shutil.which(name)
        if p:
            return p
    # Windows 上 7-Zip 的常见安装路径
    candidates = [
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def extract_7z(archive, target):
    """解压 .7z 到 target。优先外部 7z，其次 py7zr。"""
    log("  [extract] %s -> %s" % (os.path.basename(archive), target))
    os.makedirs(target, exist_ok=True)
    sevenzip = _find_7z()
    if sevenzip:
        cmd = [sevenzip, "x", "-y", "-o" + target, archive]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if proc.returncode != 0:
            sys.exit("7z 解压失败：\n%s" % proc.stdout.decode("utf-8", "replace"))
        return
    try:
        import py7zr
    except ImportError:
        sys.exit("需要 7z 来解压 .7z 环境包。请安装 p7zip，"
                 "或执行: python3 -m pip install --user py7zr")
    with py7zr.SevenZipFile(archive) as z:
        z.extractall(target)


def copy_python_sources(repo, app):
    """把 QuickPanel 运行所需的源码拷贝到包根目录。"""
    for name in ("start_quickpanel.py", "quickpanel_rc.py", "tetrix.py",
                 "background.png", "license.txt"):
        src = os.path.join(repo, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(app, name))
            log("  [copy] %s" % name)
        else:
            log("  [!!] 仓库缺少 %s，产物将不完整" % name)
    # besteam 包（全部 .py，跳过 __pycache__）
    for root, dirs, files in os.walk(os.path.join(repo, "besteam")):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        rel = os.path.relpath(root, os.path.join(repo, "besteam"))
        for fn in files:
            if not fn.endswith(".py"):
                continue
            dst = os.path.join(app, "besteam", rel, fn)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(root, fn), dst)
    log("  [copy] besteam/")


def write_readme(app):
    readme = """QuickPanel（Windows 7 独立版）
==========================

双击 QuickPanel.exe 即可启动。启动后系统托盘出现小丑鱼图标，按 Alt+` 呼出
快捷面板。

目录结构
--------
  QuickPanel.exe     启动器（PyStand，可自由改名，需同时改 QuickPanel.int）
  QuickPanel.int     入口脚本
  runtime/           内嵌 Python 3.8（最后支持 Win7 的 Python）
  site-packages/     PyQt5 精简运行环境（Qt 5.15）
  *.py、besteam/     QuickPanel 源码
  background.png     默认背景
  quickpanel.log     运行日志（出问题时先看这里）
  license.txt        程序许可证（含 PyQt5 的 GPL v3 说明）

系统要求
--------
  * Windows 7 SP1（本包为 32 位环境，32 位与 64 位 Win7 均可运行）
  * 若提示缺少 vcruntime140.dll / msvcp140.dll，请先安装：
    Microsoft Visual C++ 2015-2022 Redistributable (x86)

常见问题
--------
  * 双击没反应：请把整个目录放到纯英文路径（例如 D:\\QuickPanel）再试；
    仍然不行就在 cmd.exe 里运行 QuickPanel.exe 看输出，或查看 quickpanel.log。
  * 想换程序图标：用 Resource Hacker 直接替换 QuickPanel.exe 的资源图标。
  * 重新打包：在开发机上执行 python3 build_pystand.py 即可。
"""
    path = os.path.join(app, "QuickPanel-README.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(readme)
    log("  [write] QuickPanel-README.txt")


def validate(app):
    print("\n===== 产物校验 =====")
    ok = True

    def check(cond, text):
        nonlocal ok
        ok = ok and cond
        print(("  [OK] " if cond else "  [!!] ") + text)

    check(os.path.isfile(os.path.join(app, "QuickPanel.exe")), "QuickPanel.exe 存在")
    check(os.path.isfile(os.path.join(app, "QuickPanel.int")), "QuickPanel.int 存在")
    runtime = os.path.join(app, "runtime")
    check(os.path.isfile(os.path.join(runtime, "python38.dll")),
          "runtime/python38.dll 存在")
    check(os.path.isfile(os.path.join(runtime, "python3.dll")),
          "runtime/python3.dll 存在（PyStand 依赖）")
    check(os.path.isfile(os.path.join(runtime, "vcruntime140.dll")),
          "runtime/vcruntime140.dll 存在")
    site = os.path.join(app, "site-packages")
    check(os.path.isdir(os.path.join(site, "PyQt5")), "site-packages/PyQt5 存在")
    sipfiles = []
    pyqt = os.path.join(site, "PyQt5")
    if os.path.isdir(pyqt):
        sipfiles = [n for n in os.listdir(pyqt) if n.lower().startswith("sip")]
    check(bool(sipfiles), "site-packages/PyQt5/sip 扩展存在（%s）" % ", ".join(sipfiles))
    qtbin = os.path.join(site, "PyQt5", "Qt5", "bin")
    check(os.path.isfile(os.path.join(qtbin, "Qt5Core.dll")), "Qt5Core.dll 位于 %s" % qtbin)
    check(os.path.isfile(os.path.join(site, "PyQt5", "Qt5", "plugins",
                                      "platforms", "qwindows.dll")),
          "qwindows.dll 平台插件存在")
    for f in ("start_quickpanel.py", "quickpanel_rc.py", "tetrix.py",
              "background.png"):
        check(os.path.isfile(os.path.join(app, f)), "%s 存在" % f)
    check(os.path.isdir(os.path.join(app, "besteam")), "besteam/ 存在")
    if not ok:
        print("\n校验未全部通过，请检查上面的 [!!] 项。")
        sys.exit(1)


def total_size(path):
    total = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    return total


def print_tree(app):
    print("\n===== 产物结构（%s）=====" % app)
    for name in sorted(os.listdir(app)):
        p = os.path.join(app, name)
        if os.path.isdir(p):
            print("  %-28s %9.1f MB" % (name + "/", total_size(p) / 1048576.0))
        else:
            print("  %-28s %9.1f KB" % (name, os.path.getsize(p) / 1024.0))


def build(args):
    # 本脚本随仓库放在 dist/ 下：仓库根是它的上一级目录。
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    out = os.path.abspath(args.out) if args.out else here
    cache = os.path.abspath(args.cache) if args.cache else os.path.join(out, "cache")
    app = os.path.join(out, APP_NAME)
    # 下载缓存目录刻意保留：环境包（约 15MB）只下载一次，之后构建复用。
    os.makedirs(cache, exist_ok=True)

    if os.path.isdir(app) and not args.keep:
        # 只重建产物目录；cache/ 内的下载包不动。
        log("清除旧产物: %s" % app)
        shutil.rmtree(app)
    os.makedirs(app, exist_ok=True)

    print("===== 1/4 下载 PyStand 现成环境包 =====")
    pystand_7z = os.path.join(cache, "PyStand-py38-pyqt5-lite.7z")
    download(PYSTAND_LITE_URL, pystand_7z, sha256sum=PYSTAND_LITE_SHA256)

    print("===== 2/4 解压环境包 =====")
    stage = os.path.join(cache, "pystand-lite")
    if os.path.isdir(stage):
        shutil.rmtree(stage)
    extract_7z(pystand_7z, stage)
    srcdir = None
    for name in os.listdir(stage):
        cand = os.path.join(stage, name)
        if os.path.isdir(cand) and os.path.isfile(os.path.join(cand, "PyStand.exe")):
            srcdir = cand
            break
    if srcdir is None:
        sys.exit("环境包解压后未找到含 PyStand.exe 的目录: %s" % stage)

    print("===== 3/4 组装 QuickPanel =====")
    # 拷贝整个环境（runtime/ site-packages/ 等）
    for name in os.listdir(srcdir):
        s = os.path.join(srcdir, name)
        d = os.path.join(app, name)
        if name == "PyStand.exe":
            continue  # 稍后改名拷贝
        if os.path.isdir(s):
            if os.path.isdir(d):
                shutil.rmtree(d)
            shutil.copytree(s, d)
            log("  [copy-dir] %s/" % name)
        else:
            shutil.copy2(s, d)
            log("  [copy] %s" % name)
    # PyStand.exe 改名 QuickPanel.exe（PyStand 加载同名的 .int）
    shutil.copy2(os.path.join(srcdir, "PyStand.exe"), os.path.join(app, "QuickPanel.exe"))
    log("  [exe] PyStand.exe -> QuickPanel.exe")

    # 去掉环境包自带的示例入口，避免误导
    for name in ("PyStand.int", "PyStand.py", "PyStand.pyw", "README.md"):
        p = os.path.join(app, name)
        if os.path.isfile(p):
            os.remove(p)
            log("  [remove] %s" % name)

    int_path = os.path.join(app, "QuickPanel.int")
    with open(int_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(INT_TEMPLATE)
    log("  [write] QuickPanel.int")

    copy_python_sources(repo, app)
    write_readme(app)

    print("===== 4/4 校验 =====")
    validate(app)
    print_tree(app)
    total = total_size(app)
    print("\n完成：%s（共 %.1f MB，解压后）" % (app, total / 1048576.0))
    print("下载包已缓存于 %s，下次构建直接复用，不会重新下载。" % cache)
    print("把整个 QuickPanel 目录拷贝到 Windows 7 上，双击 QuickPanel.exe 即可。")
    if args.zip:
        zip_path = os.path.join(out, "%s-win7.zip" % APP_NAME)
        log("压缩 %s ..." % zip_path)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for root, dirs, files in os.walk(app):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                for f in files:
                    p = os.path.join(root, f)
                    z.write(p, os.path.relpath(p, out))
        print("已生成：%s（%.1f MB）" % (zip_path, os.path.getsize(zip_path) / 1048576.0))


def main():
    parser = argparse.ArgumentParser(
        description="QuickPanel 的 PyStand 打包脚本（面向 Windows 7）。\n"
                    "直接使用韦易笑发布的现成 PyStand-py38-pyqt5-lite 环境包，"
                    "32 位环境同时兼容 32/64 位 Win7。",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=None,
                        help="产物根目录（默认本脚本所在目录，即 dist/）")
    parser.add_argument("--cache", default=None,
                        help="下载缓存目录（默认 <out>/cache）")
    parser.add_argument("--keep", action="store_true",
                        help="不清除旧的 dist/QuickPanel 直接覆盖组装")
    parser.add_argument("--zip", action="store_true", help="顺带生成 zip 压缩包")
    args = parser.parse_args()
    build(args)


if __name__ == "__main__":
    sys.exit(main())
