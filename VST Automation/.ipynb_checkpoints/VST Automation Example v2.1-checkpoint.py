#!/usr/bin/env python
# coding: utf-8

# ## Vensim Script automation example
# 
# This example demonstrates how to use Python to interface with Vensim through use of Vensim command scripts. The core of the Python code is the custom `Script` object, which holds details of the .cmd file to be compiled and run as attributes, and contains the necessary methods to actually assemble and run the .cmd. The main function involved, `compile_script`, can be integrated into more complex workflows, e.g. iteratively calibrating partial models. This example will run a single optimization run, reporting the payoff and exporting the results to .tab, and then run a single simple simulation based on  the output of the previous optimization.
# 
# By default, `Script` objects do Vensim optimization runs. Sub-classes of `Script` can be used to modify the .cmd file and the run type; the `RunScript` shown here is one example, used to conduct a simple simulation run rather than an optimization. The controls and settings for the optimization are largely set through a separate .txt ControlFile.
# 
# ### To test this example
# 1. Place this .py / .ipynb script and all necessary files in the same directory
# 2. Modify the ControlFile `Control.txt` to point to the correct path for your Vensim or Vengine .exe (under 'venginepath' or 'vensimpath'; **leave 'venginepath' blank** if you don't have Vengine installed)
# 3. Run either the .ipynb or the .py file, and enter the ControlFile name when prompted

# In[ ]:


import os
import json
import time
import regex
import subprocess
from shutil import copy

class Script(object):
    """Master object for holding and modifying .cmd script settings, 
    creating .cmd files, and running them through Vensim/Vengine"""
    def __init__(self, controlfile):
        print("Initialising", self)
        for k, v in controlfile['simsettings'].items():
            self.__setattr__(k, v if isinstance(v, str) else v.copy())
        self.setvals = []
        self.runcmd = "SIMULATE>REPORT|1\nMENU>RUN_OPTIMIZE|o\n"
        self.savecmd = f"MENU>VDF2TAB|!|!|{self.savelist}|\n"
        self.basename = controlfile['baserunname']
        self.cmdtext = []
        
    def copy_model_files(self, dirname):
        """Create subdirectory and copy relevant model files to it,
        then change working directory to subdirectory"""
        os.makedirs(dirname, exist_ok=True)
        os.chdir(f"./{dirname}")

        # Copy needed files from the working directory into the sub-directory
        for s in ['model', 'payoff', 'optparm', 'sensitivity', 'savelist', 'senssavelist']:
            if getattr(self, s):
                copy(f"../{getattr(self, s)}", "./")
        for slist in ['data', 'changes']:
            for file in getattr(self, slist):
                copy(f"../{file}", "./")
        
    def add_suffixes(self, settingsfxs):
        """Modify mdl, voc, etc. with suffixes specified as dict"""
        for s, sfx in settingsfxs.items():
            if hasattr(self, s):
                self.__setattr__(s, getattr(self, s)[:-4] + sfx + getattr(self, s)[-4:])
   
    def update_changes(self, chglist, setvals=[]):
        """Combines and flattens list of paired names & suffixes for 
        changes, and appends to changes setting; also updates setvals"""
        flat = [i for s in 
                [[f"{self.basename}_{n}_{sfx}.out" for n in name] if isinstance(name, list) 
                 else [f"{self.basename}_{name}_{sfx}.out"] for name, sfx in chglist] for i in s]
        self.changes.extend(flat)
        self.setvals = setvals
        
    def write_script(self, scriptname):
        """Write actual .cmd file based on controlfile attributes"""
        self.cmdtext.extend(["SPECIAL>NOINTERACTION\n", 
                             f"SPECIAL>LOADMODEL|{self.model}\n"])
        
        for s in ['payoff', 'sensitivity', 'optparm', 'savelist', 'senssavelist']:
            if hasattr(self, s):
                self.cmdtext.append(f"SIMULATE>{s}|{getattr(self, s)}\n")
        
        if hasattr(self, 'data'):
            datatext = ','.join(self.data)
            self.cmdtext.append(f"SIMULATE>DATA|\"{','.join(self.data)}\"\n")

        if hasattr(self, 'changes'):
            if self.changes:
                self.cmdtext.append(f"SIMULATE>READCIN|{self.changes[0]}\n")
                for file in self.changes[1:]:
                    self.cmdtext.append(f"SIMULATE>ADDCIN|{file}\n")
        
        self.cmdtext.extend(["\n", f"SIMULATE>RUNNAME|{scriptname}\n"])
        
        if hasattr(self, 'setvals'):
            for var, val in self.setvals:
                self.cmdtext.append(f"SIMULATE>SETVAL|{var}={val}\n")
        
        self.cmdtext.extend([self.runcmd, self.savecmd, 
                             "SPECIAL>CLEARRUNS\n", "MENU>EXIT\n"])
        
        with open(f"{scriptname}.cmd", 'w') as scriptfile:
            scriptfile.writelines(self.cmdtext)

    def run_script(self, scriptname, controlfile, subdir, logfile):
        """Run the compiled .cmd file, calling Vengine by default"""
        if venginepath:
            return run_vengine_script(scriptname, controlfile['venginepath'], 
                                      controlfile['timelimit'], '.log', check_opt, logfile)
        else:
            return run_vensim_script(scriptname, controlfile['vensimpath'], 
                                     controlfile['timelimit'], logfile)    
        

