#!/usr/bin/env python
# coding: utf-8

# ## PSRF Calculator
# 
# Simple standalone `py` / `ipynb` widget for calculating % of PSRF values (Gelman-Rubin convergence statistic) below specified thresholds, which is a common measure of convergence in MCMC.
# 
# For more information on PSRF, see [Vensim documentation](https://www.vensim.com/documentation/mcmc_output.html) and:
# >Stephen P. Brooks; Andrew Gelman, Journal of Computational and Graphical Statistics, Vol. 7, No. 4. (Dec., 1998), pp. 434-455.
# 
# This widget requires several inputs:
# 1. `runname` - name of the MCMC run, used to find the runname_MCMC_stats.dat file automatically generated by Vensim
# 2. `vensimpath` - file path for Vensim `.exe` file, required to convert `.dat` file to `.tab` file
# 3. `burnin` - the burnin period, if any, specified when running MCMC; simulations during the burnin period are excluded from PSRF calculations
# 4. `thresholds` - a Python-format list of threshold values against which to compare PSRF values; PSRF is expected to converge to `1`, so common thresholds are `1.2` or `1.1`
# 
# It returns a simple Python list of fractions of PSRF values post-burnin below the specified thresholds (in order). As an intermediate step, it also generates `runname_MCMC_stats.tab`, containing various MCMC summary stats in more readable tabular format than Vensim's default `.dat` output.
# 
# Please contact [Tse Yang Lim](mailto:tylim@mit.edu) with any questions or suggestions.
# 
# #### TODO:
# - Once necessary functions are incorporated into `VST` module, import from `VST` instead

# In[ ]:


import os
import time
import subprocess
import numpy as np
import pandas as pd

def compile_psrf(runname, vensimpath):
    """Using Vensim, convert MCMC_stats.dat output into tab file with 
    PSRF values (and other MCMC summary stats) for each simulation"""
    # Compile .cmd script to convert stats .dat to tabfile
    cmdtext = [
        "SPECIAL>NOINTERACTION\n",
        f"MENU>DAT2VDF|{runname}_MCMC_stats.dat\n",
        f"SIMULATE>RUNNAME|{runname}\n",
        f"MENU>VDF2TAB|{runname}_MCMC_stats|{runname}_MCMC_stats|\n",
        "SPECIAL>CLEARRUNS\n",
        "MENU>EXIT\n"
    ]

    with open(f"{runname}_PSRF.cmd", 'w') as scriptfile:
        scriptfile.writelines(cmdtext)

    if os.path.exists(f"./{runname}_MCMC_stats.dat"): # Make sure .dat file exists
        # Run .dat conversion with Vensim
        while True: # Keep trying until tabfile created successfully
            subprocess.run(f"{vensimpath} \"./{runname}_PSRF.cmd\"")
            time.sleep(1)
            if os.path.exists(f"./{runname}_MCMC_stats.tab"):
                break # If tabfile exists, move on
            print(f"Help! {runname} is being repressed!")
    else:
        print(f"Help! {runname}_MCMC_stats.dat file does not exist!")


def calc_psrf(runname, burnin, thresholds):
    """Using MCMC_stats.tab file (from `compile_psrf` function), return 
    % of PSRF values below each threshold in list of `thresholds`"""
    
    mcout = pd.read_csv(f'{runname}_MCMC_stats.tab', sep='\t', index_col=0)    
    
    # Subset to only rows containing PSRF values
    psrfs = [i for i in mcout.index if 'PSRF' in i]
    psrfs.remove('PSRF Payoff') # Except for this one
    mcout = mcout.loc[psrfs]
    
    # Further subset to only simulations after burnin period
    mcout.columns = mcout.columns.astype('float').astype('int') # Convert columns to int
    mcout = mcout[mcout.columns[mcout.columns > burnin]].dropna(axis=1)
    
    return [np.nanmean(mcout < t) for t in thresholds]


# In[ ]:


# For widget version, get user input for arguments needed
runname = input("Enter runname:") 
vensimpath = input("Enter Vensim .exe path (with extension):")
burnin = input("Enter MCMC burnin period:")
thresh_str = input("Enter threshold value[s], separated by commas:")

# Convert threshold input to numeric list
thresholds = [float(i.strip()) for i in thresh_str.split(',')]

print("Converting .dat file to .tab...")
compile_psrf(runname, vensimpath)
print("Calculating PSRF...")
prop_PSRF = calc_psrf(runname, burnin, thresholds)
print(f"PSRF values below {thresholds}:")
print(prop_PSRF)


# In[ ]:


000000000000000000000000000000000000000000000000000000000000000000000000
000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000

