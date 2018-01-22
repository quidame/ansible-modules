#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Ansible module to manage debian package's files diversions.

(c) 2017, Yann Amar <quidame@poivron.org>

Ansible is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Ansible is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
"""

DOCUMENTATION = '''
---
module: dpkg_divert
short_description: Override a package's version of a file
description:
    - This module manages diversions of debian packages files using the
      I(dpkg-divert)(1) commandline tool.
version_added: "2.4"
author:
    - "quidame@poivron.org"
options:
    path:
        description:
            - The original and absolute path of the file to be diverted or
              undiverted.
        required: true
        default: null
    divert:
        description:
            - The location where the versions of file will be diverted.
            - Default is to add suffix B(.distrib) to the file path.
        required: false
        default: null
    remove:
        description:
            - Remove a diversion for file.
        required: false
        choices: [ "yes", "no" ]
        default: "no"
    rename:
        description:
            - Actually move the file aside (or back).
            - Operation is aborted (but module doesn't fail) in case the
              destination file already exists.
        required: false
        choices: [ "yes", "no" ]
        default: "no"
    package:
        description:
            - The name of the package whose copy of file is not diverted.
            - Operation is aborted in case the diversion already exists and
              belongs to another package.
            - If not specified, diversion is hold by 'LOCAL', that is not a
              package.
        required: false
        default: null
    force:
        description:
            - Force to divert file when diversion already exists and is hold
              by another C(package) or points to another C(divert). There is
              no need to use it for C(remove) action if C(divert) or C(package)
              are not used.
            - This doesn't override the rename's lock feature, i.e. it doesn't
              help to force C(rename), but only to force the diversion.
        required: false
        choices: [ "yes", "no" ]
        default: "no"
requirements: [ dpkg-divert ]
'''

EXAMPLES = '''
- name: divert /etc/screenrc to /etc/screenrc.distrib and keep file in place
  dpkg_divert: path=/etc/screenrc

- name: divert /etc/screenrc for package 'branding' (fake, used as a tag)
  dpkg_divert:
    path: /etc/screenrc
    package: branding

- name: remove the screenrc diversion only if belonging to 'branding'
  dpkg_divert:
    path: /etc/screenrc
    package: branding
    remove: yes

- name: divert and rename screenrc to screenrc.dpkg-divert, even if diversion is already set
  dpkg_divert:
    path: /etc/screenrc
    divert: /etc/screenrc.dpkg-divert
    rename: yes
    force: yes

- name: remove the screenrc diversion and maybe move the diverted file to its original place
  dpkg_divert:
    path: /etc/screenrc
    remove: yes
    rename: yes
'''

import re
import os.path
from ansible.module_utils.basic import *

def main():

    # Mimic the behaviour of the dpkg-divert(1) command: '--add' is implicit
    # when not using '--remove', '--rename' takes care to never overwrite
    # existing files, and options are intended to not conflict between them.

    # 'force' is an option of the module, not of the command, and implies to
    # run the command twice. Its purpose is to allow one to re-divert a file
    # with another target path or to 'give' it to another package, in one task.

    module = AnsibleModule(
        argument_spec = dict(
            package = dict(required=False),
            path    = dict(required=True,  type='path'),
            divert  = dict(required=False, type='path'),
            remove  = dict(required=False, type='bool', default=False),
            rename  = dict(required=False, type='bool', default=False),
            force   = dict(required=False, type='bool', default=False),
        ),
        supports_check_mode = True,
    )

    params  = module.params
    path    = params['path']
    divert  = params['divert']
    remove  = params['remove']
    rename  = params['rename']
    package = params['package']
    force   = params['force']

    DPKG_DIVERT = module.get_bin_path('dpkg-divert', required=True)
    # We need to parse the command's output, which is localized.
    # So we have to reset environment variable (LC_ALL).
    ENVIRONMENT = module.get_bin_path('env', required=True)

    # Start to build the commandline we'll have to run
    COMMANDLINE = [ENVIRONMENT, 'LC_ALL=C', DPKG_DIVERT, path]

    # Then add options as requested in the task:
    remove and COMMANDLINE.insert(3, '--remove')
    rename and COMMANDLINE.insert(3, '--rename')
    if divert:
        COMMANDLINE.insert(3, '--divert')
        COMMANDLINE.insert(4, divert)
    if package:
        COMMANDLINE.insert(3, '--package')
        COMMANDLINE.insert(4, package)

    # dpkg-divert has a useful --test option that we will use in check mode or
    # when needing to parse output before actually doing anything.
    TESTCOMMAND = list(COMMANDLINE)
    TESTCOMMAND.insert(3, '--test')
    if module.check_mode: COMMANDLINE = list(TESTCOMMAND)

    cmdline = ' '.join(COMMANDLINE)
    fortest = ' '.join(TESTCOMMAND)

    # `dpkg-divert --listpackage FILE` always returns 0, but not diverted files
    # provide no output.
    rc, listpackage, _ = module.run_command([DPKG_DIVERT, '--listpackage', path])
    rc, placeholder, _ = module.run_command(TESTCOMMAND)

    # There is probably no need to do more than that:
    if rc == 0 or not force or not listpackage:
        rc, stdout, stderr = module.run_command(COMMANDLINE, check_rc=True)
        if re.match('^(Leaving|No diversion)', stdout):
            module.exit_json(changed=False, stdout=stdout, stderr=stderr, cmd=cmdline)
        module.exit_json(changed=True, stdout=stdout, stderr=stderr, cmd=cmdline)

    # So, here we are: the test failed AND force is true AND a diversion exists
    # for the file.  Anyway, we have to remove it first (then stop or add a new
    # diversion for the same file), and without failure. Cases of failure are:
    # - The diversion does not belong to the same package (or LOCAL)
    # - The divert filename is not the same (e.g. path.distrib != path.divert)
    # So: force removal by stripping 'package' and 'divert' options:
    FORCEREMOVE = [ENVIRONMENT, 'LC_ALL=C', DPKG_DIVERT, '--remove', path]
    module.check_mode and FORCEREMOVE.insert(3, '--test')
    rename and FORCEREMOVE.insert(3, '--rename')
    forcerm = ' '.join(FORCEREMOVE)

    if remove:
        rc, stdout, stderr = module.run_command(FORCEREMOVE, check_rc=True)
        module.exit_json(changed=True, stdout=stdout, stderr=stderr, cmd=forcerm)

    # The situation is that we want to modify the settings (package or divert)
    # of an existing diversion. dpkg-divert does not handle this, and we have
    # to remove the diversion and set a new one. First, get state info:
    rc, truename, _ = module.run_command([DPKG_DIVERT, '--truename', path])
    # and go on
    rc, rmout, rmerr = module.run_command(FORCEREMOVE, check_rc=True)
    if module.check_mode:
        module.exit_json(changed=True, cmd=[forcerm, cmdline], msg=[rmout,
            "*** RUNNING IN CHECK MODE ***",
            "The next step can't be actually performed but is supposed to achieve the task."])

    old = truename.rstrip()
    if divert: new = divert
    else: new = '.'.join([path, 'distrib'])

    old_exists = os.path.isfile(old)
    new_exists = os.path.isfile(new)
    if rename and old_exists and not new_exists: os.rename(old, new)

    rc, stdout, stderr = module.run_command(COMMANDLINE)
    rc == 0 and module.exit_json(changed=True, stdout=stdout, stderr=stderr, cmd=[forcerm, cmdline], msg=[rmout, stdout])

    # Damn! FORCEREMOVE succeeded and COMMANDLINE failed. Try to restore old
    # state and end up with a 'failed' status anyway.
    if rename and ( old_exists and not os.path.isfile(old) ) and ( os.path.isfile(new) and not new_exists ):
        os.rename(new, old)

    RESTORE = [ENVIRONMENT, 'LC_ALL=C', DPKG_DIVERT, '--divert', old, path]
    old_pkg = listpackage.rstrip()
    if old_pkg != "LOCAL":
        RESTORE.insert(3, '--package')
        RESTORE.insert(4, old_pkg)
    rename and RESTORE.insert(3, '--rename')

    module.run_command(RESTORE, check_rc=True)
    module.exit_json(failed=True, changed=True, stdout=stdout, stderr=stderr, cmd=[forcerm, cmdline])

if __name__ == '__main__':
    main()
