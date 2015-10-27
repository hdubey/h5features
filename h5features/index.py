# Copyright 2014-2015 Thomas Schatz, Mathieu Bernard, Roland Thiolliere
#
# This file is part of h5features.
#
# h5features is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# h5features is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with h5features.  If not, see <http://www.gnu.org/licenses/>.
"""Provides the Index class to the h5features module."""

import numpy as np
from .version import is_supported_version
from .dataset.dataset import _nb_per_chunk

def init_index(version):
    """Initializes an h5features index according to a file *version*."""
    if not is_supported_version(version):
        raise IOError('version {} is not supported'.format(version))

    if version == '0.1':
        index_class = IndexV0_1()
    elif version == '1.0':
        index_class = IndexV1_0()
    else:
        index_class = Index()

    return index_class


class Index(object):
    """Index class for version 1.1 (current version)"""
    def __init__(self, name='index'):
        self.name = name

    def create_dataset(self, group, chunk_size):
        """Create an empty index dataset in the given group."""
        dtype=np.int64
        chunks = (_nb_per_chunk(np.dtype(dtype).itemsize, 1, chunk_size),)
        group.create_dataset(self.name, (0,), dtype=dtype,
                             chunks=chunks, maxshape=(None,))

    def write(self, group, items, features):
        """Write the index to the given HDF5 group."""
        nitm = group[items.name].shape[0]
        last_index = group[self.name][-1] if nitm > 0 else -1
        index = last_index + np.cumsum([x.shape[0] for x in features.data])

        nidx = group[self.name].shape[0]
        # in case we append to the end of an existing item
        if items.continue_last_item(group):
            nidx -= 1

        group[self.name].resize((nidx + index.shape[0],))
        group[self.name][nidx:] = index

    def read(self, group):
        """Read and return a stored index in an HDF5 group."""
        items = list(group['items'][...])
        index = {'items': items,
                 'index': group['index'][...],
                 'times': group['times'][...],
                 'format': group.attrs['format']}

        # index contains the index of the end of each file
        if index['format'] == 'sparse':
            index['dim'] = g.attrs['dim']
            index['frames'] = g['frames'][...]

        return index

class IndexV1_0(Index):
    """Index class for version 1.0"""
    def __init__(self, name='file_index'):
        Index.__init__(self, name)

    def read(self, group):
        """Read and return a stored index in an HDF5 group."""
        items = list(group['files'][...])
        index = {'items': items,
                 'index': group['file_index'][...],
                 'times': group['times'][...],
                 'format': group.attrs['format']}

        # index contains the index of the end of each file
        if index['format'] == 'sparse':
            index['dim'] = g.attrs['dim']
            index['frames'] = g['frames'][...]
        return index


class IndexV0_1(IndexV1_0):
    """TODO"""
    def read(self, group):
        files = ''.join([unichr(int(c)) for c in group['files'][...]]).replace(
            '/-', '/').split('/\\')  # parse unicode to strings
        # file_index contains the index of the end of each file:
        index = {'files': files, 'index': np.int64(group['index'][...]),
                 'times': group['times'][...], 'format': group.attrs['format']}
        if index['format'] == 'sparse':
            index['dim'] = group.attrs['dim']  # TODO type ?
            index['frames'] = group['lines'][...]  # TODO type ?
        return index
