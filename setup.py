from distutils.core import Extension
from distutils.core import setup

# Set these so they match your system.
XLIBDIR = '/usr/X11R6/lib'
XINCLUDES = '/usr/X11R6/include'


MODULE1 = Extension('wmdocklib.pywmgeneral',
                    libraries=['Xpm', 'Xext', 'X11'],
                    library_dirs=[XLIBDIR],
                    include_dirs=[XINCLUDES],
                    sources=['wmdocklib/pywmgeneral.c'])

setup(name="pywmdockapps",
      version="1.23",
      description="Library for creating dockapps for Window Maker/AfterStep",
      author="Kristoffer Erlandsson & al.",
      author_email="mfrasca@zonnet.nl",
      url="http://pywmdockapps.sourceforge.net",
      license="(L)GPL",
      packages=['wmdocklib'],
      ext_modules=[MODULE1])
