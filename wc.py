#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import io

join = os.path.join
basename = os.path.basename

def countLine(filename):
    lines = 0
    blankLines = 0
    commentedLines = 0
    with io.open(filename, "r", encoding = "utf-8") as f:
        while True:
            line = f.readline()
            if line is None or line == "":
                break
            lines += 1
            if line == "\n":
                blankLines += 1
            elif line.lstrip().startswith(("//", "#")):
                commentedLines += 1
    return lines, blankLines, commentedLines

def findCppFiles(dirname):
    cppFiles = []
    for filename in os.listdir(dirname):
        if os.path.isdir(filename):
            d = join(dirname, filename)
            cppFiles.extend(findCppFiles(d))
        if filename.lower().startswith("ui_"):
            continue
        if filename.lower().endswith((".hpp", ".cpp", ".c", ".h")):
            cppFiles.append(join(dirname, filename))
    return cppFiles

def findPyFiles(dirname):
    pyFiles = []
    for filename in os.listdir(dirname):
        if os.path.isdir(join(dirname, filename)):
            d = join(dirname, filename)
            pyFiles.extend(findPyFiles(d))
        if filename.startswith("Ui_"):
            continue
        if filename.endswith("_rc.py"):
            continue
        if filename.lower().endswith((".py", ".pyw")):
            pyFiles.append(join(dirname, filename))
    return pyFiles

if __name__ == "__main__":
    print("filename".ljust(25) + "bytes".ljust(12) + "total lines".ljust(12) + \
        "blank lines".ljust(12) + "commented lines".ljust(12))
    print("=" * 79)
    totalBytes = 0
    totalLines = 0
    totalBlankLines = 0
    totalCommentedLines = 0
    for filename in findPyFiles("."):
        bytes = os.path.getsize(filename)
        lines, blankLines, commentedLines = countLine(filename)
        totalBytes += bytes
        totalLines += lines
        totalBlankLines += blankLines
        totalCommentedLines += commentedLines
        print(basename(filename).ljust(25) + str(bytes).ljust(12) + str(lines).ljust(12) + \
            str(blankLines).ljust(12) + str(commentedLines).ljust(12))
    print("=" * 79)
    print(" " * 25 + str(totalBytes).ljust(12) + str(totalLines).ljust(12) + \
        str(totalBlankLines).ljust(12) + str(totalCommentedLines).ljust(12))