class RunScript(Script):
    """Script subclass for simple single runs (not optimzations)"""
    def __init__(self, controlfile):
        super().__init__(controlfile)
        self.runcmd = "MENU>RUN|o\n" # Change .cmd run command

    def run_script(self, scriptname, controlfile, subdir, logfile):
        """Run the compiled .cmd file with Vensim instead of Vengine"""
        return run_vensim_script(scriptname, controlfile['vensimpath'], 10, logfile)

    
def compile_script(controlfile, scriptclass, name, namesfx, settingsfxs, 
                   logfile, chglist=[], setvals=[], subdir=None):
    """Master function for assembling & running .cmd script
    
    Parameters
    ----------
    controlfile : JSON object
        Master control file specifying sim settings, runname, etc.
    scriptclass : Script object
        Type of script object to instantiate, depending on run type
    name : str
    namesfx : str
        Along with `name`, specifies name added to baserunname for run
    settingsfxs : dict of str
        Dict of suffixes to append to filenames in simsettings; use to 
        distinguish versions of e.g. .mdl, .voc, .vpd etc. files
    logfile : str of filename/path
    chglist : list of tuples of (str or list, str)
        Specifies changes files to be used in script; specify as tuples 
        corresponding to `name`, `namesfx` of previous run .out to use; 
        tuples can also take a list of `names` as first element, taking 
        each with the same second element; if used with ScenScript run, 
        `chglist` can also take one non-tuple str as its last element, 
        which will be added directly (e.g. .cin files for scenarios)
    setvals : list of tuples of (str, int or float, <str>)
        Specifies variables and values to change for a given run using 
        Vensim's SETVAL script command; by default all SETVAL commands 
        will be implemented together for main run, but if `scriptclass` 
        is MultiScript, each SETVAL command will be implemented and run 
        separately in sequence; if used with MultiScript, each tuple in 
        `setvals` will require a third str element specifying the suffix 
        with which to save the run
    subdir : str, optional
        Name of subdirectory to create/use for run, if applicable
    
    Returns
    -------
    float
        Payoff value of the script run, if applicable, else 0
    """
    mainscript = scriptclass(controlfile)
    mainscript.add_suffixes(settingsfxs)
    mainscript.update_changes(chglist, setvals)
    scriptname = f"{mainscript.basename}_{name}_{namesfx}"    
    mainscript.write_script(scriptname)
    return mainscript.run_script(scriptname, controlfile, subdir, logfile)


