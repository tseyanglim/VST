#!/usr/bin/env python
# coding: utf-8

# ## Text Replacer
# 
# Simple standalone `py` / `ipynb` widget for replacing text in a list of files, based on a dictionary of 'old' text to be replaced and 'new' text to replace with. Useful for changing multiple variable names simultaneously across a suite of text-readable Vensim files (e.g. `mdl`, `cin`, `voc`, `vgd`, `vpd`, `lst`, etc.) so that nothing breaks, as is likely with manual renaming.
# 
# Requires two inputs:
# 1. `filelist` - a simple text-format list of files or filepaths (relative or absolute), one file name on each line
# 2. `varnamedict` - a JSON-format dictionary matching keys (text to be replaced) to values (text to replace with)
# 
# **WARNING:** This will update files in-place, silently overwriting the old files!
# 
# Please contact [Tse Yang Lim](mailto:tylim@mit.edu) with any questions or suggestions.
# 
# #### TODO:
# - Once necessary functions are incorporated into `VST` module, import from `VST` instead

# In[ ]:


import regex
import json


def rep_strings(string, subs):
    """Core text replacement function; searches text and replaces old 
    strings with corresponding new ones; should correctly handle strings 
    that are substrings of longer strings, prioritising longest possible 
    matches first    
    
    Parameters
    ----------
    string : str
        Text within which to replace parts based on `subs`
    subs : dict of str
        Dict of old strings to replace with matching new strings
        
    Returns
    -------
    str
        Text with replacements made
    """
    substrings = sorted(subs, key=len, reverse=True)  # Arrange replacement keys by length
    regexp = regex.compile('|'.join(map(regex.escape, substrings)))
    return regexp.sub(lambda match: subs[match.group(0)], string)


def rep_text(filelist, varnamedict):
    """Replace text using `rep_strings` in multiple files; `filelist` is 
    list of file names/paths w/ extensions, can be absolute or relative 
    to working directory; `varnamedict` is json-format dictionary of str 
    keys and replacements; NOTE overwrites `filelist` files inplace
    """
    
    with open(filelist, 'r') as fl:
        files = fl.read().splitlines()
    subs = json.load(open(varnamedict, 'r'))  # Read replacements dict

    for file in list(filter(None, files)):  # Ignores empty lines in filelist
        print(f"Modifying {file}...")
        with open(file, 'r') as f:
            old = f.read()

        new = rep_strings(old, subs)
        with open(file, 'w') as f:
            f.write(new)


# In[ ]:


# For widget version, get user input for filelist and varnamedict
filelist = input("Enter FileList (with extension):") 
varnamedict = input("Enter VarNameDict (with extension):")

rep_text(filelist, varnamedict)
print("Job done!")


# In[ ]:


000000000000000000000000000000000000000000000000000000000000000000000000
000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000

