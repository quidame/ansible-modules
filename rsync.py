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
    - This module is a simple wrapper around C(rsync)(1) commandline tool. It
      is intended to synchronize two directories on remote hosts or between
      remote hosts, instead of between the ansible controller and its targets
      (as does the M(synchronize) module).
    - More suitable to trigger backup tasks on the targets than to deploy same
      directory contents on them, it allows one to do that too, by pulling a
      directory contents from a third server that may as well not be in the
      inventory. This is the point.
    - Again, if you have to deploy directories from controller to targets, use
      the M(synchronize) module instead, whose it's the purpose.
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
            - Archive mode. Implies I(recursive), I(links), I(perms), I(times),
              I(group), I(owner), I(devices) and I(specials) set to C(True).
            - Each of them can be explicitly and individually reset to C(False)
              to override this default behaviour.
            - Does not affect I(hard_links), I(acls) nor I(xattrs) values.
        type: 'bool'
        default: true
    recursive:
        description:
            - Copy directories recursively.
        type: 'bool'
        default: same value than archive parameter
    links:
        description:
            - Copy symlinks as symlinks.
        type: 'bool'
        default: same value than archive parameter
    perms:
        description:
            - Preserve permissions.
        type: 'bool'
        default: same value than archive parameter
    times:
        description:
            - Preserve modification times.
        type: 'bool'
        default: same value than archive parameter
    group:
        description:
            - Preserve group.
        type: 'bool'
        default: same value than archive parameter
    owner:
        description:
            - Preserve owner.
            - This parameter is silently ignored for non-root users.
        type: 'bool'
        default: same value than archive parameter
    devices:
        description:
            - Preserve device files.
            - This parameter is silently ignored for non-root users.
        type: 'bool'
        default: same value than archive parameter
    specials:
        description:
            - Preserve special files.
        type: 'bool'
        default: same value than archive parameter
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
              transfer with more granularity than with the I(exclude)/I(include)
              parameters.
        type: 'list'
        default: []
    delete:
        description:
            - Delete extraneous files from the receiving side (ones that aren’t
              on the sending side), but only for the directories that are being
              synchronized. Files that are excluded from the transfer are also
              excluded from being deleted unless you use the C(delete_excluded)
              parameter.
            - C(before) requests that the file-deletions on the receiving side
              be done before the transfer starts.
            - C(during) requests that the file-deletions on the receiving side
              be done incrementally as the transfer happens.
            - C(delay) requests that the file-deletions on the receiving side
              be computed during the transfer (like C(during)), and then removed
              after the transfer completes (like C(after)).
            - C(after) requests that the file-deletions on the receiving side
              be done after the transfer has completed.
            - C(auto) defaults to C(during) or C(delay), then fallbacks to
              C(after), depending on rsync version on both sides.
        choices: ['before', 'during', 'delay', 'after', 'auto']
    delete_excluded:
        description:
            - In addition to deleting the files on the receiving side that are
              not on the sending side, this tells rsync to also delete any files
              on the receiving side that are excluded (see I(exclude)).
        type: 'bool'
        default: false
    one_file_system:
        description:
            - Do not cross filesystem boundaries.
            - When set, this parameter limits rsync’s recursion through the
              hierarchy of the I(src) specified for sending, and also the
              analogous recursion on the receiving side during deletion.
        type: 'bool'
        default: false
    ignore_vanished:
        description:
            - Ignore errors due to files that where present on the sender at
              the time of rsync scan, but where not present at the time of
              transfer.
        type: 'bool'
        default: false
    link_dest:
        description:
            - Hardlink files to those within the specified directory when they
              are unchanged.
            - When relative, the path is relative to the destination directory.
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
    rsync_path:
        description:
            - Absolute path of the rsync command on the remote host.
        type: 'path'
    rsync_super:
        description:
            - Operate as root on the remote host.
            - There is no way to pass a password to the module to become root.
        type: 'bool'
        default: false
    rsync_opts:
        description:
            - List of arbitrary rsync options and their arguments. As the
              I(src) and the I(dest), they're passed verbatim to rsync (and
              errors are handled by rsync too).
            - C(--out-format) is always added with a proper argument to ensure
              idempotency.
            - C(--dry-run) is also added when running ansible in check mode.
        default: []
