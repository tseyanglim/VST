#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import os
import regex
import numpy as np


# 
# #### Check functions
# The `check_func` argument to `run_vengine_script` allows use of helper functions to catch additional bugs in Vengine output (e.g. nonexistent output, zeroing bug, inconsistent payoffs...); the helper functions should return `True` only if no bugs of concern have occurred. If checks fail, `run_vengine_script` will rerun itself. Existing check functions and the bugs they catch are detailed further below.
# 
# ##### check_output
# The most basic check function ensures that appropriate output (i.e. a `vdf` or `vdfx` file) has been produced. This is a good catch-all check that fails if anything major goes wrong, preventing the optimisation (or sensitivity analysis, etc.) from running.
# 
# ##### check_payoffs
# Running MCMC with Vengine sometimes results in inconsistent sets of results being produced; this can cause trouble down the line. The first symptom is different payoff values reported in the `out` and `rep` files, which this function should catch.
# 
# ##### check_restarts
# Sometimes runs fail silently, without causing Vensim/Vengine to actually crash, usually due to model error (e.g. floating point errors). In this case, an optimisation will 'run' but not yield meaningful results, usually terminating on the initial simulation (or after one simulation per restart). This function catches when the number of simulations equals the number of restarts specified, indicating this sort of failure.
# 
# ##### check_zeroes
# Vengine has an odd bug (still present as of Mar 2022 release) whereby parameters estimated in optimisation are sometimes set to `0` even when that's outside the allowed range for the parameter. If any parameters are erroneously 'zeroed' in this way, this function will catch them.
# 
# Note that this function only flags parameters estimated at `0` if `0` is outside the specified optimisation range for the parameter; if one of the bounds is set to `0`, then output values of `0` will not be flagged, *even if those values result from Vengine error*. For this reason, while working with Vengine, I suggest using very small absolute values (e.g. `+/- 1e-6`) in place of `0` for any parameter bounds when specifying optimisation control. For most formulations (e.g. additive, multiplicative, exponential), a very small value will not behave meaningfully differently from `0`.
# 
# 
# 

# In[ ]:


def write_log(string, logfile):
    """Writes printed script output to a logfile"""
    with open(logfile,'a') as f:
        f.write(string + "\n")
    print(string)


def get_value(file, varname):
    """General purpose function for reading values from .mdl, .out, etc. 
    files; returns value matching `varname` in a 'var = val' syntax
    """
    varregex = regex.compile(
        r'(?<=([^\w ]|\n)\s?'  # Identify optional leading <= e.g. in outfile
        + regex.escape(varname)  # Identify variable name
        + r'\s*=)\s*-?(?:\d*)(\.\d*)?([eE][+\-]?\d+)?' # Capture value following = sign
    )
    ### TODO: double check whether this regex pattern works with variable names 
    ### containing numbers or special characters
    
    with open(file, 'r') as f:
        filetext = f.read()
        value = float((regex.search(varregex, filetext))[0]) # Convert to numeric

    return value

    
def read_payoff(outfile, logfile):
    """Identifies payoff value from file, usually .OUT or .REP"""
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


def increment_seed(vocfile, logfile):
    """Increments random number seed in a .VOC file by 1"""
    with open(vocfile, 'r') as f:
        vocdata = f.read()
    seedregex = regex.compile(r':SEED=\d+')
    try:  # Identify random number seed
        i = int(regex.search(r'\d+', regex.search(seedregex, vocdata).group()).group())
        newdata = seedregex.sub(f":SEED={i+1}", vocdata) # Increment by 1
        with open(vocfile, 'w') as f:
            f.write(newdata)
    except:  # If VOC file contains no seed entry
        write_log("No seed found, skipping incrementing.", logfile)
        

def parse_outval(outputline):
    """Splits .out file output line into dict of variable name, value, 
    lower and upper bounds, filling +/- infinity as needed
    """
    out = [-np.inf, None, np.nan, np.inf]  # Initialise output w/ default values
    parts = outputline.split('= ')
    if parts[0].endswith('<'):  # If lower bound specified
        out[0:len(parts)] = [p.replace(" <", "").strip() for p in parts]
    else:  # If no lower bound specified
        out[1:len(parts)+1] = [p.replace(" <", "").strip() for p in parts]
    
    return {'Name': out[1], 'Value': float(out[2]), 
            'Lower': float(out[0]), 'Upper': float(out[3])}


