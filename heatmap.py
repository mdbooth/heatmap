#!/usr/bin/python

# heatmap - a program to extract statistical information from gerrit and git
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

from __future__ import print_function

import json
import os
import re
import subprocess
import sys
import time

import gerrit

devnull = open('/dev/null', 'w')
def get_patch(ref, rev):
    try:
        return subprocess.check_output(['git', 'show', rev], stderr=devnull)
    except subprocess.CalledProcessError:
        pass

    subprocess.call(['git', 'fetch', 'gerrit', ref], stdout=sys.stderr)
    return subprocess.check_output(['git', 'show', rev])


def changes():
    return gerrit.query(['project:openstack/nova', 'branch:master',
                        '-status:workinprogress', '-status:abandoned'],
                        {'current-patch-set': True}, limit=1000)

class Node(object):
    def __init__(self, parent, name):
        self.name = name
        if parent is None:
            self.path = ''
        else:
            self.path = parent.path + '/' + name

        self.children = {}
        self.stats = {
            'touched': 0,
            'age': 0,
            'added': 0,
            'removed': 0,
            'age_added': 0,
            'age_removed': 0,
            'lines': 0
        }
        self.merged = {
            'touched': 0,
            'age': 0,
            'changed': 0,
            'age_changed': 0
        }


root = Node(None, '/')
def get_nodeset(diff_path, prune=1):
    def _get_child(parent, name):
        child = parent.children.get(name)
        if child is not None:
            return child

        child = Node(parent, name)
        parent.children[name] = child
        return child

    last = root
    nodeset = [root]
    for name in diff_path.split('/')[prune::]:
        last = _get_child(last, name)
        nodeset.append(last)
    return nodeset


def diff_files(diff):
    lines = iter(diff.splitlines())

    line = None
    while True:
        # Skip over leading metadata
        try:
            while True:
                line = lines.next()
                if len(line) > 0 and line[0:4] == '--- ':
                    break
        except StopIteration:
            return
        if line is None:
            return

        hunks = []

        path = line[4::].rstrip()
        # Skip the +++ line
        lines.next()

        while True:
            try:
                line = lines.next()
            except StopIteration:
                line = None

            if (line is None) or (len(line) > 0 and line[0:5] == 'diff '):
                yield (path, hunks)
                break

            hunks.append(line)


def hunks_count_churn(hunks):
    added = 0
    removed = 0

    lines = iter(hunks)
    try:
        line = lines.next()
    except StopIteration:
        return (added, removed)

    while True:
        m = re.match('@@ -\d*,?(\d+) \+\d*,?(\d+) @@', line)
        if m is None:
            print('\n'.join(hunks), file=sys.stderr)
            raise Exception(line)
        context_removed = int(m.group(1))
        context_added = int(m.group(2))
        while context_removed > 0 or context_added > 0:
            line = lines.next()
            if line[0] == ' ':
                context_removed -= 1
                context_added -= 1
            elif line[0] == '-':
                context_removed -= 1
                removed += 1
            elif line[0] == '+':
                context_added -= 1
                added += 1

        while True:
            try:
                line = lines.next()
            except StopIteration:
                return (added, removed)

            # Skip over '\ No newline'
            if line[0] != '\\':
                break


class NodeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Node):
            r = {'name': o.name, 'stats': o.stats, 'merged': o.merged}
            if o.path == '':
                r['path'] = '/'
            else:
                r['path'] = o.path
            if len(o.children) > 0:
                r['children'] = o.children
            return r
        else:
            return super(self, NodeEncoder).default(o)


for dirname, dirs, files in os.walk('.'):
    for f in files:
        path = dirname + '/' + f
        lines = len(open(path, 'r').read().splitlines())
        for node in get_nodeset(path):
            node.stats['lines'] += lines

now = int(time.time())
all_changes = list(changes())
total=len(all_changes)
for i in range(0, len(all_changes)):
    change = all_changes[i]
    print('*** {i}/{t}: {s}'.format(i=i+1, t=total, s=change['subject']),
          file=sys.stderr)

    status = change['status']
    patch = change['currentPatchSet']

    if status == 'NEW':
        age = now - patch['createdOn']
    elif status == 'MERGED':
        approved = None
        for approval in patch['approvals']:
            if approval['type'] == 'APRV':
                approved = int(approval['grantedOn'])
                break
        if approved is None:
            raise Exception('MERGED with no APRV: {}'.format(change))
        age = approved - patch['createdOn']
    else:
        raise Exception('Unexpected status: {status}'
                        .format(status=change['status']))

    touched = set([])

    diff = get_patch(patch['ref'], patch['revision'])
    for (path, hunks) in diff_files(diff):
        if path == '/dev/null':
            continue

        (patch_added, patch_removed) = hunks_count_churn(hunks)
        nodeset = get_nodeset(path)
        for node in nodeset:
            touched.add(node)

            if status == 'NEW':
                stats = node.stats
                stats['added'] += patch_added
                stats['removed'] += patch_removed
                stats['age_removed'] += patch_removed * age
                stats['age_added'] += patch_added * age
            elif status == 'MERGED':
                merged = node.merged
                merged['changed'] += patch_removed + patch_added
                merged['age_changed'] += (patch_removed + patch_added) * age

    for node in touched:
        if status == 'NEW':
            stats = node.stats
            stats['touched'] += 1
            stats['age'] += age
        elif status == 'MERGED':
            merged = node.merged
            merged['touched'] += 1
            merged['age'] += age

print(json.dumps(root, indent=4, cls=NodeEncoder))
