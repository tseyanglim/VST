#!/usr/bin/env python
# coding: utf-8

# ## Parameter Value Updater for Vensim
# 
# This widget reads parameter values from a specified input file and writes those value to the corresponding parameters in a specified `mdl` output file, overwriting existing parameter values. For instance, hard-coded constant values in an `mdl` file could be replaced with calibrated parameter results from an `out` file. This is the reverse operation of writing a `cin` file based on changes made in SimSetup.
# 
# Requires two inputs:
# 1. `inputlist` - a text-format file with `varname` = `value` entries, e.g. `out` or `cin`; see Notes below
# 2. `mdlfile` - a Vensim `mdl` file
# 
# #### Notes:
# 1. Intended input file formats include `out` and `cin`, though any text-input format containing the syntax '`varname` = `value`' should work.
# 2. The code automatically creates a backup copy of the output file before overwriting. Note that rerunning the code subsequently *will* overwrite the backup copy, so check and restore as needed before rerunning!
# 3. Allowed `varname` syntax includes alphanumeric characters, subscript brackets `[]`, commas `,`, and underscores `_`. Other special characters are not allowed and will not be recognised.
# 4. The code should correctly ignore any lines commented out with `:C` per Vensim syntax.
# 5. Variables which end with other variable names (e.g. `ni peng neewom` contains `peng neewom`) *should* correctly be ignored.
# 6. Any variables in the output model *not* defined as constants (with a numeric value) will be quietly ignored, even if present in the input file.
# 7. **Important:** The code should correctly replace any subscripted variables defined as constants *with separate equations for subscript elements*, but will *not* replace subscripted variables defined in compact form.
# 
#     For instance, if the input file contains values specified for `Varname[Elm1] = 3` and `Varname[Elm2] = 4`, the code will successfully replace:
#     
#     `Varname[Elm1] = 1` --> `Varname[Elm1] = 3`
#     
#     `Varname[Elm2] = 2` --> `Varname[Elm1] = 4`
# 
#     BUT NOT:
#     
#     `Varname[Elm] = 1,2` --> `Varname[Elm] = 3,4`
# 
# 
# 8. Any other variable syntax not mentioned above, e.g. initial values, has not yet been tested; use with caution!
# 
# Please contact [Tse Yang Lim](mailto:tylim@mit.edu) with any questions or suggestions, especially if you find any variable syntax use cases not behaving as expected.
# 
# #### Update Notes:
# - v3 - Wrapped widget in function for future module compatibility
# - v2 - Fixed issue where variables containing other variable names would be erroneously updated as well.
# 
# #### TODO:
# - Consider adding handling of compact form subscripted constants (see #7 above)
# - Add logging function to record variables actually changed
# - Once necessary functions are incorporated into `VST` module, import from `VST` instead

# In[ ]:


import regex
from shutil import copy


def update_mdl_params(inputfile, mdlfile):
    """Read parameter values from `inputfile` and replace corresponding 
    parameter values in `mdlfile`"""
    
    # Compile regex to identify varnames and values from file text
    inregex = regex.compile(
        r"(?:<=\s?)?(?!\s)" # Identify optional '<=' and ignore preceding whitespace
        r"([a-zA-Z0-9\s\[\],_]*)" # Capture varname, possibly including [],_
        r"(?<! )\s*=\s*" # Ignore trailing whitespace on varname and identify '='
        r"(-?(?:0|[1-9]\d*)(?:\.\d*)?" # Capture value, incl. -. scientific notation
        r"(?:[eE][+\-]?\d+)?)(?:\s*<=)?" # Capture scientific notation and identify optional '<='
    )

    with open(inputfile, 'r') as f:
        lines = [line for line in f.readlines() if line[0] != ':'] # Ignore control/comment lines
        text = ''.join(lines)

    results = regex.findall(inregex, text) # Pull out list of (varname, value) tuples

    copy(mdlfile, f'./{mdlfile[:-4]}_BACKUP{mdlfile[-4:]}') # Create backup copy of model file

    with open(mdlfile, 'r') as m:
        mdl = m.read()
        
        for var, val in results: # Loop through list of regex results
            varregex = regex.compile(r"\n" # Include linebreak to avoid varname substrings
                                     + regex.escape(var) # Combine varname with existing value
                                     + r"\s*=\s*(-?(?:0|[1-9]\d*)(?:\.\d*)?(?:[eE][+\-]?\d+)?)")
            mdl = varregex.sub(f"{var} = {val}", mdl) # Substitute new varname and value

        ### TODO: consider whether loop necessary or substitution can be done simultaneously
        ### using compiled match pattern with '|'.join
        
    with open(mdlfile, 'w') as m: # Write output to model
        m.write(mdl)

    print("Substitution complete!")


# In[ ]:


# For widget version, get user input for inputfile and mdlfile
inputfile = input("Enter variable input filename (with extension):")
mdlfile = input("Enter model filename (with extension):")

update_mdl_params(inputfile, mdlfile)


# In[ ]:


000000000000000000000000000000000000000000000000000000000000000000000000
000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000

