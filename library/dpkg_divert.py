#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2017-2020, Yann Amar <quidame@poivron.org>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = r'''
---
module: dpkg_divert
short_description: Override a package's version of a file
version_added: "2.10"
author:
  - quidame (@quidame)
description:
  - A diversion is for C(dpkg) the knowledge that only a given I(package)
    is allowed to install a file at a given I(path). Other packages shipping
    their own version of this file will be forced to I(divert) it, i.e. to
    install it at another location. It allows one to keep changes in a file
    provided by a debian package by preventing its overwrite at package
    upgrade.
  - This module manages diversions of debian packages files using the
    C(dpkg-divert)(1) commandline tool. It can either create or remove a
    diversion for a given file, but also update an existing diversion to
    modify its holder and/or its divert path.
  - It's a feature of this module to mimic C(dpkg-divert)'s behaviour
    regarding the renaming of files when removing as well as adding a
    diversion, i.e. existing files are never overwritten.
options:
  path:
    description:
      - The original and absolute path of the file to be diverted or
        undiverted. This path is unique, i.e. it is not possible to get
        two diversions for the same I(path).
    required: true
    type: path
    aliases: [name]
  state:
    description:
      - When I(state=absent), remove the diversion of the specified
        I(path); when I(state=present), create the diversion if it does
        not exist, or update its I(package) holder or I(divert) path,
        if any, and if I(force) is C(True).
      - Unless I(force) is C(True), the removal of I(path)'s diversion
        only happens if the diversion matches the I(divert) and
        I(package) values, if they're provided.
    type: str
    default: present
    choices: [absent, present]
  holder:
    description:
      - The name of the package whose copy of file is not diverted, also
        known as the diversion holder or the package the diversion belongs
        to.
      - The actual package does not have to be installed or even to exist
        for its name to be valid. If not specified, the diversion is hold
        by 'LOCAL', that is reserved by/for dpkg for local diversions.
      - Removing or updating a diversion fails if the diversion exists
        and belongs to another holder, unless I(force) is C(True).
    type: str
    aliases: [package]
  divert:
    description:
      - The location where the versions of file will be diverted.
      - Default is to add suffix C(.distrib) to the file path.
    type: path
  rename:
    description:
      - Actually move the file aside (or back).
      - Renaming is skipped (but module doesn't fail) in case the
        destination file already exists. This is a C(dpkg-divert)
        feature, and its purpose is to never overwrite a file. It also
        makes the command itself idempotent, and the module's I(force)
        parameter has no effect on this behaviour.
      - Also, I(rename) is ignored if the diversion entry is unchanged
        in the diversion database (adding an already existing diversion
        or removing a non-existing one).
    type: bool
    default: false
  force:
    description:
      - Force to divert file when diversion already exists and is hold
        by another I(package) or points to another I(divert). There is
        no need to use it for I(remove) action if I(divert) or I(holder)
        are not used.
      - This doesn't override the rename's lock feature, i.e. it doesn't
        help to force I(rename), but only to replace the diversion in
        dpkg database.
    type: bool
    default: false
requirements: [dpkg-divert]
'''

EXAMPLES = r'''
- name: divert /etc/screenrc to /etc/screenrc.distrib and keep file in place
  dpkg_divert: path=/etc/screenrc

- name: divert /etc/screenrc by package 'branding' (fake, used as a tag)
  dpkg_divert:
    name: /etc/screenrc
    package: branding

- name: remove the screenrc diversion only if belonging to 'branding'
  dpkg_divert:
    path: /etc/screenrc
    holder: branding
    state: absent

- name: divert and rename screenrc to screenrc.dpkg-divert, even if diversion is already set
  dpkg_divert:
    path: /etc/screenrc
    divert: /etc/screenrc.dpkg-divert
    rename: yes
    force: yes

- name: remove the screenrc diversion and maybe move the diverted file to its original place
  dpkg_divert:
    path: /etc/screenrc
    state: absent
    rename: yes
'''

import re
import os

from ansible.module_utils.basic import AnsibleModule


def main():

    # Mimic the behaviour of the dpkg-divert(1) command: '--add' is implicit
    # when not using '--remove'; '--rename' takes care to never overwrite
    # existing files; and options are intended to not conflict between them.

    # 'force' is an option of the module, not of the command, and implies to
    # run the command twice. Its purpose is to allow one to re-divert a file
    # with another target path or to 'give' it to another package, in one task.
    # This is very easy because one of the values is unique in the diversion
    # database, and dpkg-divert itself is idempotent (does nothing when nothing
    # needs doing).

    module = AnsibleModule(
        argument_spec=dict(
            path=dict(required=True, type='path', aliases=['name']),
            state=dict(required=False, type='str', default='present', choices=['absent', 'present']),
            holder=dict(required=False, type='str', aliases=['package']),
            divert=dict(required=False, type='path'),
            rename=dict(required=False, type='bool', default=False),
            force=dict(required=False, type='bool', default=False),
        ),
        supports_check_mode=True,
    )

    module.run_command_environ_update = dict(LANG='C', LC_ALL='C', LC_MESSAGES='C', LC_CTYPE='C')

    path = module.params['path']
    state = module.params['state']
    holder = module.params['holder']
    divert = module.params['divert']
    rename = module.params['rename']
    force = module.params['force']

    DPKG_DIVERT = module.get_bin_path('dpkg-divert', required=True)

    # Start to build the commandline we'll have to run
    COMMANDLINE = [DPKG_DIVERT, path]

    # Then insert options as requested in the task parameters:
    if state == 'absent':
        COMMANDLINE.insert(1, '--remove')
    elif state == 'present':
        COMMANDLINE.insert(1, '--add')

    if rename:
        COMMANDLINE.insert(1, '--rename')
    else:
        COMMANDLINE.insert(1, '--no-rename')

    if divert:
        COMMANDLINE.insert(1, '--divert')
        COMMANDLINE.insert(2, divert)

    if holder == 'LOCAL':
        COMMANDLINE.insert(1, '--local')
    elif holder:
        COMMANDLINE.insert(1, '--package')
        COMMANDLINE.insert(2, holder)

    # dpkg-divert has a useful --test option that we will use in check mode or
    # when needing to parse output before actually doing anything.
    TESTCOMMAND = list(COMMANDLINE)
    TESTCOMMAND.insert(1, '--test')
    if module.check_mode:
        COMMANDLINE = list(TESTCOMMAND)

    cmd = ' '.join(COMMANDLINE)

    # `dpkg-divert --listpackage FILE` always returns 0, but not diverted files
    # provide no output.
    rc, listpackage, err = module.run_command([DPKG_DIVERT, '--listpackage', path])
    rc, placeholder, err = module.run_command(TESTCOMMAND)

    # There is probably no need to do more than that. Please read the first
    # sentence of the next comment for a better understanding of the following
    # `if` statement:
    if rc == 0 or not force or not listpackage:
        rc, stdout, stderr = module.run_command(COMMANDLINE, check_rc=True)
        if re.match('^(Leaving|No diversion)', stdout):
            module.exit_json(changed=False, stdout=stdout, stderr=stderr, cmd=cmd)
        else:
            module.exit_json(changed=True, stdout=stdout, stderr=stderr, cmd=cmd)

    # So, here we are: the test failed AND force is true AND a diversion exists
    # for the file: 'rc != 0 and force and listpackage' is not a condition
    # because this is the only way since all other cases are caught by the OR'd
    # condition above (a OR b OR c).
    # Anyway, we have to remove this diversion first (then stop here, or add
    # a new diversion for the same file), and without failure. Cases of failure
    # with dpkg-divert are:
    # - The diversion does not belong to the same package (or LOCAL)
    # - The divert filename is not the same (e.g. path.distrib != path.divert)
    # So: force removal by stripping '--package' and '--divert' options... and
    # their arguments. Fortunately, this module accepts only a few parameters,
    # so we can rebuild a whole command line from scratch at no cost:
    FORCEREMOVE = [DPKG_DIVERT, '--remove', path]
    if rename:
        FORCEREMOVE.insert(1, '--rename')
    else:
        FORCEREMOVE.insert(1, '--no-rename')

    if module.check_mode:
        FORCEREMOVE.insert(1, '--test')

    forcerm = ' '.join(FORCEREMOVE)

    if state == 'absent':
        rc, stdout, stderr = module.run_command(FORCEREMOVE, check_rc=True)
        module.exit_json(changed=True, stdout=stdout, stderr=stderr, cmd=forcerm)

    # The situation is that we want to modify the settings (holder or divert)
    # of an existing diversion. dpkg-divert does not handle this, and we have
    # to remove the diversion and set a new one. First, get state info:
    rc, truename, err = module.run_command([DPKG_DIVERT, '--truename', path])
    rc, rmout, rmerr = module.run_command(FORCEREMOVE, check_rc=True)
    if module.check_mode:
        module.exit_json(changed=True, cmd=[forcerm, cmd], msg=[rmout, (
            "*** RUNNING IN CHECK MODE ***",
            "The next step can't be actually performed - even dry-run - "
            "without error (since the previous removal didn't happen) "
            "but is supposed to achieve the task.")])

    old = truename.rstrip()
    if divert:
        new = divert
    else:
        new = '.'.join([path, 'distrib'])

    # Store state of files as they may change
    old_exists = os.path.isfile(old)
    new_exists = os.path.isfile(new)

    # RENAMING NOT REMAINING
    # The behaviour of this module is to NEVER overwrite a file, i.e. never
    # change file contents but only file paths and only if not conflicting,
    # as does dpkg-divert. It means that if there is already a diversion for
    # a given file and the divert file exists too, the divert file must be
    # moved from old to new divert paths between the two dpkg-divert commands,
    # because:
    #
    # src = /etc/screenrc           (tweaked ; exists)
    # old = /etc/screentc.distrib   (default ; exists)
    # new = /etc/screenrc.ansible   (not existing yet)
    #
    # Without extra move:
    # 1. dpkg-divert --rename --remove src
    #    => dont move old to src because src exists
    # 2. dpkg-divert --rename --divert new --add src
    #    => move src to new because new doesn't exist
    # Results:
    #   - old still exists with default contents
    #   - new holds the tweaked contents
    #   - src is missing
    #   => confusing, kind of breakage
    #
    # With extra move:
    # 1. dpkg-divert --rename --remove src
    #    => dont move old to src because src exists
    # 2. os.path.rename(old, new) [conditional]
    #    => move old to new because new doesn't exist
    # 3. dpkg-divert --rename --divert new --add src
    #    => dont move src to new because new exists
    # Results:
    #   - old does not exist anymore
    #   - src is still the same tweaked file
    #   - new exists with default contents
    #   => idempotency for next times, and no breakage
    #
    if rename and old_exists and not new_exists:
        os.rename(old, new)

    rc, stdout, stderr = module.run_command(COMMANDLINE)
    rc == 0 and module.exit_json(changed=True, stdout=stdout, stderr=stderr, cmd=[forcerm, cmd], msg=[rmout, stdout])

    # Damn! FORCEREMOVE succeeded and COMMANDLINE failed. Try to restore old
    # state and end up with a 'failed' status anyway.
    if rename and (old_exists and not os.path.isfile(old)) and (os.path.isfile(new) and not new_exists):
        os.rename(new, old)

    RESTORE = [DPKG_DIVERT, '--divert', old, path]
    old_pkg = listpackage.rstrip()
    if old_pkg == "LOCAL":
        RESTORE.insert(1, '--local')
    else:
        RESTORE.insert(1, '--package')
        RESTORE.insert(2, old_pkg)

    if rename:
        RESTORE.insert(1, '--rename')
    else:
        RESTORE.insert(1, '--no-rename')

    module.run_command(RESTORE, check_rc=True)
    module.exit_json(failed=True, changed=True, stdout=stdout, stderr=stderr, cmd=[forcerm, cmd])


if __name__ == '__main__':
    main()
