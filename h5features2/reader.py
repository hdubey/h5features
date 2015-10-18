"""Provides the Reader class to the h5features2 module."""

import h5py
import numpy as np

from h5features2.index import Index, LegacyIndex

class Reader(object):
    """This class enables reading from h5features files.

    .. note:: Also note that the functions are not concurrent nor
    thread-safe (because the HDF5 library is not concurrent and not
    always thread-safe), moreover, they aren't even atomic for
    independent process (because there are several independent calls
    to the file system), so that thread-safety and atomicity of
    operations should be enforced externally when necessary.

    """
    # TODO Check the group contains a valid h5features structure.
    def __init__(self, filename, groupname, index=None):
        """Initializes a h5features reader to read a group in a HDF5 file.

        This constructor open an HDF5 file for reading and load its index.

        Parameters
        ----------

        filename : filename --- hdf5 file potentially serving as a
        container for many small files.

        groupname : str --- h5 group to read the data from.

        index : int, optional -- for faster access.

        Raise
        -----

        IOError if `filename` is not an existing HDF5 file.
        IOError if `groupname` is not a valid group in `filename`.

        """

        # check filename
        if not h5py.is_hdf5(filename):
            raise IOError('{} is not a HDF5 file'.format(filename))
        self.filename = filename

        # open the HDF5 file for reading
        self.h5file = h5py.File(self.filename, 'r')

        # access to the requested group
        if not groupname in self.h5file:
            raise IOError('{} is not a valid group in {}'
                          .format(groupname, self.filename))
        self.groupname = groupname
        self.group = self.h5file[groupname]

        # read the index from group if not provided
        if index is None:
            self.legacy = not 'version' in self.group.attrs
            self.index = (LegacyIndex().read(self.group) if self.legacy
                          else Index().read(self.group))
        else:
            # TODO not really safe to fetch a legacy attribute here...
            self.legacy = index['legacy']
            self.index = index

    def read(self, from_item=None, to_item=None,
             from_time=None, to_time=None):
        """Retrieve requested datasets coordinates from the h5features index.

        Parameters
        ----------

        from_item : str, optional --- Read the data starting from this
        item. (defaults to the first stored item)

        to_item : str, optional --- Read the data until reaching the
        item. (defaults to from_item if it was specified and to the
        last stored item otherwise)

        from_time : float, optional --- (defaults to the beginning
        time in from_item) the specified times are included in the
        output

        to_time : float, optional --- (defaults to the ending time in
        to_item) the specified times are included in the output

        """
        items_group = self.index['items']
        if to_item is None:
            to_item = items_group[-1] if from_item is None else from_item
        if from_item is None:
            from_item = items_group[0]

        item1 = self._get_item(items_group, from_item)
        item2 = self._get_item(items_group, to_item)
        if not item2 >= item1:
            raise IOError('from_item {} is located after to_item {} in file {}'
                          .format(from_item, to_item, self.filename))

        # index associated with the begin/end of from/to_item :
        index_group = self.index['index']
        item1_start = 0 if item1 == 0 else index_group[item1 - 1] + 1
        item2_start = 0 if item2 == 0 else index_group[item2 - 1] + 1
        item1_end = index_group[item1]
        item2_end = index_group[item2]

        if from_time is None:
            i1 = item1_start
        else:
            # the end is included...
            times = index_group['times'][item1_start:item1_end + 1]
            try:
                # smallest time larger or equal to from_time
                i1 = item1_start + np.where(times >= from_time)[0][0]
            except IndexError:
                raise IOError('from_time {} is larger than the biggest time in '
                              'from_item {}'.format(from_time, from_item))

        if to_time is None:
            i2 = item2_end
        else:
            # the end is included...
            times = index_group['times'][item2_start:item2_end + 1]
            try:
                # largest time smaller or equal to to_time
                i2 = item2_start + np.where(times <= to_time)[0][-1]
            except IndexError:
                raise Exception('to_time {} is smaller than the smallest time '
                                'in to_item {}'.format(to_time, to_item))

        # Step 2: access actual data
        features_group = self.group['features']
        if self.index['format'] == 'dense':
            if self.legacy:
                features = features_group[:, i1:i2 + 1].T  # i2 included
            else:
                features = features_group[i1:i2 + 1, :]  # i2 included
            times = self.group['times'][i1:i2 + 1]
        else:
            # FIXME implement this. will be different for v1.0 and legacy
            raise IOError('reading sparse features not yet implemented')

        if item2 > item1:
            file_ends = index_group[item1:item2] - item1_start
            # FIXME change axis from 1 to 0, but need to check that this doesn't
            # break compatibility with matlab generated files
            features = np.split(features, file_ends + 1, axis=0)
            times = np.split(times, file_ends + 1)
        else:
            features = [features]
            times = [times]

        items = items_group[item1:item2 + 1]
        return items, times, features


    def _get_item(self, group, element):
        """Look for the given element in the given group (a list)."""
        try:
            return group.index(element)
        except ValueError:
            raise IOError('No entry for item {} in the group {} in {}'
                          .format(element, self.filename, self.groupname))