def write_log(string, logfile):
    """Writes printed script output to a logfile"""
    with open(logfile,'a') as f:
        f.write(string + "\n")
    print(string)
    

def read_payoff(outfile, logfile):
    """Identifies payoff value from .OUT or .REP file"""
    # Identify line to read payoff from
    line = 1
    if outfile.endswith('.rep'):
        line = 0
    elif outfile.endswith('.out'): pass
    else:
        write_log(f"Warning: attempting to read payoff from {outfile}", logfile)
    
    with open(outfile, 'r') as f:
        payoffline = f.readlines()[line]
    payoffvalue = [float(s) for s in 
                   regex.findall(r'-?(?:0|[1-9]\d*)(?:\.\d*)?(?:[eE][+\-]?\d+)?', payoffline)][0]
    return payoffvalue


# ### Script running functions
# 
# `compile_script` calls Vensim or Vengine to run a .cmd file, defaulting to Vengine if available. (*For any substantial analysis, always use Vengine if available!*)
# 
# Fundamentally, doing this is extremely simple, and a single `subprocess.Popen` or `subprocess.run` call should suffice. But **Vensim is buggy, and Vengine more so**. The `run_vengine_script` and `run_vensim_script` functions wrap the core `subprocess` call in various forms of exception handling and other checks to keep things running smoothly. These checks are crucial for successful hands-off automation. Otherwise you risk coming back to your analysis after it's been running all night to find it's been stuck on a Vensim loading screen for 12 hours.
# 
# Because `run_vengine_script` has seen more use, its exception handling is better developed. (Also, Vengine has more bugs.) If needed, you could modify `run_vensim_script` using similar checks, e.g. incorporating a time limit. Get creative. Learn from painful experience.
# 
# The `check_func` argument to `run_vengine_script` allows use of a helper function to catch additional bugs in Vengine output (e.g. nonexistent output, zeroing bug, inconsistent payoffs...); the helper function should return `True` only if no bugs of concern have occurred. One example helper function, `check_opt`, is included here for reference.

# In[ ]:


def run_vengine_script(scriptname, venginepath, timelimit, checkfile, check_func, logfile):
    """Call Vengine with command script using subprocess; monitor output 
    file for changes to see if Vengine has stalled out, and restart if 
    it does, or otherwise bugs out; use helper function `check_func` to 
    identify errors in output; return payoff if applicable"""

    write_log(f"Initialising {scriptname}!", logfile)

    while True:
        proc = subprocess.Popen(f"{venginepath} \"./{scriptname}.cmd\"")
        time.sleep(2)
        # press('enter') # Necessary to bypass the popup message in Vengine
        while True:
            try: # See if run completes within timelimit
                proc.wait(timeout=timelimit)
                break
            except subprocess.TimeoutExpired: # If timelimit reached, check run status
                try: # If Vengine gives error popup on exit, attempt to bypass it
                    print("Attempting bypass...")
                    # press('enter')
                    proc.wait(3) # Process should complete if bypass successful
                    break
                except subprocess.TimeoutExpired:
                    try: # If bypass unsuccessful, check if run still going
                        write_log(f"Checking for {scriptname}{checkfile}...", logfile)
                        timelag = time.time() - os.path.getmtime(f"./{scriptname}{checkfile}")                        
                        if timelag < (timelimit): # Compare time since last output with timelimit
                            write_log(f"At {time.ctime()}, {round(timelag,3)}s since last output, "
                                      "continuing...", logfile)
                            continue
                        else: # If run seems to have stalled out, kill and restart
                            proc.kill()
                            write_log(f"At {time.ctime()}, {round(timelag,3)}s since last output. "
                                      "Calibration timed out!", logfile)
                            break
                    except FileNotFoundError: # If check fails, kill and restart
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
        try: # If process completed successfully, run final check for errors in output
            if check_func(scriptname, logfile):
                break # NOTE: this is the only successful completion outcome!
        except FileNotFoundError: # Catch output error and restart run
            write_log("Outfile not found! That's it, I'm dead.", logfile)
            pass
    
    time.sleep(2)

    if os.path.exists(f"./{scriptname}.out"):
        payoffvalue = read_payoff(f"{scriptname}.out", logfile)
        write_log(f"Payoff for {scriptname} is {payoffvalue}, calibration complete!", logfile)
        return payoffvalue # For optimisation runs, return payoff
    return 0 # Set default payoff value for simtypes that don't generate one


