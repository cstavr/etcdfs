#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Filesystem based on etcd."""
from . import __version__

import os
import sys
import stat
import etcd
import errno
import logging
import argparse
import urlparse
import posixpath
from boltons.funcutils import wraps
from fuse import FUSE, Operations, LoggingMixIn, FuseOSError

log = logging.getLogger(__name__)
fuselog = logging.getLogger("fuse.log-mixin")

DESCRIPTION = "Filesystem based on etcd"
LOG_FORMAT = ("%(asctime)-15s etcdfs pid=%(process)d "
              "%(module)s:%(lineno)s [%(levelname)s] %(message)s")

# Mapping of etcd error code to linux errno
ETCD_CODE_TO_ERRNO = {
    # EtcdKeyNotFound
    100: errno.ENOENT,
    # EtcdCompareFailed
    101: errno.EBADFD,
    # EtcdNotFile
    102: errno.EISDIR,
    # EtcdNotDir
    104: errno.ENOTDIR,
    # EtcdAlreadyExist
    105: errno.EEXIST,
    # EtcdRootReadOnly
    107: errno.EACCES,
    # EtcdDirNotEmpty
    108: errno.ENOTEMPTY,
    # EtcdInsufficentpermissions,
    110: errno.EPERM,
}


def handle_etcd_errors(func):
    """Decorator to convert etcd errors to FUSE errors."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except etcd.EtcdException as e:
            payload = getattr(e, "payload", {})
            error_code = payload.get("errorCode", None)
            if error_code:
                _errno = ETCD_CODE_TO_ERRNO.get(error_code, errno.EINVAL)
                raise FuseOSError(_errno)
            else:
                raise FuseOSError(errno.EINVAL)
    return wrapper


class EtcdFSOperations(LoggingMixIn, Operations):
    """FUSE Operations for etcd filesystem."""

    def __init__(self, client, basedir, uid=None, gid=None, mode=0o600):
        self.client = client
        self.basedir = "/%s" % basedir.strip("/")
        self.uid = uid or os.getuid()
        self.gid = gid or os.getgid()
        self.mode = mode

    def etcd_node_to_stat(self, node):
        """Convert an etcd node to stat struct."""
        if node.dir:
            st_mode = (stat.S_IFDIR | stat.S_IXUSR | self.mode)
            st_size = 4096
        else:
            st_mode = (stat.S_IFREG | self.mode)
            st_size = len(node.value)

        return {"st_ino": node.createdIndex or 0,
                "st_mode": st_mode,
                "st_nlink": 1,
                "st_uid": self.uid,
                "st_gid": self.gid,
                "st_size": st_size,
                "st_mtime": float(node.modifiedIndex or 0),
                "st_atime": float(node.modifiedIndex or 0),
                "st_ctime": float(node.createdIndex or 0)}

    def chmod(self, path, mode):
        raise FuseOSError(errno.ENOTSUP)

    def chown(self, path, uid, gid):
        raise FuseOSError(errno.ENOTSUP)

    def create(self, path, mode, fi=None):
        key = self._path_to_key(path)
        self.client.write(key, value="", prevExist=False)
        return 0

    def destroy(self, path):
        return 0

    def flush(self, path, fh):
        return 0

    def fsync(self, path, datasync, fh):
        return 0

    def fsyncdir(self, path, datasync, fh):
        return 0

    @handle_etcd_errors
    def getattr(self, path, fh=None):
        key = self._path_to_key(path)
        res = self.client.read(key)
        return self.etcd_node_to_stat(res)

    def getxattr(self, path, name, position=0):
        raise FuseOSError(errno.ENOTSUP)

    def init(self, path):
        return

    def ioctl(self, path, cmd, arg, fip, flags, data):
        raise FuseOSError(errno.ENOTSUP)

    def link(self, target, source):
        raise FuseOSError(errno.ENOTSUP)

    def listxattr(self, path):
        return []

    @handle_etcd_errors
    def mkdir(self, path, mode):
        dirkey = self._path_to_key(path)
        self.client.write(dirkey, value=None, dir=True, prevExist=False)
        return 0

    def mknode(self, path, mode, dev):
        raise FuseOSError(errno.ENOTSUP)

    def open(self, path, flags):
        return 0

    def opendir(self, path):
        return 0

    @handle_etcd_errors
    def read(self, path, size, offset, fh):
        key = self._path_to_key(path)
        res = self.client.read(key)
        return res.value[offset:offset + size]

    @handle_etcd_errors
    def readdir(self, path, fh):
        dirkey = self._path_to_key(path)
        res = self.client.read(dirkey)
        self._ensure_dir(res)

        names = [".", ".."]
        for _node in res.children:
            if _node.key is None:
                continue
            key = _node.key.rstrip("/")
            if key == dirkey:
                continue
            key = _node.key.replace(dirkey, "", 1).lstrip("/")
            if not key:
                continue
            attrs = self.etcd_node_to_stat(_node)
            names.append((key, attrs, 0))

        return names

    def readlink(self, path):
        raise FuseOSError(errno.ENOTSUP)

    def release(self, path, fh):
        return 0

    def releasedir(self, path, fh):
        return 0

    def removexattr(self, path, name):
        raise FuseOSError(errno.ENOTSUP)

    def rename(self, old, new):
        raise FuseOSError(errno.ENOTSUP)

    @handle_etcd_errors
    def rmdir(self, path):
        key = self._path_to_key(path)
        self.client.delete(key, dir=True)
        return 0

    def setxattr(self, path, name, value, options, position=0):
        raise FuseOSError(errno.ENOTSUP)

    def statfs(self, path):
        return {}

    def symlink(self, target, source):
        raise FuseOSError(errno.ENOTSUP)

    def truncate(self, path, length, fh=None):
        key = self._path_to_key(path)
        res = self.client.read(key)
        value = res.value
        old_length = len(value)
        if old_length == length:
            return 0
        if old_length > length:
            new_value = value[0:length]
        else:
            new_value = value.ljust(length)
        self.client.write(key, value=new_value)
        return 0

    @handle_etcd_errors
    def unlink(self, path):
        key = self._path_to_key(path)
        self.client.delete(key)
        return 0

    def utimens(self, path, times=None):
        """Times is a (atime, mtime) tuple. If None use current time."""
        return 0

    @handle_etcd_errors
    def write(self, path, data, offset, fh):
        key = self._path_to_key(path)
        value = data

        # Handle updates
        if offset:
            try:
                res = self.client.read(key)
                self._ensure_key(res)
                old_value = res.value
                pre = old_value[0:offset].ljust(offset)
                post = old_value[offset + len(data):]
                value = pre + data + post
            except etcd.EtcdKeyNotFound:
                value = "" * offset + data

        self.client.write(key, value=value)
        return len(data)

    def _path_to_key(self, path):
        """Convert filesystem path to etcd key."""
        return posixpath.join(self.basedir, path.lstrip("/")).rstrip("/")

    def _key_to_path(self, key, dirkey=None):
        """Convert etcdkey to filesystem relative path."""
        dirkey = dirkey or self.basedir
        return key.replace(dirkey, "", 1).lstrip("/") or "/"

    def _ensure_dir(self, node):
        """Ensure that an etcd node is a directory."""
        if not node.dir:
            raise FuseOSError(errno.ENOTDIR)

    def _ensure_key(self, node):
        """Ensure that an etcd node is a not directory."""
        if node.dir:
            raise FuseOSError(errno.EISDIR)


def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("mountpoint", metavar="MOUNT_POINT",
                        help="Mount etcd filesystem at the point"
                             " %(metavar)s")
    parser.add_argument("-v", "--verbose", default=False,
                        action="store_true",
                        help="Increase logging verbosity")
    parser.add_argument("-d", "--debug", default=False,
                        action="store_true",
                        help="Set FUSE in debug mode")
    parser.add_argument("-f", "--foreground", default=False,
                        action="store_true",
                        help="Do not daemonize, stay in the foreground")
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

    if args.verbose:
        fuselog.addHandler(handler)
        fuselog.setLevel(lvl)

    log.info("Initialing etcdfs. Version: %s", __version__)

    # Check mountpoint
    mountpoint = args.mountpoint
    if not os.path.exists(mountpoint):
        log.error("Mount point '%s' does not exist", mountpoint)
        sys.exit(1)
    if not os.path.isdir(mountpoint):
        log.error("Mount point '%s' is not a directory", mountpoint)
        sys.exit(1)

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

    # Pass control to FUSE
    etcd_fs_ops = EtcdFSOperations(client, basedir)
    FUSE(etcd_fs_ops, args.mountpoint,
         foreground=args.foreground, debug=args.debug)

    log.info("Exiting")


if __name__ == "__main__":
    main()
