Installation
============

Wakarimasen is still experimental software - use it at your own risk and
if you know how to fix stuff when it breaks.

Requirements
------------

-  Shell access to the server
-  Python >= 2.6, <= 3
-  Werkzeug
-  SQLAlchemy >= 0.8
-  Jinja2
-  ImageMagick commandline tools (``convert`` and ``identify``)
-  ``file`` command

Supported deployment methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  uWSGI
-  FastCGI
-  CGI (fallback)

Supported webservers
~~~~~~~~~~~~~~~~~~~~

-  Apache: Completely supported
-  nginx: Works, but a few features such as bans rely in .htaccess
-  lighttpd: Works, but same as nginx.

Development server included (``python wakarimasen.py http``)

Note on root access
~~~~~~~~~~~~~~~~~~~

Most instructions in here assume that you have at least a virtual
private server with root access. However, it's technically possible to
install requirements using
`virtualenv <http://www.virtualenv.org/en/latest/virtualenv.html>`__ and
use wakarimasen over cgi or fastcgi if already configured in a shared
server.

Installing dependencies
-----------------------

All dependencies should be available from the package manager of the
average linux distro.

If the python dependencies are too old, you could `install them with
pip <http://www.pip-installer.org/en/latest/quickstart.html>`__ instead.
If you don't want or can't do system-wide installs of python packages,
`virtualenv <http://www.virtualenv.org/en/latest/virtualenv.html>`__
exists and integrates nicely with pip.

If you don't have ``convert``, ``identify`` or ``file``, and can't
install them with a package manager system-wide, well, hope you don't
mind not having images in the imageboard.

Basic installation (CGI)
------------------------

This section explains the simplest setup, assuming that your webserver
already has CGI working. If you need to configure your webserver for cgi
or something more efficient than cgi, see :doc:`webserver`

#. First, place the source code somewhere in the docroot. That is, the
   ``wakarimasen.py`` file should be where you'd put an index.html file.

#. Copy config.py.example to config.py. Edit it and set ``ADMIN_PASS``,
   ``SECRET`` and ``SQL_ENGINE``. The format for ``SQL_ENGINE`` is the
   following:

   ::

       SQL_ENGINE = 'mysql://USERNAME:PASSWORD@HOSTNAME/DATABASE'

   You can also use sqlite:

   ::

       SQL_ENGINE = 'sqlite:///wakarimasen.sqlite'
       SQL_POOLING = False

   Note that this will create the database in the current directory -
   please avoid exposing it to the webserver!

#. Now make sure the shebang line in wakarimasen.py points to the right
   python interpreter (the default is ``#!/usr/bin/python2``, do not use
   a python 3.x interpreter) and that the file has execute permissions.
   If you use suexec for cgi, it must be chmod 755, too.

   Visit ``http://example.com/wakarimasen.py`` - This will check for any
   configuration errors in your installation, and if everything is okay,
   it should open the first time setup page. Enter the ``ADMIN_PASS``
   here.

#. To create a new board called /temp/, copy the base\_board directory:

   ::

       cp -r base_board temp

   Edit temp/board\_config.py. Important settings are NUKE\_PASS, TITLE
   and SQL\_TABLE. Keep in mind most of those options are not supported
   for now (captcha, load balancing, proxy, etc).

#. Go to ``http://example.com/wakarimasen.py?board=temp`` - This should
   rebuild the cache and redirect you to your board.
