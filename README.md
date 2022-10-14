# VST
 Vensim Script Tools for improving workflow in Vensim

This project is a collection of Python-based tools for working with [Vensim](https://vensim.com/) software for [system dynamics](http://en.wikipedia.org/wiki/System_dynamics) modelling.

## Materials

[**VST**](vst) contains the main codebase. For now, this contains usable code snippets, as well as `ipynb` notebooks with more extensive documentation; this will eventually be developed into an installable package.

[**VST Automation**](VST%20Automation) *TEMPORARY* contains a basic automation example for 15.879 use.

[**VST Testing**](VST%20Testing) contains a test package for the alpha version of `vst`, with an `ipynb` notebook showcasing a demonstration workflow based on the new syntax.

[**Widgets**](Widgets) contains handy standalone tools drawing on the main codebase; these are intended to be usable even with minimal coding proficiency, as executable `py` files / `ipynb` notebooks.

### Citing this code

If you use any VST code or widgets in any published work, please consider citing this repository:
>Lim, T.Y. (2022) "Vensim Script Tools." [https://github.com/tseyanglim/VST](https://github.com/tseyanglim/VST) Accessed (DATE)


## Why VST?

Vensim excels at its core competency of system dynamics modelling, and in particular, is *extremely* efficient at standard simulation model analyses (estimation/optimisation, sensitivity analyses).

VST leverages those advantages by providing tools that make it easier to integrate Vensim into more complex workflows and analysis pipelines, while still relying on Vensim as the core analytical / computational engine.

VST is thus different from, but complementary to, both [VenPy](https://github.com/VensimOfficial/venpy) and [PySD](https://github.com/SDXorg/pysd). VenPy utilises the Vensim DLL to interface more closely with Vensim models, in more interactive ways; PySD allows development and analysis of system dynamics models in native Python, without use of Vensim. Both allow greater flexibility and interactivity - especially the ability to use other data science tools - than is possible when relying on Vensim, but without the benefit of the computing power and speed that Vensim brings. Which one to use depends on your specific task.


#### TODO:
- Add citation file and Zenodo link
