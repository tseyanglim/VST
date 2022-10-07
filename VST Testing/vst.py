#!/usr/bin/env python
# coding: utf-8

# **NOTE:** this version is *not* backward-compatible with existing scripts: 1) `Script` objects and use syntax have been substantially modified, and 2) newest Vengine no longer has the expiration popup to bypass, so `press` lines are no longer needed and have been removed.

# In[1]:


import os
import subprocess
import regex
import json
import time
import numpy as np
import pandas as pd
from vst_text import *
from keyboard import press
from shutil import copy


# In[5]:


class Script(object):
    """Master object for holding and modifying .cmd script settings, 
    creating .cmd files, and running them through Vensim/Vengine
    """
    def __init__(self, controlfile, name, logfile, 
                 sfxs={}, chglist=[], setvals=[], simtype='o'):
        """Initialise script object from controlfile, modifying 
        simcontrol settings as specified

        Parameters
        ----------
        controlfile : dict or JSON object
            Control file specifying `basename`, `simcontrol` settings, 
            and optionally `runcmd` and `savecmd`; can be modified as 
            needed for each Script instance
        name : str
            Specifies additional string to append to basename for run
        logfile : str of filename/path
            Path to logfile for logging progress & errors
        sfxs : dict of str
            Dict of suffixes to append to filenames in simcontrol; use 
            to distinguish versions of e.g. .mdl, .voc, .vpd etc. files
        chglist : list of str or tuples of (str or list, str)
            Specifies additional changes files to be used in script; see 
            documentation for details of syntax
        setvals : list of tuples of (str, int or float)
            Specifies variable-value pairs to change using Vensim's 
            SETVAL script command; see documentation for details
        simtype : 'o', 'r', 's', or 'sf', optional (default 'o')
            Type of sim to run, determines default runcmd and savecmd to 
            use if not otherwise specified
        """
        write_log(f"Initialising {self}", logfile)
        self.basename = controlfile['basename']
        
        # Set core simcontrol attributes from controlfile
        for k, v in controlfile['simcontrol'].items():
            self.__setattr__(k, v if isinstance(v, str) else v.copy())

        # Modify mdl, voc, etc. with suffixes specified as dict
        for s, sfx in sfxs.items():
            if hasattr(self, s):  # Unneeded sfxs quietly ignored
                self.__setattr__(s, getattr(self, s)[:-4] + sfx + getattr(self, s)[-4:])
        self.runname = self.basename + name
        
        # Set default run & save cmds by simtype
        defaults = {  # Dictionary of default runcmd / savecmd combos by simtype
            'o': ['RUN_OPTIMIZE|o', f'VDF2TAB|!|!|{self.savelist}|'],  # Optimization
            'r': ['RUN|o', f'VDF2TAB|!|!|{self.savelist}|'],  # Normal run
            's': ['RUN_SENSITIVITY|o', 'SENS2FILE|!|!|%#T'],  # Sensitivity run
            'sf': ['RUN_SENSITIVITY|o', 'SENS2FILE|!|!|#T[']  # Sens with full save (V. LARGE)
            } 
        self.runcmd = defaults[simtype][0]
        self.savecmd = defaults[simtype][1]
        
        # Overwrite run & save cmds if specified
        for cmd in ['runcmd', 'savecmd']:
            if controlfile[cmd]:  # Not triggered by empty string
                write_log(f'Overwriting default {cmd} with {controlfile[cmd]}!', logfile)
                self.__setattr__(cmd, controlfile[cmd])
        
        # Update changes with `chglist`    
        flat = [i for s in 
                [[c] if isinstance(c, str)  # List-wrap single items to flatten properly
                 else [f"{self.basename}{name}{c[1]}.out"  # Expand lists in paired tuples
                       for name in c[0]] if isinstance(c[0], list) 
                 else [f"{self.basename}{c[0]}{c[1]}.out"]  # Or combine paired string tuples
                 for c in chglist] for i in s]  # Nested list flattening syntax
        self.changes.extend(flat)
        self.setvals = setvals


    def write_script(self):
        """Write actual .cmd file based on Script attributes"""
        
        cmdtext = ["SPECIAL>NOINTERACTION\n", f"SPECIAL>LOADMODEL|{self.model}\n"]
        
        for s in ['payoff', 'sensitivity', 'optparm', 'savelist', 'senssavelist']:
            if hasattr(self, s):
                cmdtext.append(f"SIMULATE>{s}|{getattr(self, s)}\n")
        
        if hasattr(self, 'data'):
            cmdtext.append(f"SIMULATE>DATA|\"{','.join(self.data)}\"\n")

        if hasattr(self, 'changes'):
            if len(self.changes) > 0:
                cmdtext.append(f"SIMULATE>READCIN|{self.changes[0]}\n")
                for file in self.changes[1:]:
                    cmdtext.append(f"SIMULATE>ADDCIN|{file}\n")

        if hasattr(self, 'setvals'):
            for var, val in self.setvals:
                cmdtext.append(f"SIMULATE>SETVAL|{var}={val}\n")
        
        cmdtext.extend([
            "\n", f"SIMULATE>RUNNAME|{self.runname}\n", 
            "SIMULATE>REPORT|1\n", f"MENU>{self.runcmd}\n", 
            f"MENU>{self.savecmd}|\n", 
            "SPECIAL>CLEARRUNS\n", "MENU>EXIT\n"
            ])
        
        # Assign cmdtext list to Script object and write actual cmd file
        with open(f"{self.runname}.cmd", 'w') as scriptfile:
            scriptfile.writelines(cmdtext)
        self.__setattr__('cmdtext', cmdtext)
        self.__setattr__('cmdfile', f"./{self.runname}.cmd")
                

    def copy_model_files(self, dirname):
        """Create subdirectory and copy relevant model files to it,
        then change working directory to subdirectory"""
        # Create and change to subdirectory
        os.makedirs(dirname, exist_ok=True)
        os.chdir(f"./{dirname}")

        # Copy needed files, based on updated Script attributes
        for s in ['model', 'payoff', 'optparm', 'sensitivity', 
                  'savelist', 'senssavelist', 'cmdfile']:
            if getattr(self, s, False):  # Default to false if attr does not exist
                copy(f"../{getattr(self, s)}", "./")
        for slist in ['data', 'changes']:
            for file in getattr(self, slist):
                copy(f"../{file}", "./")


    def compile_script(self, vensimpath, logfile, vengine=True, subdir=None, **kwargs):
        """Write script from attributes to .cmd file and run in Vensim
        
        Parameters
        ----------
        logfile : str of filename/path
            Path to logfile for logging progress & errors
        vengine : Boolean
            If True, run Vengine, otherwise run Vensim
        subdir : str, optional
            If specified, will create subdirectory in which to run model
        kwargs : additional arguments to pass to run function 
            outext : str
                File extension (and optionally suffix) added to runname 
                to identify file to monitor for successful (Vensim) or 
                ongoing (Vengine) run; usually `.log` for Vengine
            timelimit : int or float
                Timelimit for Vengine run monitoring; defaults to global 
                variable `timelimit`
            check_funcs : list of check functions
                Check functions to run to verify bug-free Vengine result
            maxattempts : int
                Maximum times to try running Vensim before failure

        Returns
        -------
        float
            Payoff value of the script run, if applicable, else 0
        """
        if subdir:
            self.copy_model_files(subdir)
            self.subdir = os.getcwd()
            
        self.write_script()  # Generate the actual .cmd file
        
        if vengine:
            payoff = run_vengine_script(self.runname, vensimpath, logfile, **kwargs)
        else:
            payoff = run_vensim_script(self.runname, vensimpath, logfile, **kwargs)
        ### TODO: Add automatic recognition of different `outext` extensions to pass to 
        ### run_vensim_script based on `self.savecmd`
        
        if subdir:
            if os.path.exists(f"./{self.runname}.out"):  # Copy outfile to parent directory
                copy(f"./{self.runname}.out", "../")
            os.chdir('..')  # Return to parent directory from subdirectory
    
        return payoff

    
    def downsample(self, samplefrac, remove=True, vsc=True):
        """Downsamples MCMC _sample tab file by `samplefrac`, creating 
        sample of accepted points; optionally deletes MCMC _sample and 
        _points files to free up disk space; optionally creates .vsc for 
        file method sensitivity analysis using subsample
        """
        path = getattr(self, 'subdir', '.')
        
        rawdf = pd.read_csv(f"{path}/{self.runname}_MCMC_sample.tab", sep='\t')
        newdf = rawdf.sample(frac=samplefrac)  # Downsample randomly by samplefrac
        newdf.dropna(axis=1, how='all', inplace=True)  # Remove 'Unknown' column from sample
        newdf.to_csv(f"{self.runname}_MCMC_sample_frac.tab", sep='\t', index=False)
        
        if remove:  # Optionally remove main MCMC outputs to free up disk space
            os.remove(f"{path}/{self.runname}_MCMC_sample.tab")
            os.remove(f"{path}/{self.runname}_MCMC_points.tab")
            
        if vsc:  # Optionally create file input method .vsc file, reading from sample
            with open(f"{self.runname}.vsc", 'w') as f:
                f.write(f",F,,{os.getcwd()}/{self.runname}_MCMC_sample_frac.tab,0")


