Commandline actions
====================

Wakarimasen includes a few administrative commands that can be used from
the commandline.

To use them, do:

::

    python wakarimasen.py <command> [parameters]

To see usage info of an individual command, do:

::

    python wakarimasen.py help <command>

Servers
-------

- fcgi_tcp *[host [port]]*

  Starts a standalone FastCGI server over tcp. Defaults to listening on
  127.0.0.1, port 9000

- fcgi_unix *<path>*

  Starts a standalone FastCGI over unix socket. The path is required,
  and you should ensure the permissions allow the webserver to connect.

- http *[host [port]]*

  Starts a http server for development/testing purposes. Do not use in
  production, even cgi is better than this.

Admin actions
-------------

- delete_by_ip *<ip> <boards>*

  *<boards>* is a comma separated list of board names.

- rebuild_cache *<board>*

- rebuild_global_cache

Admin actions require some knowledge about the webserver environment.
For this reason, you need to pass the following environment variables

- ``DOCUMENT_ROOT``: full filesystem path to html files.
  Example: ``/srv/http/imageboard.example.com/``

- ``SCRIPT_NAME``: url to wakarimasen.py without host part.
  Example: ``/wakarimasen.py``

- ``SERVER_NAME``: hostname of the webserver.
  Example: ``imageboard.example.com``

- ``SERVER_PORT``: port of the webserver *(optional)*.
  Example: ``80``

If these values are wrong, it will probably result in a bunch of broken
links in the generated pages. Try rebuilding cache from the real web
interface.

Complete example usage:

::

    DOCUMENT_ROOT=$PWD SCRIPT_NAME=/wakarimasen.py SERVER_NAME=0.0.0.0 \
        python wakarimasen.py rebuild_global_cache

You could also have a script that sets this for you.
