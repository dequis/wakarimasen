# Wakarimasen installation guide.

Wakarimasen is still experimental software - use it at your own risk and
if you know how to fix stuff when it breaks.

## Requirements

* python >= 2.6, <= 3
* werkzeug
* sqlalchemy >= 0.8
* jinja2

### Supported deployment methods

* uWSGI (recommended)
* FastCGI
* CGI (fallback)

### Supported webservers

* Apache: Completely supported
* nginx: Works, but a few features such as bans rely in .htaccess (TODO)
* lighttpd: Should work (same as nginx), but untested.

Development server included (`python wakarimasen.py http`)

### Note on root access

Most instructions in here assume that you have at least a virtual private
server with root access. However, it's technically possible to install
requirements using virtualenv and even run uwsgi in shared hosts such as
dreamhost. See [this tutorial][dh] for that (Good luck!).

## Basic installation (CGI)

- For CGI based setups the source code must be placed somewhere in the docroot

- Copy config.py.example to config.py. Edit it and set ADMIN_PASS, SECRET and
SQL_ENGINE.  The format for SQL_ENGINE is the following:

        SQL_ENGINE = 'mysql://USERNAME:PASSWORD@HOSTNAME/DATABASE'

    You can also use sqlite:

        SQL_ENGINE = 'sqlite:///wakarimasen.sqlite'
        SQL_POOLING = False

    Note that this will create the database in the current directory - please
    avoid exposing it to the webserver!

- Now make sure the shebang line in wakarimasen.py points to the right
python interpreter and that the file has execute permissions. If you use suexec
for cgi, it must be chmod 755, too.

    Visit `http://example.com/wakarimasen.py` - This should open the first time
    setup page. Enter the ADMIN_PASS here.

- To create a new board called /temp/, copy the base_board directory:

        cp -r base_board temp

    Edit temp/board_config.py. Important settings are NUKE_PASS, TITLE and
    SQL_TABLE. Keep in mind most of those options are not supported for now
    (captcha, load balancing, proxy, etc).

- Go to `http://example.com/wakarimasen.py?board=temp` - This should rebuild the
cache and redirect you to your board.


## Webserver configuration

### uWSGI

uWSGI is the recommended deployment setup. It can also be the most complex to
setup, but not by much. This document is not going to cover the details, but
you can check the [uWSGI docs][ud]. In particular:

 * The [quickstart][qs] gives a rough outline of the process.
    * Note: wakarimasen can't run directly with the uwsgi http server for
      now, you need to put it behind a real webserver.
    * Note: The uwsgi "network installer" is awesome, try it out.
 * Using the [emperor][emp] can raise the enterpriseness of your setup
   significantly.
 * The [web server integration][ws] page gives several alternatives for each
   server.
    * There are a few modules for apache. You have to grab them from the uwsgi
      git repo and run the specified `apxs` command to compile and install.
    * Nginx has built-in support of uwsgi. That page describes how to use it.

More detailed instructions soon&trade;

### Apache + mod_fastcgi

The default html file of boards is usually called "wakaba.html", so add this to
your config (can be in .htaccess)

    DirectoryIndex wakaba.html

Enable CGI execution:

    <Directory "/path/to/wakarimasen">
        Options +ExecCGI
    </Directory>

Load mod_fastcgi or mod_fcgid:

    # mod_fastcgi
    LoadModule fastcgi_module modules/mod_fastcgi.so

    # *or* mod_fcgid:
    LoadModule fcgid_module modules/mod_fcgid.so

Handle .py files with it:

    # mod_fastcgi
    <IfModule fastcgi_module>
      AddHandler fastcgi-script .fcgi
    </IfModule>

    # *or* mod_fcgid
    <IfModule fcgid_module>
        AddHandler fcgid-script .py .fcgi
    </IfModule>

### Nginx + cgi with fcgiwrap

Turns out that nginx requires a listening fastcgi process, it doesn't do
process spawning. Wakarimasen doesn't work as a listening daemon either.

If you want a real nginx wakarimasen setup, use uwsgi, but this method is okay
to get something quick and dirty running.

Just install fcgiwrap from your distro and add this to the server block:

    index wakaba.html;
    include /etc/nginx/fcgiwrap.conf;

[dh]: http://uwsgi-docs.readthedocs.org/en/latest/tutorials/dreamhost.html
[ud]: http://uwsgi-docs.readthedocs.org/en/latest/
[qs]: http://uwsgi-docs.readthedocs.org/en/latest/WSGIquickstart.html
[emp]: http://uwsgi-docs.readthedocs.org/en/latest/Emperor.html
[ws]: http://uwsgi-docs.readthedocs.org/en/latest/WebServers.html