########################################################################                

### TODO: remove `press` calls

def run_vengine_script(scriptname, vensimpath, logfile, 
                       timelimit=None, outext='.log', check_funcs=[]):
    """Call Vengine with command script using subprocess; monitor output 
    file for changes to see if Vengine has stalled out, and restart if 
    it does, or otherwise bugs out; return payoff if applicable"""

    write_log(f"Initialising {scriptname}!", logfile)

    # Set default values for `timelimit` and `check_funcs`
    if not timelimit:  # `timelimit` should be globally specified
        timelimit = getattr(run_vengine_script, 'timelimit', timelimit)
    if not check_funcs:  # Sets two default check_funcs, can specify more in function call
        check_funcs = getattr(run_vengine_script, 'check_funcs', [check_restarts, check_zeroes])
    
    while True:
        proc = subprocess.Popen(f"{vensimpath} \"./{scriptname}.cmd\"")
        time.sleep(2)
        press('enter')  # Necessary to bypass the popup message in Vengine
        while True:
            try:  # See if run completes within timelimit
                proc.wait(timeout=timelimit)
                break
            except subprocess.TimeoutExpired:  # If timelimit reached, check run status
                try:  # If Vengine gives error popup on exit, attempt to bypass it
                    print("Attempting bypass...")
                    press('enter')
                    proc.wait(3)  # Process should complete if bypass successful
                    break
                except subprocess.TimeoutExpired:
                    try:  # If bypass unsuccessful, check if run still going
                        write_log(f"Checking for {scriptname}{outext}...", logfile)
                        timelag = time.time() - os.path.getmtime(f"./{scriptname}{outext}")
                        if timelag < (timelimit):  # Compare time since last output with timelimit
                            write_log(f"At {time.ctime()}, {round(timelag,3)}s since last output, "
                                      "continuing...", logfile)
                            continue
                        else:  # If run seems to have stalled out, kill and restart
                            proc.kill()
                            write_log(f"At {time.ctime()}, {round(timelag,3)}s since last output. "
                                      "Calibration timed out!", logfile)
                            break
                    except FileNotFoundError:  # If check fails, kill and restart
                        proc.kill()
                        write_log("Calibration timed out!", logfile)
                        break
        # Check if process successfully completed or bugged out / was killed
        # if proc.returncode != 1:  # Note that Vengine returns 1 on MENU>EXIT, not 0!
        ### TODO: Update this when Vengine return codes are fixed
        ### Vengine 7.2 returns 1 on MENU>EXIT, but Vengine 9.3 sometimes returns 0 
        ### and sometimes returns 3221225477 despite successful completion
        if not (proc.returncode == 0 or proc.returncode == 3221225477):
            write_log(f"Return code is {proc.returncode}", logfile)
            write_log("Vensim! Trying again...", logfile)
            continue
        else: write_log(f"Return code is {proc.returncode}", logfile)
        try:  # If process completed successfully, run final check for errors in output
            if all([func(scriptname, logfile) for func in check_funcs]):
                break  # NOTE: this is the only successful completion outcome!
        except FileNotFoundError:  # Catch output error and restart run
            write_log("Outfile not found! That's it, I'm dead.", logfile)
            pass
    
    time.sleep(2)

    if os.path.exists(f"./{scriptname}.out"):
        payoffvalue = read_payoff(f"{scriptname}.out", logfile)
        write_log(f"Payoff for {scriptname} is {payoffvalue}, calibration complete!", logfile)
        return payoffvalue # For optimisation runs, return payoff
    return 0 # Set default payoff value for simtypes that don't generate one


