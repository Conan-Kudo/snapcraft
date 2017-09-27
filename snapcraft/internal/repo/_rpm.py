# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright (C) 2017 Neal Gompa <ngompa13@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import contextlib
import glob
import hashlib
import logging
import os
import shutil
import stat
import string
import subprocess
import sys
import urllib
import urllib.request

import dnf
import dnf.rpm
import rpm

import hawkey

# for CLI output
from dnf.cli.progress import MultiFileProgressMeter as DownloadProgress
from dnf.cli.output import CliTransactionDisplay as TransactionProgress


from xml.etree import ElementTree

import snapcraft
from snapcraft import file_utils
from snapcraft.internal import cache, repo, common
from snapcraft.internal.errors import SnapcraftEnvironmentError
from snapcraft.internal.indicators import is_dumb_terminal
from ._base import BaseRepo
from . import errors
from snapcraft.internal.common import get_os_release_info


logger = logging.getLogger(__name__)


_MAIN_YUM_CONFIG = \
    '''[main]
keepcache=1
debuglevel=2
reposdir=/dev/null
logdir=/var/log/snapcraft/dnf
retries=20
obsoletes=1
gpgcheck=1
assumeyes=1
install_weak_deps=0
tsflags=nodocs
metadata_expire=0
cachedir=/var/cache/snapcraft/dnf

'''

# From mock
_DEFAULT_REPOS_CENTOS = \
    '''[centos]
name=centos
mirrorlist=http://mirrorlist.centos.org/?release=$releasever&arch=$basearch&repo=os
fastestmirror=1
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-$releasever
gpgcheck=1
skip_if_unavailable=0

[updates]
name=updates
enabled=1
mirrorlist=http://mirrorlist.centos.org/?release=$releasever&arch=$basearch&repo=updates
fastestmirror=1
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-$releasever
gpgcheck=1
skip_if_unavailable=0

[epel]
name=epel
metalink=http://mirrors.fedoraproject.org/metalink?repo=epel-$releasever&arch=$basearch
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/epel/RPM-GPG-KEY-EPEL-$releasever
gpgcheck=1
skip_if_unavailable=0

[extras]
name=extras
mirrorlist=http://mirrorlist.centos.org/?release=$releasever&arch=$basearch&repo=extras
fastestmirror=1
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/centos/RPM-GPG-KEY-CentOS-$releasever
gpgcheck=1
skip_if_unavailable=0
'''

_DEFAULT_REPOS_FEDORA = \
    '''[fedora]
name=fedora
metalink=https://mirrors.fedoraproject.org/metalink?repo=fedora-$releasever&arch=$basearch
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/fedora/RPM-GPG-KEY-fedora-$releasever-primary
gpgcheck=1
skip_if_unavailable=0

[updates]
name=updates
metalink=https://mirrors.fedoraproject.org/metalink?repo=updates-released-f$releasever&arch=$basearch
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/fedora/RPM-GPG-KEY-fedora-$releasever-primary
gpgcheck=1
skip_if_unavailable=0
'''

_DEFAULT_REPOS_MAGEIA = \
    '''[mageia]
name=mageia
mirrorlist=https://www.mageia.org/mirrorlist/?release=$releasever&arch=${distarch}&section=core&repo=release
fastestmirror=1
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/mageia/RPM-GPG-KEY-Mageia
gpgcheck=1
skip_if_unavailable=0

[updates]
name=updates
mirrorlist=https://www.mageia.org/mirrorlist/?release=$releasever&arch=${distarch}&section=core&repo=updates
fastestmirror=1
failovermethod=priority
gpgkey=file:///usr/share/distribution-gpg-keys/mageia/RPM-GPG-KEY-Mageia
gpgcheck=1
skip_if_unavailable=0
'''

_DEFAULT_REPOS_OPENSUSE_LEAP = \
    '''[opensuse-leap-oss]
name=opensuse-leap-oss
metalink=http://download.opensuse.org/distribution/leap/$releasever/repo/oss/suse/repodata/repomd.xml.metalink
failovermethod=priority
gpgkey=http://download.opensuse.org/distribution/leap/$releasever/repo/oss/suse/repodata/repomd.xml.key
gpgcheck=1
repo_gpgcheck=1
skip_if_unavailable=0

[updates-oss]
name=updates-oss
metalink=http://download.opensuse.org/update/leap/$releasever/oss/repodata/repomd.xml.metalink
failovermethod=priority
gpgkey=http://download.opensuse.org/update/leap/$releasever/oss/repodata/repomd.xml.key
gpgcheck=1
repo_gpgcheck=1
skip_if_unavailable=0
'''

_library_list = dict()


class RPM(BaseRepo):

    @classmethod
    def get_package_libraries(cls, package_name):
        raise SnapcraftEnvironmentError('dpkg -L {} | grep lib'.format(package_name))


    @classmethod
    def install_build_packages(cls, package_names):
        raise SnapcraftEnvironmentError("I ain't got no clue what to do with {}".format(package_names))

    @classmethod
    def get_packages_for_source_type(cls, source_type):
        if source_type == 'bzr':
            packages = {'bzr'}
        elif source_type == 'git':
            packages = {'git'}
        elif source_type == 'tar':
            packages = {'tar'}
        elif source_type == 'hg' or source_type == 'mercurial':
            packages = {'mercurial'}
        elif source_type == 'subversion' or source_type == 'svn':
            packages = {'subversion'}
        else:
            packages = set()
        raise SnapcraftEnvironmentError('Which package for {}?'.format(source_type))
        return packages

    @classmethod
    def install_build_packages(cls, package_names):
        # install packages
        # return installed packages in the form [foo=version]
        raise SnapcraftEnvironmentError('How ever would I install {}?'.format(package_names))

    @classmethod
    def build_package_is_valid(cls, package_name):
        raise SnapcraftEnvironmentError('return True if {} in cache'.format(package_names))

    @classmethod
    def is_package_installed(cls, package_name):
        raise SnapcraftEnvironmentError('return True if {} installed'.format(package_names))

    @classmethod
    def get_installed_packages(cls):
        raise SnapcraftEnvironmentError('return list of the form [foo=version]')

    def __init__(self, rootdir, sources=None, project_options=None):
        super().__init__(rootdir)
        self._downloaddir = os.path.join(rootdir, 'download')

        if not project_options:
            project_options = snapcraft.ProjectOptions()

    def is_valid(self, package_name):
        raise SnapcraftEnvironmentError('RPM.is_valid')

    def get(self, package_names):
        raise SnapcraftEnvironmentError('RPM.get')

    def unpack(self, unpackdir):
        raise SnapcraftEnvironmentError('RPM.unpack')

    # distro = get_os_release_info()['ID']
