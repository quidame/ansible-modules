#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2018, Yann Amar <quidame@poivron.org>
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
module: etckeeper
short_description: track changes in /etc with I(etckeeper(8))
description:
    - This module runs the command I(etckeeper)(1) to commit changes in
      /etc or to check that nothing has to be commited.
version_added: "2.4"
author: "quidame@poivron.org"
options:
    commit:
        description:
            - When set, commit changes and use the value as the commit
              message.
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


from ansible.module_utils.basic import AnsibleModule

def main():
    module = AnsibleModule(
        argument_spec = dict(commit = dict(required=False, type='str')),
        supports_check_mode = True
    )
    commit_message = module.params['commit']

    ETCKEEPER = module.get_bin_path('etckeeper')
    # Committing atomic changes may lead to run etckeeper module
    # everywhere between other tasks. To not overload all etckeeper
    # tasks with conditional statements, we don't want to fail if
    # etckeeper is not installed. This is why, despite the name of the
    # module, the command itself is not required.
    if not ETCKEEPER: module.exit_json(changed=False, msg="etckeeper is not installed on %s." % os.uname()[1])

    rc, out, err = module.run_command([ETCKEEPER, 'unclean'])
    if rc == 0 and commit_message:
        if module.check_mode: module.exit_json(changed=True, msg="*** RUNNING IN CHECK MODE ***")
        rc, stdout, stderr = module.run_command([ETCKEEPER, 'commit', commit_message], check_rc=True)
        module.exit_json(changed=True, stdout=stdout, stderr=stderr, msg=commit_message)
    elif rc == 0:
        module.fail_json(msg="/etc is not clean")
    else:
        module.exit_json(changed=False, msg="/etc is clean (or not tracked) on %s." % os.uname()[1])

if __name__ == '__main__':
    main()
