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
    one_file_system:
        description:
            - Do not cross filesystem boundaries.
            - When set, this parameter limits rsync’s recursion through the
              hierarchy of the C(src) specified for sending, and also the
              analogous recursion on the receiving side during deletion.
        type: 'bool'
        default: false
    exclude:
        description:
            - List of PATTERNS allowing one to exclude files matching a PATTERN.
        type: 'list'
        default: []
    include:
        description:
            - List of PATTERNS allowing one to include files matching a PATTERN
              even if they match ecluded PATTERNS.
        type: 'list'
        default: []
    filter:
        description:
            - List of file-filtering RULES, allowing one to exclude files from
              transfer with more granularity than with the C(exclude)/C(include)
              parameters.
        type: 'list'
        default: []
    ssh_pass:
        description:
            - Password to use to authenticate the ssh's remote user on the rsync
              server side from the rsync client side (i.e. the ansible target).
            - When set, it requires C(sshpass) program to be installed on the
              ansible target (i.e. the rsync client).
        type: 'string'
    ssh_args:
        description:
            - List of arbitrary ssh options and their arguments used to ensure
              transport of the rsync protocol between hosts.
        type: 'list'
        default: []
    rsync_opts:
        description:
            - List of arbitrary rsync options and their arguments. As the
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
    rsync_opts:
      - "--delete"

- name: create a (likely complete) differential backup against the complete backup of the day
  rsync:
    src: '{{ ansible_env.HOME }}/'
    dest: '/media/nfs/{{ ansible_fqdn }}/{{ ansible_env.HOME }}.{{ ansible_date_time.date }}.{{ ansible_date_time.hour }}{{ ansible_date_time.minute }}'
    rsync_opts:
      - "--delete"
      - "--link-dest=../{{ ansible_env.HOME }}.{{ ansible_date_time.date }}"

- name: synchronize two directories without worrying about vanished files (rc=24)
  rsync:
    src: /some/directory/to/backup
    dest: remote:/some/directory/to/receive/backup
    one_file_system: yes
    exclude:
      - /lost+found
    rsync_opts:
      - "--delete"
      - "--delete-excluded"
  register: reg
  failed_when: reg.rc != 0 and reg.rc != 24

- name: run rsync in a command task, with bits of idempotency and check mode support
  command: >
    rsync {% if ansible_check_mode %}--dry-run{% endif %}
    --out-format="<<CHANGED>>%i %n%L" --archive --delete --one-file-system
    --exclude=/lost+found --delete-excluded {{ source }} {{ destination }}
  register: result
  changed_when: '"<<CHANGED>>" in result.stdout'
'''


from ansible.module_utils.basic import AnsibleModule

def main():
    # Define module's parameters and supported modes
    module = AnsibleModule(
        argument_spec = dict(
            src             = dict(type='str', required=True),
            dest            = dict(type='str', required=True),
            archive         = dict(type='bool', default=True),
            one_file_system = dict(type='bool', default=False),
            exclude         = dict(type='list', default=[]),
            include         = dict(type='list', default=[]),
            filter          = dict(type='list', default=[]),
            ssh_pass        = dict(type='str', no_log=True),
            ssh_args        = dict(type='list'),
            rsync_opts      = dict(type='list', default=[])
        ),
        supports_check_mode = True
    )

    # Set variables with the same name as the module parameters, also with the
    # same values, i.e. do not ever try to do complicated things with namespaces
    src             = module.params['src']
    dest            = module.params['dest']
    archive         = module.params['archive']
    one_file_system = module.params['one_file_system']
    exclude         = module.params['exclude']
    include         = module.params['include']
    filter          = module.params['include']
    ssh_pass        = module.params['ssh_pass']
    ssh_args        = module.params['ssh_args']
    rsync_opts      = module.params['rsync_opts']

    # Requirements:
    RSYNC = module.get_bin_path('rsync', required=True)
    if ssh_pass: module.get_bin_path('sshpass', required=True)

    # Start to build the commandline to be performed, as a list to pass to
    # module.run_command().
    COMMANDLINE = [RSYNC]

    if archive:
        COMMANDLINE.append('--archive')

    if one_file_system:
        COMMANDLINE.append('--one-file-system')

    for x in exclude:
        COMMANDLINE.append('--exclude=%s' % x)
    for i in include:
        COMMANDLINE.append('--include=%s' % i)
    for f in filter:
        COMMANDLINE.append('--filter=%s' % f)

    # Setup the ssh transport of the rsync protocol. Be sure arguments with
    # white spaces will be passed correctly to both rsync AND ssh.
    if ssh_pass or ssh_args:
        COMMANDLINE.append('--rsh')
    if ssh_pass and ssh_args:
        COMMANDLINE.append('sshpass -p \'%s\' ssh %s' % (ssh_pass, ' '.join(ssh_args)))
    else:
        if ssh_pass:
            COMMANDLINE.append('sshpass -p \'%s\' ssh' % ssh_pass)
        if ssh_args:
            COMMANDLINE.append('ssh %s' % ' '.join(ssh_args))

    # This allows one to append options that are not supported as module
    # parameters, or to override module parameters with --no-OPTION options.
    if rsync_opts:
        COMMANDLINE.extend(rsync_opts)

    # These rsync options (--dry-run and --out-format) MUST come at the very end
    # to not be overridden by rsync_opts contents (--no-dry-run, another format
    # for --out-format).
    if module.check_mode:
        COMMANDLINE.append('--dry-run')

    # All the stuff with --out-format, the marker and its further cleanup, diff
    # mode and so on came first from the 'synchronize' module.
    marker = '<<CHANGED>>'
    COMMANDLINE.append('--out-format=%s%s' % (marker, '%i %n%L'))

    COMMANDLINE.append(src)
    COMMANDLINE.append(dest)

    cmd = ' '.join(COMMANDLINE)

    ( rc, stdout_marker, stderr ) = module.run_command(COMMANDLINE)
    changed = marker in stdout_marker

    # Format what will be returned by the module
    stdout = stdout_marker.replace(marker, '')
    stdout_lines = stdout.split('\n')
    stderr_lines = stderr.split('\n')
    while '' in stdout_lines: stdout_lines.remove('')
    while '' in stderr_lines: stderr_lines.remove('')

    if rc:
        return module.fail_json(rc=rc, msg=stderr_lines, cmd=cmd)

    if module._diff:
        diff = {'prepared': stdout}
        return module.exit_json(diff=diff,
                changed=changed,
                rc=rc,
                stdout=stdout,
                stderr=stderr,
                stdout_lines=stdout_lines,
                cmd=cmd)
    else:
        return module.exit_json(
                changed=changed,
                rc=rc,
                stdout=stdout,
                stderr=stderr,
                stdout_lines=stdout_lines,
                cmd=cmd)

if __name__ == '__main__':
    main()