def read_outvals(filename, transpose=False):
    """Converts full .out file into list of dicts of variable names, 
    values, lower and upper bounds, filling +/- infinity as needed; if 
    `transpose` is specified, converts into dict of tuples instead
    """
    with open(filename, 'r') as f:
        output = [line for line in f.readlines() if line[0] != ':']  # Ignore controls & comments
    
    if transpose:
        return dict(zip(['Name', 'Value', 'Lower', 'Upper'],  # Respecify dict keys
                        zip(*[parse_outval(line).values() for line in output])))
    else:
        return [parse_outval(line) for line in output]
    

def subset_lines(filename, linekey):
    """Clean a multi-line text file `filename`, such as an .out file, to 
    include only lines containing strings included in `linekey` (a list 
    of strings to keep); can be used to subset an .out file to a single 
    subscript element to prevent loading errors
    """
    with open(filename,'r') as f:
        filedata = f.readlines()

    newdata = [line for line in filedata if any(k in line for k in linekey)]
    
    with open(filename, 'w') as f:
        f.writelines(newdata)


# In[ ]:


def check_output(scriptname, logfile):
    """Check that output .vdf / .vdfx file exists, fail otherwise"""
    exists = (os.path.exists(f"./{scriptname}.vdf") or os.path.exists(f"./{scriptname}.vdfx"))
    if not exists:  # If neither VDF nor VDFX exists
        write_log(f"Help! {scriptname} is being repressed!", logfile)
    return exists


def check_payoffs(scriptname, logfile, threshold=0.1):
    """Check if .out and .rep file payoff difference exceeds `threshold` 
    (indicates Vengine bug, usually with MCMC)
    """
    # Calculate .out and .rep payoff discrepancy
    diff = read_payoff(f"{scriptname}.out", logfile) - read_payoff(f"{scriptname}.rep", logfile)
    write_log(f".OUT and .REP payoff difference is {diff}", logfile)
    
    if abs(diff) >= threshold:  # Difference greater than threshold indicates Vengine bug
        write_log(f"{scriptname} isn't an argument, it's just contradiction!", logfile)
        return False
    return True # Only returned if difference less than threshold


def check_restarts(scriptname, logfile):
    """Check if number of simulations equals number of restarts, which 
    indicates hidden optimisation failure (since each optimisation took 
    only one simulation, which is impossible)
    """
    with open(f"{scriptname}.out",'r') as f0:
        filedata = f0.readlines()
    
    restarts = 0 # Assign default value
    for line in filedata:
        if ':RESTART_MAX' in line:
            restarts = regex.findall(r'\d+', line)[0]  # Extract number of restarts
            break  # Stop looking through lines to save time
            
    # Ensure number of simulations != number of restarts
    if f"After {restarts} simulations" in filedata[0]:
        write_log(f"{scriptname} is Spam, egg, Spam, Spam, bacon, and Spam!", logfile)
        return False  # Fail if simulations = RESTART_MAX value
    return True  # Otherwise pass


def check_zeroes(scriptname, logfile):
    """Check if an .out file has any parameters incorrectly set to zero 
    (indicates Vengine error), return False if any parameters zeroed
    """
    checklist = []  # Initialise results container
    outdata = read_outvals(f"{scriptname}.out")
    
    for line in outdata:
        if (((0 < line['Lower']) or (0 > line['Upper']))  # If 0 is out of bounds
            and (line['Value'] == 0)):  # But parameter estimated at 0, indicating bug
            checklist.append(False)
            write_log(f"{line['Name']} is no more!", logfile)
        else:
            checklist.append(True)
    
    return all(checklist)  # Only yields True if no values incorrectly zeroed


# In[ ]:


000000000000000000000000000000000000000000000000000000000000000000000000
000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000

