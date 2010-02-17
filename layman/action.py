#!/usr/bin/python
# -*- coding: utf-8 -*-
#################################################################################
# LAYMAN ACTIONS
#################################################################################
# File:       action.py
#
#             Handles layman actions.
#
# Copyright:
#             (c) 2005 - 2008 Gunnar Wrobel
#             Distributed under the terms of the GNU General Public License v2
#
# Author(s):
#             Gunnar Wrobel <wrobel@gentoo.org>
#
''' Provides the different actions that can be performed by layman.'''

__version__ = "$Id: action.py 312 2007-04-09 19:45:49Z wrobel $"

#===============================================================================
#
# Dependencies
#
#-------------------------------------------------------------------------------

import os, sys

from   layman.db                import DB, RemoteDB, UnknownOverlayException
from   layman.utils             import path, delete_empty_directory
from   layman.debug             import OUT

#===============================================================================
#
# Class Fetch
#
#-------------------------------------------------------------------------------

class Fetch:
    ''' Fetches the overlay listing.

    >>> import os
    >>> here = os.path.dirname(os.path.realpath(__file__))
    >>> cache = os.tmpnam()
    >>> config = {'overlays' :
    ...           'file://' + here + '/tests/testfiles/global-overlays.xml',
    ...           'cache' : cache,
    ...           'nocheck'    : True,
    ...           'proxy' : None,
    ...           'quietness':3,
    ...           'svn_command':'/usr/bin/svn',
    ...           'rsync_command':'/usr/bin/rsync'}
    >>> a = Fetch(config)
    >>> a.run()
    0
    >>> b = open(a.db.path(config['overlays']))
    >>> b.readlines()[24]
    '      A collection of ebuilds from Gunnar Wrobel [wrobel@gentoo.org].\\n'

    >>> b.close()
    >>> os.unlink(a.db.path(config['overlays']))

    >>> a.db.overlays.keys()
    [u'wrobel', u'wrobel-stable']
    '''

    def __init__(self, config):
        self.db = RemoteDB(config)

    def run(self):
        '''Fetch the overlay listing.'''
        try:
            self.db.cache()
        except Exception, error:
            OUT.die('Failed to fetch overlay list!\nError was: '
                    + str(error))

        return 0

#===============================================================================
#
# Class Sync
#
#-------------------------------------------------------------------------------

class Sync:
    ''' Syncs the selected overlays.'''

    def __init__(self, config):

        self.db = DB(config)

        self.rdb = RemoteDB(config)

        self.quiet = int(config['quietness']) < 3

        self.selection = config['sync']

        if config['sync_all'] or 'ALL' in self.selection:
            self.selection = self.db.overlays.keys()

        enc = sys.getfilesystemencoding()
        if enc:
            self.selection = [i.decode(enc) for i in self.selection]

    def run(self):
        '''Synchronize the overlays.'''

        OUT.debug('Updating selected overlays', 6)

        fatals = []
        warnings = []
        success  = []
        for i in self.selection:
            try:
                odb = self.db.select(i)
            except UnknownOverlayException, error:
                fatals.append(str(error))
                continue

            try:
                ordb = self.rdb.select(i)
            except UnknownOverlayException:
                warnings.append(\
                    'Overlay "%s" could not be found in the remote lists.\n'
                    'Please check if it has been renamed and re-add if necessary.' % i)
            else:
                current_src = odb.sources[0].src
                available_srcs = set(e.src for e in ordb.sources)
                if ordb and odb and not current_src in available_srcs:
                    if len(available_srcs) == 1:
                        plural = ''
                        candidates = '  %s' % tuple(available_srcs)[0]
                    else:
                        plural = 's'
                        candidates = '\n'.join(('  %d. %s' % (i + 1, v)) for i, v in enumerate(available_srcs))

                    warnings.append(
                        'The source of the overlay "%(repo_name)s" seems to have changed.\n'
                        'You currently sync from\n'
                        '\n'
                        '  %(current_src)s\n'
                        '\n'
                        'while the remote lists report\n'
                        '\n'
                        '%(candidates)s\n'
                        '\n'
                        'as correct location%(plural)s.\n'
                        'Please consider removing and re-adding the overlay.' % {
                            'repo_name':i,
                            'current_src':current_src,
                            'candidates':candidates,
                            'plural':plural,
                            })

            try:
                self.db.sync(i, self.quiet)
                success.append('Successfully synchronized overlay "' + i + '".')
            except Exception, error:
                fatals.append(
                    'Failed to sync overlay "' + i + '".\nError was: '
                    + str(error))

        if success:
            OUT.info('\nSuccess:\n------\n', 3)
            for i in success:
                OUT.info(i, 3)
                
        if warnings:
            OUT.warn('\nWarnings:\n------\n', 2)
            for i in warnings:
                OUT.warn(i + '\n', 2)

        if fatals:
            OUT.error('\nErrors:\n------\n')
            for i in fatals:
                OUT.error(i + '\n')
            return 1

        return 0

#===============================================================================
#
# Class Add
#
#-------------------------------------------------------------------------------

