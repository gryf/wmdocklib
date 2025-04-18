/* pywmgeneral.c
 *
 * Python bindings to some of the most important functions in the widely used
 * wmgeneral.c. Also some added functions. The rc file parser is removed since
 * Python provide better facilities for this.
 *
 * Copyright (C) 2003 Kristoffer Erlandsson
 *
 * Licensed under the GNU General Public License.
 *
 * History:
 *
 * 2003-06-24 Kristoffer Erlandsson
 * Added some additional event handling.
 *
 * 2003-06-16 Kristoffer Erlandsson
 * Added checkForMouseClick to make catching of mouse clicks available from
 * Python.
 *
 * 2003-06-14 Kristoffer Erlandsson
 * Finished support for "everything" included in wmgeneral by default.
 *
 * 2003-06-13 Kristoffer Erlandsson
 * File created made most of the pure wrapper functions and xpm inclusion.
 *
 *
 *
 * Thanks to Martijn Pieterse for createing the original wmgeneral.c
 *
 */

#include <Python.h>
#include "structmember.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <ctype.h>
#include <stdarg.h>

#include <X11/Xlib.h>
#include <X11/xpm.h>
#include <X11/extensions/shape.h>

#include "pywmgeneral.h"

  /*****************/
 /* X11 Variables */
/*****************/

Window       Root;
int          screen;
int          x_fd;
int          d_depth;
XSizeHints   mysizehints;
XWMHints     mywmhints;
Pixel        back_pix, fore_pix;
char        *Geometry = "";
Window       iconwin, win;
GC           NormalGC;
XpmIcon      wmgen;
Pixmap       pixmask;
Atom         deleteAtom; /* Added 2003-06-24 for graceful shutdown. */

/*****************************************************************************/
/* The Python stuff                                                          */
/*****************************************************************************/
static char **pixmap;  /* Global pixmap, we only support one of these */
static char *maskBits; /* Global maskbits, also only 1 supported */

char **pyListToStrs(PyObject *l) {
    /* Convert a python list of strings to a char **. */
    int size, i;
    char **target;
    PyObject *s;
    if (!PyList_Check(l)) {
        PyErr_SetString(PyExc_TypeError, "List expected.");
        return NULL;
    }
    size = PyList_Size(l);
    target = (char **)malloc(size * sizeof(char *));
    for (i = 0; i < size; i++) {
        s = PySequence_GetItem(l, i);
        if (s == NULL)
            return NULL; /* Shouldn't happen. */
        if (!PyUnicode_Check(s)) {
            PyErr_SetString(PyExc_TypeError, "String expected.");
            return NULL;
        }
        target[i] = (char *) PyUnicode_AsUTF8(s);
    }
    return target;
}


static PyObject *
pywmgeneral_includePixmap(PyObject *self, PyObject *args) {
    /* Set the global pixmap. */
    PyObject *arg;
    if (!PyArg_ParseTuple(args, "O", &arg))
        return NULL;
    if(!(pixmap = pyListToStrs(arg)))
        return NULL;
    Py_INCREF(Py_None);
    return Py_None;
}