def run_vensim_script(scriptname, vensimpath, logfile, maxattempts=10, outext='.tab'):
    """Call Vensim (not Vengine) with command script using subprocess, 
    for instances when Vengine unnecessary or unavailable; try up to 
    `maxattempts` times; return payoff if applicable
    """
    attempts = 0
    while attempts < maxattempts:
        attempts += 1  # Track & update number of attempts to prevent infinite loop
        if os.path.exists(f"./{scriptname}{outext}"):
            os.remove(f"./{scriptname}{outext}")  # Delete old output file if needed
        try:
            subprocess.run(f"{vensimpath} \"./{scriptname}.cmd\"", check=True)
            pass
        except subprocess.CalledProcessError:
            print("Vensim! Trying again...")
            continue
        if os.path.exists(f"./{scriptname}{outext}"):  # Check for output file
            break
        else:
            write_log(f"Help! {scriptname} is being repressed!", logfile)
            continue
    
    if os.path.exists(f"./{scriptname}.out"):
        payoffvalue = read_payoff(f"{scriptname}.out", logfile)
        write_log(f"Payoff for {scriptname} is {payoffvalue}, calibration complete!", logfile)
        return payoffvalue  # For optimisation runs, return payoff
    return 0  # Set default payoff value for simtypes that don't generate one