class Add:
    ''' Adds the selected overlays.'''

    def __init__(self, config):

        self.config = config

        self.db = DB(config)

        self.rdb = RemoteDB(config)

        self.quiet = int(config['quietness']) < 3

        self.selection = config['add']

        enc = sys.getfilesystemencoding()
        if enc:
            self.selection = [i.decode(enc) for i in self.selection]

        if 'ALL' in self.selection:
            self.selection = self.rdb.overlays.keys()

    def run(self):
        '''Add the overlay.'''

        OUT.debug('Adding selected overlays', 6)

        result = 0

        for i in self.selection:
            try:
                overlay = self.rdb.select(i)
            except UnknownOverlayException, error:
                OUT.warn(str(error), 2)
                result = 1
            else:
                OUT.debug('Selected overlay', 7)
                try:
                    self.db.add(overlay, self.quiet)
                    OUT.info('Successfully added overlay "' + i + '".', 2)
                except Exception, error:
                    OUT.warn('Failed to add overlay "' + i + '".\nError was: '
                             + str(error), 2)
                    result = 1

        return result

#===============================================================================
#
# Class Delete
#
#-------------------------------------------------------------------------------

class Delete:
    ''' Deletes the selected overlays.'''

    def __init__(self, config):

        self.db = DB(config)

        self.selection = config['delete']

        enc = sys.getfilesystemencoding()
        if enc:
            self.selection = [i.decode(enc) for i in self.selection]

        if 'ALL' in self.selection:
            self.selection = self.db.overlays.keys()

    def run(self):
        '''Delete the overlay.'''

        OUT.debug('Deleting selected overlays', 6)

        result = 0

        for i in self.selection:
            try:
                overlay = self.db.select(i)
            except UnknownOverlayException, error:
                OUT.warn(str(error), 2)

                mdir = path([self.db.config['storage'], i])
                delete_empty_directory(mdir)

                result = 1
            else:
                OUT.debug('Selected overlay', 7)
                try:
                    self.db.delete(overlay)
                    OUT.info('Successfully deleted overlay "' + i + '".', 2)
                except Exception, error:
                    OUT.warn('Failed to delete overlay "' + i + '".\nError was: '
                             + str(error), 2)
                    result = 1

        return result

#===============================================================================
#
# Class Info
#
#-------------------------------------------------------------------------------

class Info:
    ''' Print information about the specified overlays.

    >>> import os
    >>> here = os.path.dirname(os.path.realpath(__file__))
    >>> cache = os.tmpnam()
    >>> config = {'overlays' :
    ...           'file://' + here + '/tests/testfiles/global-overlays.xml',
    ...           'cache'  : cache,
    ...           'proxy'  : None,
    ...           'info'   : ['wrobel'],
    ...           'nocheck'    : False,
    ...           'verbose': False,
    ...           'quietness':3,
    ...           'svn_command':'/usr/bin/svn',
    ...           'rsync_command':'/usr/bin/rsync'}
    >>> a = Info(config)
    >>> a.rdb.cache()
    >>> OUT.color_off()
    >>> a.run()
    * wrobel
    * ~~~~~~
    * Source  : https://overlays.gentoo.org/svn/dev/wrobel
    * Contact : nobody@gentoo.org
    * Type    : Subversion; Priority: 10
    * Quality : experimental
    * 
    * Description:
    *   Test
    * 
    0
    '''

    def __init__(self, config):

        OUT.debug('Creating RemoteDB handler', 6)

        self.rdb    = RemoteDB(config)
        self.config = config

        self.selection = config['info']

        enc = sys.getfilesystemencoding()
        if enc:
            self.selection = [i.decode(enc) for i in self.selection]

        if 'ALL' in self.selection:
            self.selection = self.rdb.overlays.keys()

    def run(self):
        ''' Print information about the selected overlays.'''

        result = 0

        for i in self.selection:
            try:
                overlay = self.rdb.select(i)
            except UnknownOverlayException, error:
                OUT.warn(str(error), 2)
                result = 1
            else:
                # Is the overlay supported?
                OUT.info(overlay.__str__(), 1)
                if not overlay.is_official():
                    OUT.warn('*** This is no official gentoo overlay ***\n', 1)
                if not overlay.is_supported():
                    OUT.error('*** You are lacking the necessary tools to install t'
                              'his overlay ***\n')

        return result

#===============================================================================
#
# Class List
#
#-------------------------------------------------------------------------------