static PyObject *
pywmgeneral_openXwindow(PyObject *self, PyObject *args) {
    /* This function now uses the global variable pixmap as xpm and creates the
     * xbm mask of the given height and width from this one. IOW no other xbm
     * masks are supported at the moment. This shouldn't be needed except in
     * special cases (I think...)
     */
    int argc, width, height;
    PyObject *argvTmp;
    char **argv;
    if (!PyArg_ParseTuple(args, "iOii", &argc, &argvTmp, &width, &height))
        return NULL;
    if (!(argv = pyListToStrs(argvTmp)))
        return NULL;
    maskBits = (char *)malloc(width * height * sizeof(char));
    createXBMfromXPM(maskBits, pixmap, width, height);
    openXwindow(argc, argv, pixmap, maskBits, width, height);
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *
pywmgeneral_redrawWindow(PyObject *self, PyObject *args) {
    if (!PyArg_ParseTuple(args, ""))
        return NULL;
    RedrawWindow();
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *
pywmgeneral_redrawWindowXY(PyObject *self, PyObject *args) {
    int x, y;
    if (!PyArg_ParseTuple(args, "ii",  &x, &y))
        return NULL;
    RedrawWindowXY(x, y);
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *
pywmgeneral_addMouseRegion(PyObject *self, PyObject *args) {
    int index, left, top, right, bottom;
    if (!PyArg_ParseTuple(args, "iiiii", &index, &left, &top, &right, &bottom))
        return NULL;
    AddMouseRegion(index, left, top, right, bottom);
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *
pywmgeneral_checkMouseRegion(PyObject *self, PyObject *args) {
    int x, y;
    if (!PyArg_ParseTuple(args, "ii", &x, &y))
        return NULL;
    return Py_BuildValue("i", CheckMouseRegion(x, y));
}

static PyObject *
pywmgeneral_copyXPMArea(PyObject *self, PyObject *args) {
    /* sx - source x,      sy - source y
     * sw - width,         sw - height
     * dx - destination x, dy - destination y
     *
     * in the original wmgeneral.c variables are named differently.
     */
    int sx, sy, sw, sh, dx, dy;
    if (!PyArg_ParseTuple(args, "iiiiii", &sx, &sy, &sw, &sh, &dx, &dy))
        return NULL;
    copyXPMArea(sx, sy, sw, sh, dx, dy);
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *
pywmgeneral_checkForEvents(PyObject *self, PyObject *args) {
    /* If we find an event we handle, return a dictionary containing some
     * information about it. Return None if there are no events we handle.
     * Ignore events we don't handle. Also we provide a handler for when the
     * window is exposed, redraw it.
     */
    XEvent event;
    static char buffer[8];
    int bufsize = 8;
    XComposeStatus dummy;
    KeySym keysym;
    int count;

    if (!PyArg_ParseTuple(args, ""))
        return NULL;
    while (XPending(display)) {
        XNextEvent(display, &event);
        switch(event.type) {

            case Expose:
                RedrawWindow();
                break;

            case EnterNotify:
            case LeaveNotify:
                /* needed by KeyPress/release, otherwise events go to parent. */
                XSetInputFocus(display, PointerRoot, RevertToParent, CurrentTime);
                break;

            case KeyPress:
                count = XLookupString((XKeyEvent*)&event, buffer, bufsize, &keysym, &dummy);
                buffer[count] = '\0';

                return Py_BuildValue("{s:s,s:i,s:i,s:s}",
                                     "type", "keypress",
                                     "state", event.xkey.state,
                                     "keycode", event.xkey.keycode,
                                     "button", buffer);

            case ButtonPress:
            case ButtonRelease:
                return Py_BuildValue("{s:s,s:i,s:i,s:i}",
                                     "type", event.type==ButtonPress?"buttonpress":"buttonrelease",
                                     "button", event.xbutton.button,
                                     "x", event.xbutton.x, "y", event.xbutton.y);

            case ClientMessage:
                if((Atom)event.xclient.data.l[0] == deleteAtom) {
                    XCloseDisplay(display);
                    return Py_BuildValue("{s:s}", "type", "destroynotify");
                }
                break;

            case DestroyNotify:
                /* This seems to never happen, why? */
                XCloseDisplay(display);
                return Py_BuildValue("{s:s}", "type", "destroynotify");

        }
    }
    Py_INCREF(Py_None);
    return Py_None;
}

static PyMethodDef PyWmgeneralMethods[] = {
    {"open_xwindow", pywmgeneral_openXwindow, METH_VARARGS,
        "Open the X window containing everything."},
    {"include_pixmap", pywmgeneral_includePixmap, METH_VARARGS,
        "Set the global pixmap that will be used as a mask and for everything else."},
    {"redraw_window", pywmgeneral_redrawWindow, METH_VARARGS,
        "Redraw the window."},
    {"redraw_window_xy", pywmgeneral_redrawWindowXY, METH_VARARGS,
        "Redraw a given region of the window."},
    {"add_mouse_region", pywmgeneral_addMouseRegion, METH_VARARGS,
        "Add a mouse region with a given index."},
    {"check_mouse_region", pywmgeneral_checkMouseRegion, METH_VARARGS,
        "Check if the given coordinates are in any mouse region."},
    {"copy_xpm_area", pywmgeneral_copyXPMArea, METH_VARARGS,
        "Copy an area of the global XPM."},
    {"check_for_events", pywmgeneral_checkForEvents, METH_VARARGS,
        "Check for some Xevents"},
    {NULL, NULL, 0, NULL}
};

/*
 * here comes the definition of the class Drawable
 *
 */

typedef struct {
    PyObject_HEAD
    /* Type-specific fields go here. */
    int has_drawable;
    Pixmap drawable;
    int width, height;
} drawable_DrawableObject;

static PyObject *
Drawable_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    drawable_DrawableObject *self;

    self = (drawable_DrawableObject *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->has_drawable = 0;
        self->width = 0;
        self->height = 0;
    }

    return (PyObject *)self;
}

static int
Drawable_init(drawable_DrawableObject *self, PyObject *args, PyObject *kwds)
{
    unsigned int w, h;
    if (! PyArg_ParseTuple(args, "ii", &w, &h))
        return -1;
    if (!wmgen.attributes.depth) {
        PyErr_SetString(PyExc_RuntimeError, "X client must be initialized first.");
        return -1;
    }

    if (self->has_drawable)
        XFreePixmap(display, self->drawable);
    self->has_drawable = 1;
    self->width = w;
    self->height = h;
    self->drawable = XCreatePixmap(display, wmgen.pixmap,
                                   w, h, wmgen.attributes.depth);

    return 0;
}

static void
Drawable_dealloc(drawable_DrawableObject *self)
{
    if (self->has_drawable)
        XFreePixmap(display, self->drawable);
}

static PyObject *
Drawable_xCopyAreaToWindow(drawable_DrawableObject *self, PyObject *args, PyObject *kwds)
{
    unsigned int src_x, src_y, width, height, dst_x, dst_y;
    if (! PyArg_ParseTuple(args, "iiiiii", &src_x, &src_y, &width, &height, &dst_x, &dst_y))
        return NULL;

    XCopyArea(display, self->drawable, wmgen.pixmap, NormalGC,
              src_x, src_y, width, height, dst_x, dst_y);

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *
Drawable_xClear(drawable_DrawableObject *self, PyObject *args, PyObject *kwds)
{
    XFillRectangle(display, self->drawable, NormalGC,
                   0, 0, self->width, self->height);

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *
Drawable_xCopyAreaFromWindow(drawable_DrawableObject *self, PyObject *args, PyObject *kwds)
{
    unsigned int src_x, src_y, width, height, dst_x, dst_y;
    if (! PyArg_ParseTuple(args, "iiiiii", &src_x, &src_y, &width, &height, &dst_x, &dst_y))
        return NULL;

    XCopyArea(display, wmgen.pixmap, self->drawable, NormalGC,
              src_x, src_y, width, height, dst_x, dst_y);

    Py_INCREF(Py_None);
    return Py_None;
}

static PyMemberDef Drawable_members[] = {
    {NULL}  /* Sentinel */
};

static PyMethodDef Drawable_methods[] = {
    {"xCopyAreaFromWindow", (PyCFunction)Drawable_xCopyAreaFromWindow, METH_VARARGS,
     "copy from the drawable to the global pixmap"
    },
    {"xCopyAreaToWindow", (PyCFunction)Drawable_xCopyAreaToWindow, METH_VARARGS,
     "copy from the global pixmap into the drawable"
    },
    {"xClear", (PyCFunction)Drawable_xClear, METH_NOARGS,
     "clears the pixmap"
    },
    {NULL}  /* Sentinel */
};

static PyTypeObject drawable_DrawableType = {
    PyObject_HEAD_INIT(0)
    "pyywmgeneral.Drawable",   /*tp_name*/
    sizeof(drawable_DrawableObject), /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)Drawable_dealloc, /*tp_dealloc*/
    0,                         /*tp_print*/
    0,                         /*tp_getattr*/
    0,                         /*tp_setattr*/
    0,                         /*tp_compare*/
    0,                         /*tp_repr*/
    0,                         /*tp_as_number*/
    0,                         /*tp_as_sequence*/
    0,                         /*tp_as_mapping*/
    0,                         /*tp_hash */
    0,                         /*tp_call*/
    0,                         /*tp_str*/
    0,                         /*tp_getattro*/
    0,                         /*tp_setattro*/
    0,                         /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE, /*tp_flags*/
    "Drawable objects",        /* tp_doc */
    0,                         /* tp_traverse */
    0,                         /* tp_clear */
    0,                         /* tp_richcompare */
    0,                         /* tp_weaklistoffset */
    0,                         /* tp_iter */
    0,                         /* tp_iternext */
    Drawable_methods,          /* tp_methods */
    Drawable_members,          /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    (initproc)Drawable_init,   /* tp_init */
    0,                         /* tp_alloc */
    Drawable_new,              /* tp_new */
};

/*
 * end of class Drawable
 *
 */

/*****************************************************************************/
/* Original C sources (With some modifications)                              */
/*****************************************************************************/

  /*****************/
 /* Mouse Regions */
/*****************/

typedef struct {
    int        enable;
    int        top;
    int        bottom;
    int        left;
    int        right;
} MOUSE_REGION;

MOUSE_REGION    mouse_region[MAX_MOUSE_REGION];

  /***********************/
 /* Function Prototypes */
/***********************/

static void GetXPM(XpmIcon *, char **);
static Pixel GetColor(char *);
void RedrawWindow(void);
void AddMouseRegion(int, int, int, int, int);
int CheckMouseRegion(int, int);

/*******************************************************************************\
|* GetXPM                                                                      *|
\*******************************************************************************/

static void GetXPM(XpmIcon *wmgen, char *pixmap_bytes[]) {

    XWindowAttributes    attributes;
    int                    err;

    /* For the colormap */
    XGetWindowAttributes(display, Root, &attributes);

    wmgen->attributes.valuemask |= (XpmReturnPixels | XpmReturnExtensions);
    wmgen->attributes.depth = attributes.depth;

    err = XpmCreatePixmapFromData(display, Root, pixmap_bytes, &(wmgen->pixmap),
                    &(wmgen->mask), &(wmgen->attributes));

    if (err != XpmSuccess) {
        fprintf(stderr, "Not enough free colorcells. %d\n", err);
        exit(1);
    }
}

/*******************************************************************************\
|* GetColor                                                                    *|
\*******************************************************************************/

static Pixel GetColor(char *name) {

    XColor                color;
    XWindowAttributes    attributes;

    XGetWindowAttributes(display, Root, &attributes);

    color.pixel = 0;
    if (!XParseColor(display, attributes.colormap, name, &color)) {
        fprintf(stderr, "wm.app: can't parse %s.\n", name);
    } else if (!XAllocColor(display, attributes.colormap, &color)) {
        fprintf(stderr, "wm.app: can't allocate %s.\n", name);
    }
    return color.pixel;
}

/*******************************************************************************\
|* flush_expose                                                                *|
\*******************************************************************************/

static int flush_expose(Window w) {

    XEvent         dummy;
    int            i=0;

    while (XCheckTypedWindowEvent(display, w, Expose, &dummy))
        i++;

    return i;
}

/*******************************************************************************\
|* RedrawWindow                                                                *|
\*******************************************************************************/

void RedrawWindow(void) {

    flush_expose(iconwin);
    XCopyArea(display, wmgen.pixmap, iconwin, NormalGC,
              0,0, wmgen.attributes.width, wmgen.attributes.height, 0,0);
    flush_expose(win);
    XCopyArea(display, wmgen.pixmap, win, NormalGC,
              0,0, wmgen.attributes.width, wmgen.attributes.height, 0,0);
}

/*******************************************************************************\
|* RedrawWindowXY                                                              *|
\*******************************************************************************/

void RedrawWindowXY(int x, int y) {

    flush_expose(iconwin);
    XCopyArea(display, wmgen.pixmap, iconwin, NormalGC,
                x,y, wmgen.attributes.width, wmgen.attributes.height, 0,0);
    flush_expose(win);
    XCopyArea(display, wmgen.pixmap, win, NormalGC,
                x,y, wmgen.attributes.width, wmgen.attributes.height, 0,0);
}

/*******************************************************************************\
|* AddMouseRegion                                                              *|
\*******************************************************************************/

void AddMouseRegion(int index, int left, int top, int right, int bottom) {

    if (index < MAX_MOUSE_REGION) {
        mouse_region[index].enable = 1;
        mouse_region[index].top = top;
        mouse_region[index].left = left;
        mouse_region[index].bottom = bottom;
        mouse_region[index].right = right;
    }
}

/*******************************************************************************\
|* CheckMouseRegion                                                            *|
\*******************************************************************************/

int CheckMouseRegion(int x, int y) {

    int        i;
    int        found;

    found = 0;

    for (i=0; i<MAX_MOUSE_REGION && !found; i++) {
        if (mouse_region[i].enable &&
            x <= mouse_region[i].right &&
            x >= mouse_region[i].left &&
            y <= mouse_region[i].bottom &&
            y >= mouse_region[i].top)
            found = 1;
    }
    if (!found) return -1;
    return (i-1);
}

/*******************************************************************************\
|* createXBMfromXPM                                                            *|
\*******************************************************************************/
void createXBMfromXPM(char *xbm, char **xpm, int sx, int sy) {

    int        i,j,k;
    int        width, height, numcol, depth;
    int     zero=0;
    unsigned char    bwrite;
    int        bcount;
    int     curpixel;

    sscanf(*xpm, "%d %d %d %d", &width, &height, &numcol, &depth);


    for (k=0; k!=depth; k++)
    {
        zero <<=8;
        zero |= xpm[1][k];
    }

    for (i=numcol+1; i < numcol+sy+1; i++) {
        bcount = 0;
        bwrite = 0;
        for (j=0; j<sx*depth; j+=depth) {
            bwrite >>= 1;

            curpixel=0;
            for (k=0; k!=depth; k++)
            {
                curpixel <<=8;
                curpixel |= xpm[i][j+k];
            }

            if ( curpixel != zero ) {
                bwrite += 128;
            }
            bcount++;
            if (bcount == 8) {
                *xbm = bwrite;
                xbm++;
                bcount = 0;
                bwrite = 0;
            }
        }
    }
}

/*******************************************************************************\
|* copyXPMArea                                                                 *|
\*******************************************************************************/

void copyXPMArea(int x, int y, int sx, int sy, int dx, int dy) {
    /* in pywmgeneral_copyXPMArea variables are named differently.
     */

    XCopyArea(display, wmgen.pixmap, wmgen.pixmap, NormalGC, x, y, sx, sy, dx, dy);

}

/*******************************************************************************\
|* copyXBMArea                                                                 *|
\*******************************************************************************/

void copyXBMArea(int x, int y, int sx, int sy, int dx, int dy) {

    XCopyArea(display, wmgen.mask, wmgen.pixmap, NormalGC, x, y, sx, sy, dx, dy);
}


/*******************************************************************************\
|* setMaskXY                                                                   *|
\*******************************************************************************/

void setMaskXY(int x, int y) {

    XShapeCombineMask(display, win, ShapeBounding, x, y, pixmask, ShapeSet);
    XShapeCombineMask(display, iconwin, ShapeBounding, x, y, pixmask, ShapeSet);
}

/*******************************************************************************\
|* openXwindow                                                                 *|
\*******************************************************************************/
void openXwindow(int argc, char *argv[], char *pixmap_bytes[], char *pixmask_bits, int pixmask_width, int pixmask_height) {

    unsigned int   borderwidth = 1;
    XClassHint     classHint;
    char          *display_name = NULL;
    char          *wname = argv[0];
    XTextProperty  name;

    XGCValues      gcv;
    unsigned long  gcm;

    char          *geometry = NULL;

    int            dummy=0;
    int            i, wx, wy;

    /* Changed to work better with Python. Changed check in for loop to control
     * argc instead of argv.
     */
    for (i=1; i < argc; i++) {
        if (!strcmp(argv[i], "-display")) {
            display_name = argv[i+1];
            i++;
        }
        if (!strcmp(argv[i], "-geometry")) {
            geometry = argv[i+1];
            i++;
        }
    }

    if (!(display = XOpenDisplay(display_name))) {
        fprintf(stderr, "%s: can't open display %s\n",
                wname, XDisplayName(display_name));
        exit(1);
    }
    screen  = DefaultScreen(display);
    Root    = RootWindow(display, screen);
    d_depth = DefaultDepth(display, screen);
    x_fd    = XConnectionNumber(display);

    /* Convert XPM to XImage */
    GetXPM(&wmgen, pixmap_bytes);

    /* Create a window to hold the stuff */
    mysizehints.flags = USSize | USPosition;
    mysizehints.x = 0;
    mysizehints.y = 0;

    back_pix = GetColor("white");
    fore_pix = GetColor("black");

    XWMGeometry(display, screen, Geometry, NULL, borderwidth, &mysizehints,
                &mysizehints.x, &mysizehints.y,&mysizehints.width,&mysizehints.height, &dummy);

    mysizehints.width = pixmask_width;
    mysizehints.height = pixmask_height;

    win = XCreateSimpleWindow(display, Root, mysizehints.x, mysizehints.y,
                              mysizehints.width, mysizehints.height, borderwidth,
                              fore_pix, back_pix);

    iconwin = XCreateSimpleWindow(display, win, mysizehints.x, mysizehints.y,
                                  mysizehints.width, mysizehints.height, borderwidth,
                                  fore_pix, back_pix);


    /* Added 2003-06-24 for graceful shutdown. */
    deleteAtom = XInternAtom(display, "WM_DELETE_WINDOW", 0);
    XSetWMProtocols(display, win, &deleteAtom, 1);


    /* Activate hints */
    XSetWMNormalHints(display, win, &mysizehints);
    classHint.res_name = wname;
    classHint.res_class = wname;
    XSetClassHint(display, win, &classHint);

    XSelectInput(display, win,
                 ExposureMask |
                 ButtonPressMask |
                 ButtonReleaseMask |	/* added ButtonReleaseMask *charkins*/
                 KeyPressMask |           /* Try this to get keyboard working */
                 PointerMotionMask |
                 FocusChangeMask |
                 LeaveWindowMask |
                 StructureNotifyMask |
                 EnterWindowMask );
    XSelectInput(display, iconwin,
                 ExposureMask |
                 ButtonPressMask |
                 ButtonReleaseMask |	/* added ButtonReleaseMask *charkins*/
                 KeyPressMask |           /* Try this to get keyboard working */
                 PointerMotionMask |
                 FocusChangeMask |
                 LeaveWindowMask |
                 StructureNotifyMask |
                 EnterWindowMask );
                 //ButtonPressMask | ButtonReleaseMask | KeyPressMask | KeyReleaseMask |
                 //ExposureMask |
                 //FocusChangeMask | EnterWindowMask |
                 //PointerMotionMask | StructureNotifyMask);

    if (XStringListToTextProperty(&wname, 1, &name) == 0) {
        fprintf(stderr, "%s: can't allocate window name\n", wname);
        exit(1);
    }

    XSetWMName(display, win, &name);

    /* Create GC for drawing */

    gcm = GCForeground | GCBackground | GCGraphicsExposures;
    gcv.foreground = fore_pix;
    gcv.background = back_pix;
    gcv.graphics_exposures = 0;
    NormalGC = XCreateGC(display, Root, gcm, &gcv);

    /* ONLYSHAPE ON */

    pixmask = XCreateBitmapFromData(display, win, pixmask_bits, pixmask_width, pixmask_height);

    XShapeCombineMask(display, win, ShapeBounding, 0, 0, pixmask, ShapeSet);
    XShapeCombineMask(display, iconwin, ShapeBounding, 0, 0, pixmask, ShapeSet);

    /* ONLYSHAPE OFF */

    mywmhints.initial_state = WithdrawnState;
    mywmhints.icon_window = iconwin;
    mywmhints.icon_x = mysizehints.x;
    mywmhints.icon_y = mysizehints.y;
    mywmhints.window_group = win;
    mywmhints.flags = StateHint | IconWindowHint | IconPositionHint | WindowGroupHint;

    XSetWMHints(display, win, &mywmhints);

    XSetCommand(display, win, argv, argc);
    XMapWindow(display, win);

    if (geometry) {
        if (sscanf(geometry, "+%d+%d", &wx, &wy) != 2) {
            fprintf(stderr, "Bad geometry string.\n");
            exit(1);
        }
        XMoveWindow(display, win, wx, wy);
    }
}

static struct PyModuleDef pywmgeneral = {
    PyModuleDef_HEAD_INIT,
    "pywmgeneral",
    "base C module for wmdocklib",
    -1,
    PyWmgeneralMethods
};

#ifndef PyMODINIT_FUNC	/* declarations for DLL import/export */
#define PyMODINIT_FUNC void
#endif

PyMODINIT_FUNC
PyInit_pywmgeneral(void) {
    PyObject* m;

    drawable_DrawableType.tp_new = PyType_GenericNew;
    if (PyType_Ready(&drawable_DrawableType) < 0)
        return NULL;

    m = PyModule_Create(&pywmgeneral);

    if (m == NULL)
        return NULL;

    Py_INCREF(&drawable_DrawableType);
    /* Py_XINCREF(&drawable_DrawableType); */
    PyModule_AddObject(m, "Drawable", (PyObject *)&drawable_DrawableType);
    return m;
}
