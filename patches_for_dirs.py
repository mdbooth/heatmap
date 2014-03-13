#!/usr/bin/python

# Copyright (C) 2014 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51 Franklin
# Street, Fifth Floor, Boston, MA 02110-1301  USA

import re
import sys

import gerrit

if len(sys.argv) == 1:
    print "No directories given"
    sys.exit(1)
search = re.compile('|'.join(re.escape(dir) + r'(?:/|$)'
                             for dir in sys.argv[1:]))

for change in gerrit.query(['project:openstack/nova', 'branch:master',
                           'is:open'],
                           {'current-patch-set': True, 'files': True}):
    for file in change['currentPatchSet']['files']:
        file = file['file']
        if file == '/COMMIT_MSG':
            continue
        if search.match(file):
            print "{subject}: {url}".format(subject=change['subject'],
                                            url=change['url'])
            break