requirements: [ rsync ]
'''

EXAMPLES = '''
- name: copy /usr/local/bin from foo to bar (foo is the ansible target)
  rsync:
    src: "/usr/local/bin"
    dest: "bar:/usr/local"

- name: copy /usr/local/bin from bar to foo (foo is the ansible target)
  rsync:
    src: "bar:/usr/local/bin"
    dest: "/usr/local"

- name: create/update a complete user's home backup
  rsync:
    src: '{{ ansible_env.HOME }}/'
    dest: '/media/nfs/{{ ansible_fqdn }}{{ ansible_env.HOME }}/{{ ansible_date_time.date }}'
    delete: auto

- name: create a (likely complete) differential backup against the complete backup of the day
  rsync:
    src: '{{ ansible_env.HOME }}/'
    dest: '/media/nfs/{{ ansible_fqdn }}{{ ansible_env.HOME }}/{{ ansible_date_time.date }}.{{ ansible_date_time.hour }}{{ ansible_date_time.minute }}'
    delete: auto
    link_dest: "../{{ ansible_date_time.date }}"

- name: synchronize two directories without worrying about vanished files
  rsync:
    src: /some/directory/to/backup
    dest: remote:/some/directory/to/receive/backup
    one_file_system: yes
    ignore_vanished: yes
    delete_excluded: yes
    exclude:
      - /lost+found

- name: rsync command, with bits of idempotency and check mode support
  command: >
    rsync {% if ansible_check_mode %}--dry-run{% endif %}
    --out-format="<<CHANGED>>%i %n%L" --archive --delete --one-file-system
    --exclude=/lost+found --delete-excluded {{ source }} {{ destination }}
  register: result
  changed_when: '"<<CHANGED>>" in result.stdout'
  failed_when: result.rc != 0 and result.rc != 24
'''

RETURN = ''' # '''


from ansible.module_utils.basic import AnsibleModule

