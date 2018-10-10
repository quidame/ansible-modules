#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Ansible module to check or commit /etc changes using etckeeper.

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
module: etckeeper
short_description: track changes in /etc with I(etckeeper(8))
description:
    - This module runs the command I(etckeeper)(1) to commit changes in /etc
      or to check that nothing has to be commited.
version_added: "2.4"
author:
    - "quidame@poivron.org"
options:
    commit:
        description:
            - When set, commit changes and use the value as the commit message.
        required: false
        default: null
requirements: []
'''

EXAMPLES = '''
- name: check that /etc is clean and abort if it is not
  etckeeper:

- name: commit changes in /etc
  etckeeper:
    commit: "Update sshd_config with new site's version"
'''

from ansible.module_utils.basic import *

def main():
    module = AnsibleModule(
        argument_spec = dict(commit = dict(required=False, type='str')),
        supports_check_mode = True
    )
    commit_message = module.params['commit']

    ETCKEEPER = module.get_bin_path('etckeeper')
    # Committing atomic changes may lead to run etckeeper module everywhere
    # between other tasks. To not overload all etckeeper tasks with conditional
    # statements, we don't want to fail if etckeeper is not installed. This is
    # why, despite the name of the module, the command itself is not required.
    if not ETCKEEPER: module.exit_json(changed=False, msg="etckeeper is not installed on %s." % os.uname()[1])

    rc, out, err = module.run_command([ETCKEEPER, 'unclean'])
    if rc == 0 and commit_message:
        if module.check_mode: module.exit_json(changed=True, msg="*** RUNNING IN CHECK MODE ***")
        rc, stdout, stderr = module.run_command([ETCKEEPER, 'commit', commit_message], check_rc=True)
        module.exit_json(changed=True, stdout=stdout, stderr=stderr)
    elif rc == 0:
        module.fail_json(msg="/etc is not clean")
    else:
        module.exit_json(changed=False, msg="/etc is clean (or not tracked) on %s." % os.uname()[1])

if __name__ == '__main__':
    main()