class List:
    ''' Lists the available overlays.

    >>> import os
    >>> here = os.path.dirname(os.path.realpath(__file__))
    >>> cache = os.tmpnam()
    >>> config = {'overlays' :
    ...           'file://' + here + '/tests/testfiles/global-overlays.xml',
    ...           'cache'  : cache,
    ...           'proxy'  : None,
    ...           'nocheck'    : False,
    ...           'verbose': False,
    ...           'quietness':3,
    ...           'width':80,
    ...           'svn_command':'/usr/bin/svn',
    ...           'rsync_command':'/usr/bin/rsync'}
    >>> a = List(config)
    >>> a.rdb.cache()
    >>> OUT.color_off()
    >>> a.run()
    * wrobel                    [Subversion] (https://o.g.o/svn/dev/wrobel         )
    0
    >>> a.config['verbose'] = True
    >>> a.run()
    * wrobel
    * ~~~~~~
    * Source  : https://overlays.gentoo.org/svn/dev/wrobel
    * Contact : nobody@gentoo.org
    * Type    : Subversion; Priority: 10
    * Quality : experimental
    * 
    * Description:
    *   Test
    * 
    * *** This is no official gentoo overlay ***
    * 
    * wrobel-stable
    * ~~~~~~~~~~~~~
    * Source  : rsync://gunnarwrobel.de/wrobel-stable
    * Contact : nobody@gentoo.org
    * Type    : Rsync; Priority: 50
    * Quality : experimental
    * 
    * Description:
    *   A collection of ebuilds from Gunnar Wrobel [wrobel@gentoo.org].
    * 
    0
    '''

    def __init__(self, config):

        OUT.debug('Creating RemoteDB handler', 6)

        self.rdb    = RemoteDB(config)
        self.config = config

    def run(self):
        ''' List the available overlays.'''

        for i in self.rdb.list(self.config['verbose'], self.config['width']):
            # Is the overlay supported?
            if i[1]:
                # Is this an official overlay?
                if i[2]:
                    OUT.info(i[0], 1)
                # Unofficial overlays will only be listed if we are not
                # checking or listing verbose
                elif self.config['nocheck'] or self.config['verbose']:
                    # Give a reason why this is marked yellow if it is a verbose
                    # listing
                    if self.config['verbose']:
                        OUT.warn('*** This is no official gentoo overlay ***\n', 1)
                    OUT.warn(i[0], 1)
            # Unsupported overlays will only be listed if we are not checking
            # or listing verbose
            elif self.config['nocheck'] or self.config['verbose']:
                # Give a reason why this is marked red if it is a verbose
                # listing
                if self.config['verbose']:
                    OUT.error('*** You are lacking the necessary tools to insta'
                              'll this overlay ***\n')
                OUT.error(i[0])

        return 0

#===============================================================================
#
# Class ListLocal
#
#-------------------------------------------------------------------------------

class ListLocal:
    ''' Lists the local overlays.'''

    def __init__(self, config):
        self.db = DB(config)
        self.config = config

    def run(self):
        '''List the overlays.'''

        for i in self.db.list(self.config['verbose']):

            OUT.debug('Printing local overlay.', 8)

            # Is the overlay supported?
            if i[1]:
                # Is this an official overlay?
                if i[2]:
                    OUT.info(i[0], 1)
                # Unofficial overlays will only be listed if we are not
                # checking or listing verbose
                else:
                    # Give a reason why this is marked yellow if it is a verbose
                    # listing
                    if self.config['verbose']:
                        OUT.warn('*** This is no official gentoo overlay ***\n', 1)
                    OUT.warn(i[0], 1)
            # Unsupported overlays will only be listed if we are not checking
            # or listing verbose
            else:
                # Give a reason why this is marked red if it is a verbose
                # listing
                if self.config['verbose']:
                    OUT.error('*** You are lacking the necessary tools to insta'
                              'll this overlay ***\n')
                OUT.error(i[0])

        return 0

#===============================================================================
#
# Class Actions
#
#-------------------------------------------------------------------------------

class Actions:
    '''Dispatches to the actions the user selected. '''

    # Given in order of precedence
    actions = [('fetch',      Fetch),
               ('add',        Add),
               ('sync',       Sync),
               ('info',       Info),
               ('sync_all',   Sync),
               ('delete',     Delete),
               ('list',       List),
               ('list_local', ListLocal),]

    def __init__(self, config):

        # Make fetching the overlay list a default action
        if not 'nofetch' in config.keys():
            # Actions that implicitely call the fetch operation before
            fetch_actions = ['sync', 'sync_all', 'list']
            for i in fetch_actions:
                if i in config.keys():
                    # Implicitely call fetch, break loop
                    Fetch(config).run()
                    break

        result = 0

        # Set the umask
        umask = config['umask']
        try:
            new_umask = int(umask, 8)
            old_umask = os.umask(new_umask)
        except Exception, error:
            OUT.die('Failed setting to umask "' + umask + '"!\nError was: ' 
                    + str(error))

        for i in self.actions:

            OUT.debug('Checking for action', 7)

            if i[0] in config.keys():
                result += i[1](config).run()

        # Reset umask
        os.umask(old_umask)

        if not result:
            sys.exit(0)
        else:
            sys.exit(1)
            
#===============================================================================
#
# Testing
#
#-------------------------------------------------------------------------------

if __name__ == '__main__':
    import doctest, sys

    # Ignore warnings here. We are just testing
    from warnings     import filterwarnings, resetwarnings
    filterwarnings('ignore')

    doctest.testmod(sys.modules[__name__])

    resetwarnings()
