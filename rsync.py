#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Ansible module to remotely synchronize directories.

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
module: rsync
short_description: simple wrapper around rsync command
description:
    - This module is a simple wrapper around I(rsync)(1) commandline tool. It
      is intended to synchronize two directories on hosts or between hosts,
      instead of between ansible controler and the hosts (as does the module
      C(synchronize)). It does the same as the rsync command itself, with two
      ansible features in mind. Using this module instead of running rsync in
      a shell task ensures idempotency and full compatibility with I(check) or
      I(dry-run) mode. If you really want to use command or shell modules,
      take a look to the last example.
version_added: "2.4"
author:
    - "Yann Amar <quidame@poivron.org>"
options:
    dest:
        description:
            - The destination path of the synchronization. If absolute or
              relative, the path refers to the ansible target. To synchronize
              a directory from the target host to another (over ssh), prefix
              the path with the name of the remote host followed by a colon,
              as in C(foobar.example.org:/destination/path). It also accepts
              C(rsync://) URI, just as rsync does.
            - No matter if the path ends with a trailing slash or not.
        required: true
        default: null
    src:
        description:
            - The source directory of the synchronization. If absolute or
              relative, the path refers to the ansible target. To synchronize
              a directory from another host to the target (over ssh), prefix
              the path with the name of the remote host followed by a colon,
              as in C(foobar.example.org:/source/path). It also accepts
              C(rsync://) URI, just as rsync does.
            - Please refer to the rsync's manual page to be comfortable with
              the meaning of a trailing /.
        required: true
        default: null
    opts:
        description:
            - Array of arbitrary rsync options and their arguments. As the
              C(src) and the C(dest), they're passed verbatim to rsync (and
              errors are handled by rsync too). Option C(--out-format) is
              always added with a proper argument to ensure idempotency, and
              the C(--dry-run) option is also added when running ansible in
              check mode.
        required: no
        default: []
requirements: [ rsync ]
'''

EXAMPLES = '''
- name: copy /usr/local/bin from machineA to machineB (machineA is the ansible target)
  rsync:
    src: /usr/local/bin
    dest: "machineB:/usr/local"

- name: copy /usr/local/bin from machineB to machineA (machineA is the ansible target)
  rsync:
    src: "machineB:/usr/local/bin"
    dest: /usr/local

- name: create/update a complete user's home backup on a network storage locally mounted
  rsync:
    src: '{{ ansible_env.HOME }}/'
    dest: '/media/nfs/{{ ansible_fqdn }}/{{ ansible_env.HOME }}.{{ ansible_date_time.date }}'
    opts:
      - "--archive"
      - "--delete"

- name: create a (likely complete) differential backup against the complete backup of the day
  rsync:
    src: '{{ ansible_env.HOME }}/'
    dest: '/media/nfs/{{ ansible_fqdn }}/{{ ansible_env.HOME }}.{{ ansible_date_time.date }}.{{ ansible_date_time.hour }}{{ ansible_date_time.minute }}'
    opts:
      - "--archive"
      - "--delete"
      - "--link-dest=../{{ ansible_env.HOME }}.{{ ansible_date_time.date }}"

- name: synchronize two directories without worrying about vanished files (rc=24)
  rsync:
    src: /some/directory/to/backup
    dest: remote:/some/directory/to/receive/backup
    opts:
      - "--an-option"
      - "--another-option"
  register: reg
  failed_when: reg.rc != 0 and reg.rc != 24

- name: run rsync in a command task, with bits of idempotency and check mode support
  command: >
    rsync {% if ansible_check_mode %}--dry-run{% endif %}
    --out-format="<< CHANGED >> %i %n%L" --archive --delete --one-file-system
    --exclude=/lost+found --delete-excluded {{ source }} {{ destination }}
  register: result
  changed_when: '"<<CHANGED>>" in result.stdout'
'''

from ansible.module_utils.basic import *

def main():
    module = AnsibleModule(
        argument_spec = dict(
            src  = dict(required=True),
            dest = dict(required=True),
            opts = dict(type='list')
        ),
        supports_check_mode = True
    )
    src   = module.params['src']
    dest  = module.params['dest']
    opts  = module.params['opts']
    RSYNC = module.get_bin_path('rsync', required=True)

    COMMANDLINE = [RSYNC]
    marker = '<< CHANGED >>'
    COMMANDLINE.append('--out-format=' + marker + '%i %n%L')
    module.check_mode and COMMANDLINE.append('--dry-run')
    if opts: COMMANDLINE.extend(opts)
    COMMANDLINE.append(src)
    COMMANDLINE.append(dest)

    ret, out, err = module.run_command(COMMANDLINE)
    changed = marker in out
    ret == 0 and module.exit_json(changed=changed, rc=ret, stdout=out, stderr=err, cmd=' '.join(COMMANDLINE))
    module.exit_json(failed=True, changed=changed, rc=ret, stdout=out, stderr=err, cmd=' '.join(COMMANDLINE))

if __name__ == '__main__':
    main()
