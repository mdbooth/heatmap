#!/usr/bin/python

# heatmap_to_dot - Generate dot graphs from heatmap output
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
import math
import re
import sys

root = json.load(open(sys.argv[1], 'r'))
pending = open(sys.argv[2], 'w')
merged = open(sys.argv[3], 'w')


def walk_nodes(f, acc):
    def _walk_node(node, _acc):
        children = node.get('children')
        if children is None:
            return _acc

        _acc = f(node, _acc)

        for child in children.values():
            _acc = _walk_node(child, _acc)

        return _acc

    return _walk_node(root, acc)


def get_nodeset(path):
    nodeset = [root]
    node = root
    for tok in path.split('/')[1::]:
        node = node['children'][tok]
        nodeset.append(node)

    return nodeset


def prune(path, expunge=True):
    nodeset = get_nodeset(path)

    node = nodeset[-1]
    parent = nodeset[-2]

    if expunge:
        stats = node['stats']
        merged = node['merged']
        for i in nodeset:
            for j in i['stats']:
                i['stats'][j] -= stats[j]
            for j in i['merged']:
                i['merged'][j] -= merged[j]

    del(parent['children'][node['name']])


def dot_name(node):
    return re.sub('[-/.]', '_', node['path'])


def nextrank(rank):
    prune_lines = root['stats']['lines'] * 2 / 100
    n = []
    for _, node in rank:
        for child in node['children'].values():
            descs = child.get('children')
            if descs is None:
                continue

            # Filter out small branches
            if child['stats']['lines'] < prune_lines:
                continue

            n.append((node, child))
    return n


root = get_nodeset('/nova')[-1]

# Big and irrelevant
prune('/locale')

# Represented elsewhere
prune('/tests')

# Path is too long, makes the graphs ugly
prune('/api/openstack/compute', False)


def gen_pending():
    def get_pending(node):
        stats = node['stats']

        if stats['lines'] == 0:
            return 0
        return float(stats['removed']) * 100 / float(stats['lines'])


    def format_pending(node, scale):
        stat = get_pending(node)
        stats = node['stats']
        if stats['removed'] == 0:
            age = 0
        else:
            age = stats['age_removed'] / stats['removed']
        return '{name}[label="{label}({pc}%)", width={width}]'.format(
                    name=dot_name(node), label=node['name'],
                    pc=int(stat), width=math.sqrt(stat / scale) * 5)


    def max_pending_f(node, _max):
        stat = get_pending(node)
        if stat > _max:
            return stat
        return _max

    max_pending = walk_nodes(max_pending_f, 0)

    print('digraph "Percentage of changed code" {', file=pending)
    print('  node[shape=circle, fixedsize=true];', file=pending)
    print('  overlap=scale;', file=pending)
    print(file=pending)
    print('  {};'.format(format_pending(root, max_pending)), file=pending)
    print('  {}[style=filled, fillcolor=lightgreen];'.format(dot_name(root)),
          file=pending)

    rank = nextrank([(None, root)])

    while len(rank) > 0:
        print(file=pending)
        print('  subgraph {', file=pending)
        for parent, child in rank:
            print('    {parent} -> {child};'.format(parent=dot_name(parent),
                                                    child=dot_name(child)),
                  file=pending)
            print('    {};'.format(format_pending(child, max_pending)),
                  file=pending)
        print('  }', file=pending)

        rank = nextrank(rank)

    print('}', file=pending)


def gen_merged():
    def get_merged(node):
        merged = node['merged']
        if merged['touched'] == 0:
            return 0
        return float(merged['age']) / float(merged['touched'])


    def format_merged(node, scale):
        age = get_merged(node)
        merged = node['merged']
        return '{name}[label="{label}({age}d)", width={width}]'.format(
                    name=dot_name(node), label=node['name'],
                    age=int(age/60/60/24),
                    width=math.sqrt(age / scale) * 3)


    def max_merged_f(node, _max):
        stat = get_merged(node)
        if stat > _max:
            return stat
        return _max

    max_merged = walk_nodes(max_merged_f, 0)

    print('digraph "Average Approval Time" {', file=merged)
    print('  node[shape=circle, fixedsize=true];', file=merged)
    print('  overlap=scale;', file=merged)
    print(file=merged)
    print('  {};'.format(format_merged(root, max_merged)), file=merged)
    print('  {}[style=filled, fillcolor=lightgreen];'.format(dot_name(root)),
          file=merged)

    rank = nextrank([(None, root)])

    while len(rank) > 0:
        print(file=merged)
        print('  subgraph {', file=merged)
        for parent, child in rank:
            print('    {parent} -> {child};'.format(parent=dot_name(parent),
                                                    child=dot_name(child)),
                  file=merged)
            print('    {};'.format(format_merged(child, max_merged)),
                  file=merged)
        print('  }', file=merged)

        rank = nextrank(rank)

    print('}', file=merged)


gen_pending()
gen_merged()

pending.close()
merged.close()