def main():
    # Define module's parameters and supported modes
    module = AnsibleModule(
        argument_spec = dict(
            src             = dict(type='str', required=True),
            dest            = dict(type='str', required=True),
            archive         = dict(type='bool', default=True),
            recursive       = dict(type='bool'),
            links           = dict(type='bool'),
            perms           = dict(type='bool'),
            times           = dict(type='bool'),
            group           = dict(type='bool'),
            owner           = dict(type='bool'),
            devices         = dict(type='bool'),
            specials        = dict(type='bool'),
            exclude         = dict(type='list', default=[]),
            include         = dict(type='list', default=[]),
            filter          = dict(type='list', default=[]),
            delete          = dict(type='str', choices=['before','during','after','delay','auto']),
            delete_excluded = dict(type='bool', default=False),
            one_file_system = dict(type='bool', default=False),
            ignore_vanished = dict(type="bool", default=False),
            link_dest       = dict(type='str'),
            ssh_pass        = dict(type='str', no_log=True),
            ssh_args        = dict(type='list'),
            rsync_path      = dict(type='path'),
            rsync_super     = dict(type='bool', default=False),
            rsync_opts      = dict(type='list', default=[])
        ),
        supports_check_mode = True
    )

    # Set variables with the same name as the module parameters, also with the
    # same values, i.e. do not ever try to do complicated things with namespaces
    src             = module.params['src']
    dest            = module.params['dest']
    archive         = module.params['archive']
    recursive       = module.params['recursive']
    links           = module.params['links']
    perms           = module.params['perms']
    times           = module.params['times']
    group           = module.params['group']
    owner           = module.params['owner']
    devices         = module.params['devices']
    specials        = module.params['specials']
    exclude         = module.params['exclude']
    include         = module.params['include']
    filter          = module.params['include']
    delete          = module.params['delete']
    delete_excluded = module.params['delete_excluded']
    one_file_system = module.params['one_file_system']
    ignore_vanished = module.params['ignore_vanished']
    link_dest       = module.params['link_dest']
    ssh_pass        = module.params['ssh_pass']
    ssh_args        = module.params['ssh_args']
    rsync_path      = module.params['rsync_path']
    rsync_super     = module.params['rsync_super']
    rsync_opts      = module.params['rsync_opts']

    # Requirements:
    RSYNC = module.get_bin_path('rsync', required=True)
    if ssh_pass: module.get_bin_path('sshpass', required=True)

    # Start to build the commandline to be performed, as a list to pass to
    # module.run_command().
    COMMANDLINE = [RSYNC]

    if archive:
        COMMANDLINE.append('--archive')
        if recursive is False: COMMANDLINE.append('--no-recursive')
        if links is False:     COMMANDLINE.append('--no-links')
        if perms is False:     COMMANDLINE.append('--no-perms')
        if times is False:     COMMANDLINE.append('--no-times')
        if group is False:     COMMANDLINE.append('--no-group')
        if owner is False:     COMMANDLINE.append('--no-owner')
        if devices is False:   COMMANDLINE.append('--no-devices')
        if specials is False:  COMMANDLINE.append('--no-specials')
    else:
        if recursive is True:  COMMANDLINE.append('--recursive')
        if links is True:      COMMANDLINE.append('--links')
        if perms is True:      COMMANDLINE.append('--perms')
        if times is True:      COMMANDLINE.append('--times')
        if group is True:      COMMANDLINE.append('--group')
        if owner is True:      COMMANDLINE.append('--owner')
        if devices is True:    COMMANDLINE.append('--devices')
        if specials is True:   COMMANDLINE.append('--specials')

    if one_file_system:
        COMMANDLINE.append('--one-file-system')

    for x in exclude:
        COMMANDLINE.append('--exclude=%s' % x)
    for i in include:
        COMMANDLINE.append('--include=%s' % i)
    for f in filter:
        COMMANDLINE.append('--filter=%s' % f)

    if delete == 'auto':
        COMMANDLINE.append('--delete')
    elif delete != None:
        COMMANDLINE.append('--delete-%s' % delete)

    # --delete-ecluded implies --delete, and there is no good reason to allow
    # --no-delete
    if delete_excluded:
        COMMANDLINE.append('--delete-excluded')

    # Let rsync resolve the path of the directory (pass the module parameter
    # value verbatim to rsync commandline)
    if link_dest:
        COMMANDLINE.append("--link-dest=%s" % link_dest)

    # Setup the ssh transport of the rsync protocol. Be sure arguments with
    # white spaces will be passed correctly to both rsync AND ssh.
    if ssh_pass or ssh_args:
        COMMANDLINE.append('--rsh')
    if ssh_pass and ssh_args:
        COMMANDLINE.append('sshpass -p \'%s\' ssh %s' % (ssh_pass, ' '.join(ssh_args)))
    elif ssh_pass:
        COMMANDLINE.append('sshpass -p \'%s\' ssh' % ssh_pass)
    elif ssh_args:
        COMMANDLINE.append('ssh %s' % ' '.join(ssh_args))

    # Setup which remote rsync command to run, and which remote user to run as
    if rsync_path:
        COMMANDLINE.append('--rsync-path=%s' % rsync_path)
    if rsync_super:
        COMMANDLINE.append('-M--super')

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

    if rc == 0 or ( rc == 24 and ignore_vanished ):
        return module.exit_json(
                changed=changed,
                rc=rc,
                stdout=stdout,
                stderr=stderr,
                stdout_lines=stdout_lines,
                stderr_lines=stderr_lines,
                cmd=cmd)
    else:
        return module.fail_json(
                msg=stderr_lines,
                changed=changed,
                rc=rc,
                cmd=cmd)

if __name__ == '__main__':
    main()
