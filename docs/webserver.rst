Webserver configuration
-----------------------

Apache
~~~~~~

CGI
^^^

TODO (Should be very similar to the first steps of FastCGI setup..)

FastCGI
^^^^^^^

Add this to your config:

::

    DirectoryIndex wakaba.html

    <Directory "/path/to/wakarimasen">
        Options +ExecCGI
    </Directory>

Choose either ``mod_fastcgi``:

::

    LoadModule fastcgi_module modules/mod_fastcgi.so
    <IfModule fastcgi_module>
      AddHandler fastcgi-script .fcgi
    </IfModule>

Or ``mod_fcgid``:

::

    LoadModule fcgid_module modules/mod_fcgid.so
    <IfModule fcgid_module>
        AddHandler fcgid-script .py .fcgi
    </IfModule>

Nginx
~~~~~

CGI with fcgiwrap
^^^^^^^^^^^^^^^^^

See `this page <http://wiki.nginx.org/Fcgiwrap>`__ for fcgiwrap
installation details.

Then add this to the server block:

::

    index wakaba.html;
    include /etc/nginx/fcgiwrap.conf;

You should ensure that fcgiwrap.conf includes a location block, and that
it matches wakarimasen.py (sometimes it's limited to .cgi files). If it
doesn't have a location block, put that include inside one:

::

    location /wakarimasen.py {
        include /etc/nginx/fcgiwrap.conf;
    }

If you don't do this, fcgiwrap might do weird stuff like throwing '502
bad gateway' errors for most files.

FastCGI servers
^^^^^^^^^^^^^^^

Recent versions of wakarimasen have TCP and unix socket based standalone
fastcgi servers. To use them, start wakarimasen.py like this:

::

    # start a tcp fcgi server with the default settings, in 127.0.0.1:9000
    python wakarimasen.py fcgi_tcp

    # bind tcp fcgi server to a certain ethernet interface, port 9001
    python wakarimasen.py fcgi_tcp 192.168.0.1 9001

    # start a unix socket fcgi server in /tmp/derp
    python wakarimasen.py fcgi_unix /tmp/derp

In the nginx config:

::

    index wakaba.html;
    location /wakarimasen.py {
        include /etc/nginx/fastcgi.conf;
        fastcgi_pass unix:/tmp/derp;

        # or: fastcgi_pass 127.0.0.1:9001;
    }

When using unix sockets, check that the file is readable by the nginx
user.

Nginx doesn't have a fastcgi process spawner. You'll have to write a
init script, a systemd unit, or use something like
`supervisor <http://supervisord.org/configuration.html#fcgi-program-x-section-settings>`__.

Or just leave the thing running in a tmux/screen session, only to find a
few weeks later that your wakarimasen has been offline for a long time
because your server mysteriously rebooted.

Lighttpd
~~~~~~~~

CGI
^^^

Just add this to the config:

::

    server.modules += ("mod_cgi")
    cgi.assign = (".py"  => "/usr/bin/python2")
    index-file.names += ("wakaba.html")

As an nginx fanboy I'm slightly annoyed at how easy this was.

FastCGI
^^^^^^^

TODO

uWSGI
~~~~~

uWSGI is probably the best deployment setup. It can also be the most
complex to setup. This document is not going to cover the details, but
you can check the `uWSGI
docs <http://uwsgi-docs.readthedocs.org/en/latest/>`__. In particular:

-  The
   `quickstart <http://uwsgi-docs.readthedocs.org/en/latest/WSGIquickstart.html>`__
   gives a rough outline of the process.

   -  Note: wakarimasen can't run directly with the uwsgi http server
      for now, you need to put it behind a real webserver.
   -  Note: The uwsgi "network installer" is awesome, try it out.

-  Using the
   `emperor <http://uwsgi-docs.readthedocs.org/en/latest/Emperor.html>`__
   can raise the enterpriseness of your setup significantly.
-  The `web server
   integration <http://uwsgi-docs.readthedocs.org/en/latest/WebServers.html>`__
   page gives several alternatives for each server.

   -  There are a few modules for apache. You have to grab them from the
      uwsgi git repo and run the specified ``apxs`` command to compile
      and install.
   -  Nginx has built-in support of uwsgi. That page describes how to
      use it.

More detailed instructions soon™