def run_vensim_script(scriptname, vensimpath, maxattempts, logfile):
    """Call Vensim (not Vengine) with command script using subprocess, 
    for instances when Vengine unnecessary or unavailable; try up to 
    `maxattempts` times; return payoff if applicable"""
    attempts = 0
    while attempts < maxattempts:
        attempts += 1 # Track & update number of attempts to prevent infinite loop
        if os.path.exists(f"./{scriptname}.tab"):
            os.remove(f"./{scriptname}.tab") # Delete old output tabfile if needed
        try:
            subprocess.run(f"{vensimpath} \"./{scriptname}.cmd\"", check=True)
            pass
        except subprocess.CalledProcessError:
            print("Vensim! Trying again...")
            continue
        if os.path.exists(f"./{scriptname}.tab"): # Check for output tabfile
            break
        else:
            write_log(f"Help! {scriptname} is being repressed!", logfile)
            continue
    
    if os.path.exists(f"./{scriptname}.out"):
        payoffvalue = read_payoff(f"{scriptname}.out", logfile)
        write_log(f"Payoff for {scriptname} is {payoffvalue}, calibration complete!", logfile)
        return payoffvalue # For optimisation runs, return payoff
    return 0 # Set default payoff value for simtypes that don't generate one


def check_opt(scriptname, logfile):
    """Check function for use with run_vengine_script for optimizations"""
    if check_zeroes(scriptname):
        write_log(f"Help! {scriptname} is being repressed!", logfile)
    return not check_zeroes(scriptname)


def check_zeroes(scriptname):
    """Check if an .out file has any parameters set to zero (indicates 
    Vengine error), return True if any parameters zeroed OR if # runs = 
    # restarts, and False otherwise"""
    filename = f"{scriptname}.out"
    with open(filename,'r') as f0:
        filedata = f0.readlines()
    
    checklist = []
    for line in filedata:
        if line[0] != ':': # Include only parameter lines
            if ' = 0 ' in line:
                checklist.append(True)
            else:
                checklist.append(False)
        elif ':RESTART_MAX' in line:
            restarts = regex.findall(r'\d+', line)[0]
    
    # Ensure number of simulations != number of restarts
    if f"After {restarts} simulations" in filedata[0]:
        checklist.append(True)
    
    return any(checklist)


# In[ ]:


controlfilename = input("Enter control file name (with extension):")
cf = json.load(open(controlfilename, 'r'))

# Unpack controlfile into variables
for k,v in cf.items():
    exec(k + '=v')

# Set up files in run directory and initialise logfile
master = Script(cf)
master.copy_model_files(f"{baserunname}_IterCal")
copy(f"../{controlfilename}", "./")
basedir = os.getcwd()
logfile = f"{basedir}/{baserunname}.log"
write_log(f"-----\nStarting new log at {time.ctime()}\nReady to work!", logfile)

# Run an optimization based on specified .voc
payoff = compile_script(cf, Script, 'main', 'opt', {}, logfile)
write_log(f"Optimization complete - payoff is {payoff}!", logfile)

# Run a simple model simulation
write_log(f"More work? Okay!", logfile)
time.sleep(2)
compile_script(cf, RunScript, 'main', 'run', {}, logfile, chglist=[('main', 'opt')])
write_log("Job done!", logfile)


# In[ ]:




