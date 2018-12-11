#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2017-2018, Yann Amar <quidame@poivron.org>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: dpkg_divert
short_description: Override a package's version of a file
description:
    - This module manages diversions of debian packages files using the
      C(dpkg-divert)(1) commandline tool.
version_added: "2.4"
author: "quidame@poivron.org"
options:
    path:
        description:
            - The original and absolute path of the file to be diverted or
              undiverted.
        required: true
        type: 'path'
    divert:
        description:
            - The location where the versions of file will be diverted.
            - Default is to add suffix C(.distrib) to the file path.
        type: 'path'
    remove:
        description:
            - Remove a diversion for file.
            - Unless I(force) is C(True), the removal of I(path)'s diversion
              only happens if the diversion matches the I(divert) and
              I(package) values, if any.
        type: 'bool'
        default: false
    rename:
        description:
            - Actually move the file aside (or back).
            - Renaming is skipped (but module doesn't fail) in case the
              destination file already exists.
        type: 'bool'
        default: false
    package:
        description:
            - The name of the package whose copy of file is not diverted, also
              called the diversion holder or the package the diversion belongs
              to.
            - Arbitrary string. The actual package does not have to be installed
              or even to exist for its name to be valid. If not specified, the
              diversion is hold by 'LOCAL', that is reserved by/for dpkg.
            - Diversion is aborted in case the diversion already exists and
              belongs to another package, unless I(force) is C(True).
    force:
        description:
            - Force to divert file when diversion already exists and is hold
              by another I(package) or points to another I(divert). There is
              no need to use it for I(remove) action if I(divert) or I(package)
              are not used.
            - This doesn't override the rename's lock feature, i.e. it doesn't
              help to force I(rename), but only to force the diversion for dpkg.
        type: 'bool'
        default: false
requirements: [ dpkg-divert, env ]
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


from ansible.module_utils.basic import AnsibleModule
import os.path
import re

def main():

    # Mimic the behaviour of the dpkg-divert(1) command: '--add' is implicit
    # when not using '--remove'; '--rename' takes care to never overwrite
    # existing files; and options are intended to not conflict between them.

    # 'force' is an option of the module, not of the command, and implies to
    # run the command twice. Its purpose is to allow one to re-divert a file
    # with another target path or to 'give' it to another package, in one task.

    module = AnsibleModule(
        argument_spec = dict(
            package = dict(required=False, type='str'),
            path    = dict(required=True,  type='path'),
            divert  = dict(required=False, type='path'),
            remove  = dict(required=False, type='bool', default=False),
            rename  = dict(required=False, type='bool', default=False),
            force   = dict(required=False, type='bool', default=False),
        ),
        supports_check_mode = True,
    )

    path    = module.params['path']
    divert  = module.params['divert']
    remove  = module.params['remove']
    rename  = module.params['rename']
    package = module.params['package']
    force   = module.params['force']

    DPKG_DIVERT = module.get_bin_path('dpkg-divert', required=True)
    # We need to parse the command's output, which is localized.
    # So we have to reset environment variable (LC_ALL).
    ENVIRONMENT = module.get_bin_path('env', required=True)

    # Start to build the commandline we'll have to run
    COMMANDLINE = [ENVIRONMENT, 'LC_ALL=C', DPKG_DIVERT, path]

    # Then insert options as requested in the task parameters:
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
    if module.check_mode:
        COMMANDLINE = list(TESTCOMMAND)

    cmdline = ' '.join(COMMANDLINE)
    fortest = ' '.join(TESTCOMMAND)

    # `dpkg-divert --listpackage FILE` always returns 0, but not diverted files
    # provide no output.
    rc, listpackage, _ = module.run_command([DPKG_DIVERT, '--listpackage', path])
    rc, placeholder, _ = module.run_command(TESTCOMMAND)

    # There is probably no need to do more than that. Please read the first
    # sentence of the next comment for a better understanding of the following
    # `if` statement:
    if rc == 0 or not force or not listpackage:
        rc, stdout, stderr = module.run_command(COMMANDLINE, check_rc=True)
        if re.match('^(Leaving|No diversion)', stdout):
            module.exit_json(changed=False, stdout=stdout, stderr=stderr, cmd=cmdline)
        module.exit_json(changed=True, stdout=stdout, stderr=stderr, cmd=cmdline)

    # So, here we are: the test failed AND force is true AND a diversion exists
    # for the file.  Anyway, we have to remove it first (then stop here, or add
    # a new diversion for the same file), and without failure. Cases of failure
    # with dpkg-divert are:
    # - The diversion does not belong to the same package (or LOCAL)
    # - The divert filename is not the same (e.g. path.distrib != path.divert)
    # So: force removal by stripping '--package' and '--divert' options... and
    # their arguments. Fortunately, this module accepts only a few parameters,
    # so we can rebuild a whole command line from scratch at no cost:
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
    rc, rmout, rmerr = module.run_command(FORCEREMOVE, check_rc=True)
    if module.check_mode:
        module.exit_json(changed=True, cmd=[forcerm, cmdline], msg=[rmout,
            "*** RUNNING IN CHECK MODE ***",
            "The next step can't be actually performed without error (since the previous removal didn't happen) but is supposed to achieve the task."])

    old = truename.rstrip()
    if divert:
        new = divert
    else:
        new = '.'.join([path, 'distrib'])

    # Store state of files as they may change
    old_exists = os.path.isfile(old)
    new_exists = os.path.isfile(new)

    # After that, if rename, old must not exist and new may exist
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
