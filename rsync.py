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
module: rsync
short_description: simple wrapper around rsync command
description:
    - This module is a simple wrapper around I(rsync)(1) commandline tool. It
      is intended to synchronize two directories on remote hosts or between
      remote hosts, instead of between the ansible controller and its targets
      (as does the C(synchronize) module).
    - More suitable to trigger backup tasks on the targets than to deploy same
      directory contents on them, it allows one to do that too, by pulling a
      directory contents from a third server that may as well not be in the
      inventory. This is the point.
    - Again, if you have to deploy directories from controller to targets, use
      the I(synchronize) module instead, whose it's the purpose.
version_added: "2.4"
author: "quidame@poivron.org"
options:
    src:
        description:
            - The source directory of the synchronization. If absolute or
              relative, the path refers to the ansible target. To synchronize
              a directory from another host to the target (over ssh), prefix
              the path with the name of the remote host followed by a colon,
              as in C(foobar.example.org:/source/path). It also accepts
              C(rsync://) URI, just as rsync does.
            - When the source path ends with a C(/) character, the contents of
              the source directory is copied into the destination directory,
              otherwise the source directory itself is copied into the
              destination directory. Please refer to the rsync's manual page
              to be comfortable with the meaning of a trailing slash.
        required: true
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
    archive:
        description:
            - Archive mode. Implies C(recursive), C(links), C(perms), C(times),
              C(group), C(owner), C(devices) and C(specials) set to C(True).
            - Each of them can be explicitly and individually reset to C(False)
              to override this default behaviour.
            - Does not affect C(hard_links), C(acls) nor C(xattrs) values.
        type: 'bool'
        default: true
    rsync_opts:
        description:
            - Array of arbitrary rsync options and their arguments. As the
              C(src) and the C(dest), they're passed verbatim to rsync (and
              errors are handled by rsync too).
            - C(--out-format) is always added with a proper argument to ensure
              idempotency.
            - C(--dry-run) is also added when running ansible in check mode.
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

- name: create/update a complete user's home backup
  rsync:
    src: '{{ ansible_env.HOME }}/'
    dest: '/media/nfs/{{ ansible_fqdn }}/{{ ansible_env.HOME }}.{{ ansible_date_time.date }}'
    opts:
      - "--delete"

- name: create a (likely complete) differential backup against the complete backup of the day
  rsync:
    src: '{{ ansible_env.HOME }}/'
    dest: '/media/nfs/{{ ansible_fqdn }}/{{ ansible_env.HOME }}.{{ ansible_date_time.date }}.{{ ansible_date_time.hour }}{{ ansible_date_time.minute }}'
    opts:
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
    --out-format="<<CHANGED>> %i %n%L" --archive --delete --one-file-system
    --exclude=/lost+found --delete-excluded {{ source }} {{ destination }}
  register: result
  changed_when: '"<<CHANGED>>" in result.stdout'
'''


from ansible.module_utils.basic import AnsibleModule

def main():
    # Define module's parameters and supported modes
    module = AnsibleModule(
        argument_spec = dict(
            src        = dict(type='str', required=True),
            dest       = dict(type='str', required=True),
            archive    = dict(type='bool', default=True),
            rsync_opts = dict(type='list', default=[])
        ),
        supports_check_mode = True
    )

    # Set variables with the same name as the module parameters, also with the
    # same values, i.e. do not ever try to do complicated things with namespaces
    src        = module.params['src']
    dest       = module.params['dest']
    archive    = module.params['archive']
    rsync_opts = module.params['rsync_opts']

    # Requirements:
    RSYNC = module.get_bin_path('rsync', required=True)

    # Start to build the commandline to be performed, as a list to pass to
    # module.run_command().
    COMMANDLINE = [RSYNC]

    if archive:
        COMMANDLINE.append('--archive')

    if rsync_opts:
        COMMANDLINE.extend(rsync_opts)

    # These rsync options (--dry-run and --out-format) MUST come at the very end
    # to not be overridden by rsync_opts contents (--no-dry-run, another format
    # for --out-format).
    if module.check_mode:
        COMMANDLINE.append('--dry-run')

    marker = '<<CHANGED>>'
    COMMANDLINE.append('--out-format=' + marker + '%i %n%L')

    COMMANDLINE.append(src)
    COMMANDLINE.append(dest)

    ret, out, err = module.run_command(COMMANDLINE)
    changed = marker in out
    ret == 0 and module.exit_json(changed=changed, rc=ret, stdout=out, stderr=err, cmd=' '.join(COMMANDLINE))
    module.exit_json(failed=True, changed=changed, rc=ret, stdout=out, stderr=err, cmd=' '.join(COMMANDLINE))

if __name__ == '__main__':
    main()
