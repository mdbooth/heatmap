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

import collections
from itertools import ifilter
import re
import sys

import gerrit

Field = collections.namedtuple('Field', ['path', 'truncate'])

QUERY = ['project:openstack/nova', 'branch:master', 'is:open']
OPTS = ['current-patch-set', 'dependencies']
FIELDS = [Field('owner/username', 0), Field('subject', 70), Field('url', 0)]
INDENT = 1

FIELDS = map(lambda x: x._replace(path=x.path.split('/')), FIELDS)

dirs = None
if len(sys.argv) > 1:
    dirs = re.compile('|'.join(re.escape(dir) + r'(?:/|$)'
                               for dir in sys.argv[1:]))
    OPTS.append('files')

def dirs_match(change):
    for file in change['currentPatchSet']['files']:
        path = file['file']
        if path == '/COMMIT_MSG':
            continue
        if dirs.match(path):
            return True
    return False

changes = gerrit.query(QUERY, OPTS)
if dirs is not None:
    changes = ifilter(dirs_match, changes)

max_width = [0] * len(FIELDS)
all_nodes = {}
for change in changes:
    id = change['id']
    node = {
        'id': id,
        'time': change['lastUpdated'],
        'children': []
    }
    all_nodes[id] = node

    fields = []
    for i in range(0, len(FIELDS)):
        val = change
        field = FIELDS[i]
        for j in field.path:
            val = val[j]
        if field.truncate > 0 and len(val) > field.truncate:
            val = val[0:field.truncate]
        fields.append(val)
        if len(val) > max_width[i]:
            max_width[i] = len(val)
    node['fields'] = fields

    if 'dependsOn' in change:
        node['depends'] = change['dependsOn'][0]['id']

top = []
for node in all_nodes.values():
    depends = node.get('depends')
    if depends is not None and depends in all_nodes:
        parent = all_nodes[depends]
        parent['children'].append(node)
    else:
        top.append(node)

def max_width0(nodes, depth=0):
    for node in nodes:
        width0 = depth * INDENT + len(node['fields'][0])
        if width0 > max_width[0]:
            max_width[0] = width0
        max_width0(node['children'], depth + 1)
max_width0(top)

format_str = '{}' + '{:{}} ' * (len(FIELDS) - 1) + '{:{}}'
def print_nodes(nodes, depth=0):
    for node in sorted(nodes, key=lambda x: x['time']):
        vals = ([' ' * INDENT * depth,
                 node['fields'][0], max_width[0] - INDENT * depth] +
                [x for l in zip(node['fields'][1:], max_width[1:]) for x in l])
        print format_str.format(*vals)
        print_nodes(node['children'], depth + 1)

print_nodes(top)
