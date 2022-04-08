[WHAT] 
pywmdockapps is the name of an GPL'd project containing one python package
(wmdocklib) and a few python scripts.  wmdocklib will help you develop
WindowMaker dockapps in python.  it is mostly a wrapper around the popular
wmgeneral.c, but some new functions have been added too.

wmdocklib is divided in two parts: a thin wrapper around the popular
wmgeneral.c and a thicker pywmhelpers.py module providing more pythonic
interface to the wmdocklib and a few additional functions (e.g.: handling
simple configuration files).  all functions provided by these modules are
imported in the namespace of wmdocklib so you won't need explicit importing
of either modules: just import wmdocklib.  It is adviced to only use those
functions provided by pywmhelpers and not touch the pywmgeneral module
directly at all.  For information about how to use the module, see the
documentation in pywmhelpers.py.  It is also possible to import it in the
interactive interpreter and issue 'help(pywmhelpers)'.

the sample scripts are described in the examples/README 
a small set of samples are provided.  all of them make use of the module
pywmgeneral.

[INSTALLATION]
python ./setup install

[CONTACT]
Anything related to this piece of software: please open an issue here.

