#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Filesystem based on etcd."""
from . import __version__

import sys
import etcd
import logging
import argparse
import urlparse

log = logging.getLogger(__name__)

DESCRIPTION = "Filesystem based on etcd"
LOG_FORMAT = ("%(asctime)-15s etcdfs pid=%(process)d "
              "%(module)s:%(lineno)s [%(levelname)s] %(message)s")


def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("-v", "--verbose", default=False,
                        action="store_true",
                        help="Increase logging verbosity")
    parser.add_argument("--endpoint", default="http://127.0.0.1:2379",
                        help="Connect to etcd server at %(metavar)s")
    parser.add_argument("--basedir", default="/",
                        help="Mount the etcd directory %(metavar)s")
    args = parser.parse_args()

    lvl = logging.DEBUG if args.verbose else logging.INFO
    handler = logging.StreamHandler()
    formatter = logging.Formatter(LOG_FORMAT)
    handler.setFormatter(formatter)
    log.addHandler(handler)
    log.setLevel(lvl)

    log.info("Initialing etcdfs. Version: %s", __version__)

    # Parse URL and create etcd client
    # FIXME: Add authentication and other options
    url = urlparse.urlparse(args.endpoint)
    log.info("Connecting at etcd endpoint '%s'", args.endpoint)
    client = etcd.Client(protocol=url.scheme, host=url.hostname, port=url.port)

    # Check base directory
    basedir = args.basedir
    log.info("Mounting base etcd directory '%s'", basedir)
    try:
        r = client.read(basedir, dir=True)
        if not r.dir:
            log.error("Etcd key '%s' is not a directory", basedir)
    except etcd.EtcdKeyNotFound:
        log.error("Base etcd directory '%s' does not exist", basedir)
        sys.exit(1)

    log.info("Exiting")


if __name__ == "__main__":
    main()
