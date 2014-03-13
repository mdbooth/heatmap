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

import json
import subprocess

GERRIT_HOST = 'review.openstack.org'
GERRIT_PORT = 29418

def query(query, options={}, host=GERRIT_HOST, port=GERRIT_PORT, limit=0):
    cmdline = ['ssh', '-p', str(port), str(host),
               'gerrit', 'query', '--format=JSON']

    for opt, val in options.iteritems():
        if opt == 'format':
            raise ValueError('Setting format to anything other than JSON is '
                             'not supported')
        if val == True:
            cmdline.append('--{opt}'.format(opt=opt))
        else:
            cmdline.append('--{opt}={val}'.format(opt=opt, val=val))

    cmdline.append('--')
    cmdline.extend(query)

    rows = 0
    sortkey = None
    while True:
        if sortkey is None:
            response = subprocess.check_output(cmdline)
        else:
            response = subprocess.check_output(cmdline +
                ['resume_sortkey:{key}'.format(key=sortkey)])

        for line in response.splitlines():
            result = json.loads(line)
            if result.get('type') == 'stats':
                if result.get('rowCount') == 0:
                    return
            else:
                sortkey = result['sortKey']
                rows += 1

                yield result

                if rows == limit:
                    return
