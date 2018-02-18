================================
etcdfs: Filesystem based on etcd
================================

About
-----

``etcdfs`` is a simple FUSE filesystem based on etcd. It allows you to mount the
key space of an etcd cluster as a filesystem.

The main goal of this project is to be able to work with etcd with well-known
Linux tools, like ``ls``, ``cp``, ``grep``, rather than ``etcdctl`` or any
other etcd command-line client.

``etcdfs`` can also be useful in case a very simple shared storage is required,
like in the case of common configuration.

How it works
------------

``etcdfs`` can mount the whole etcd hierarchical key space (``/``) or any part
of it. Etcd keys are mapped to FS files and etcd directories are mapped to FS
directories.

Installation
------------

First you will need to install FUSE from http://github.com/libfuse/libfuse.
After installing FUSE, install the ``etcdfs`` Python package:

    $ python setup.py install

How to use
----------

Simply run ``etcdfs`` and provide the mountpoint and the etcd keyspace that
you want to mount:

	$ etcdfs --basedir $basedir $mountpoint

Unmount the filesystem by using ``fusermount``:

    $ fusermount -u $mountpoint

Unsupported Operations
----------------------

* ``chmod``
* ``chown``
* ``getxattr``
* ``ioctl``
* ``link``
* ``listxattr``
* ``readlink``
* ``removexattr``
* ``rename``
* ``setxattr``
* ``statfs``
* ``symlink``
* ``utimens``

License
-------

Free software: BSD license
