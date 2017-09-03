# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright (C) 2017 Canonical Ltd
# Copyright (C) 2017 Neal Gompa
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

import logging

from snapcraft.internal.os_release import OsRelease

logger = logging.getLogger(__name__)

_DEB_BASED_PLATFORM = [
    'ubuntu',
    'debian',
    'elementary OS',
    'elementary',
    'neon',
]

_RPM_BASED_PLATFORM = [
    'centos',
    'fedora',
    'mageia',
    'opensuse',
    'rhel',
    'suse',
]


def _is_deb_based(distro=None):
    if not distro:
        distro = OsRelease().id()
    return distro in _DEB_BASED_PLATFORM


def _is_rpm_based(distro=None):
    if not distro:
        distro = get_os_release_info()['ID']
    return distro in _RPM_BASED_PLATFORM


def _get_repo_for_platform():
    distro = OsRelease().id()
    if _is_deb_based(distro):
        from ._deb import Ubuntu
        return Ubuntu
    else:
        from ._base import DummyRepo
        return DummyRepo