# ## `Script` objects
# 
# `vst` is built around the `Script` class. Each `Script` instance corresponds to a single Vensim command script (`.cmd` file) - its various settings, the `.cmd` itself, and its output (**TODO:** Associate output VDF and tabfile with `Script` object). `Script` objects thus serve as convenient containers and interfaces for command scripts, while largely obviating the need to know or directly utilise Vensim command script syntax.
# 
# Basic `Script` use syntax is something like:
# ```
# x = Script(controlfile, name, logfile, sfxs=suffixes, chglist=changes)
# x.compile_script(logfile, **kwargs)
# ```
# This will create an instance `x` of a `Script` object with the specified settings (detailed below), compile it into a `.cmd` file, and execute that `.cmd` file to produce a Vensim run and output.
# 
# This basic syntax can be wrapped in more complex workflows, such as iteratively estimating different levels of a hierarchical model, creating a pipeline for estimating and then running sensitivity analysis under different scenarios, and so on, with necessary modifications to the `Script` instance created each time. This approach is especially powerful with procedurally generated or standardised modifications.
# 
# ### `Script` initialisation arguments
# 
# Each `Script` instance is initialised with several arguments:
# 
# #### controlfile
# The `controlfile` is a `dict` or `JSON` object with basic settings such as:
# - the `basename` to use for runs
# - `simcontrol`, a sub-dictionary closely corresponding to the fields in Vensim's 'Simulation Control' dialogue box
# - optionally, `runcmd` and `savecmd`, command-script syntax commands for specific run and save settings
# 
# `controlfile` fields are intended to be fairly stable in a given analysis - while it's conceivable they may need to be changed in the analytical pipeline for a given model (particularly `runcmd` and `savecmd`)(**TODO:** consider whether to move these two fields to `__init__` arguments), most analysis of a given model should be able to use a fixed `controlfile`, with modifications applied as needed through the other `Script` arguments below.
# 
# #### name
# A `str` extension to append to the `basename` for a given instance / run. Ideally this would be standardised and/or procedurally generated within an analytical pipeline; `chglist` syntax (see below) allows parsing of various procedurally generated name strings for easy iteration.
# 
# ##### Recommended naming convention:
# `basename` `subset` `iteration/type` `base cins` `policy/scenario cins`
# 1. `basename` - shared by all runs in a given analysis
# 2. `subset` - specific submodel or analysis (e.g. main, holdout, syndata)
# 3. `iteration/type` - iteration no. or type of run (e.g. MC, sens, scen)
# 4. `base cins` - CIN files (shared assumption sets)
# 5. `policy/scenario cins` - CIN files (individual policies/scenarios)
# 
# #### logfile
# File used for shared progress & error logging with `write_log` (**TODO:** switch to using `logging` module)
# 
# #### sfxs
# A `dict` of `simcontrol` entries, such as payoff `vpd` or sensitivity control `vsc`, and corresponding string suffixes to modify them with. For instance, if the `simcontrol` specified payoff file is `foo.vpd`, specifying `payoff: '_b'` would modify the payoff file for this `Script` instance to `foo_b.vpd`. Useful for specifying different model or simulation control file versions, denoted by automatically assigned suffixes, for different `Script` instances. Any suffixes specified for missing `simcontrol` entries will be quietly ignored.
# 
# #### chglist
# A `list` of changes files to add to the `Script` beyond those specified in `simcontrol`. Entries are appended to `changes` in the order that they appear in `chglist`. Entries in `chglist` can be:
# - Single strings, e.g. ``'Scenario.cin'` -> these are added as-is, and should include file extensions; useful for adding `.cin` files for specific scenarios, policy analysis, etc.
# - Tuples of two elements, either:
#     - Two strings, e.g. `('Main', 'MC')` -> these are concatenated with the `basename` and `.out` extension, e.g. `'{basename}MainMC.out'`; useful for adding results of a previous optimization or iteration
#     - A list and string, e.g. `(['Albert', 'Bob', 'Charlie'], 'Final')` -> these are likewise concatenated with `basename` and `.out` extension, for each element in the list, e.g. `['{basename}AlbertFinal.out', '{basename}BobFinal.out', '{basename}CharlieFinal.out']`; useful for easily combining multiple outputs from previous optimizations, as is common with a hierarchical estimation approach
# 
# #### setvals
# A `list` of tuples containing paired variable names and values, to be included in a `Script` using Vensim's SETVAL command. All SETVAL commands are implemented together for the run. This is particularly useful for reducing file proliferation, especially for e.g. parametric sensitivity analysis; note however that the only obvious record in any output files of changes made with SETVAL will be in the `.cmd` file, which may confound easy replication.
# 
# #### simtype: `o`, `r`, `s`, `sf`; default `o`
# Type of simulation to run; determines default `runcmd` and `savecmd` to use if not otherwise specified:
# - `o`: optimization
# - `r`: simple run
# - `s`: sensitivity with percentile output
# - `sf`: sensitivity with full output saving
# (**TODO:** figure out Tidy format sensitivity output default `savecmd`)

# In[ ]:


000000000000000000000000000000000000000000000000000000000000000000000000
000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000

