import unittest
import os
from getpass import getuser

# import lshell specifics
from lshell.shellcmd import ShellCmd
from lshell.checkconfig import CheckConfig
from lshell.utils import get_aliases, updateprompt
from lshell.variables import builtins_list
from lshell import builtins
from lshell import sec

TOPDIR = '%s/../' % os.path.dirname(os.path.realpath(__file__))


class TestFunctions(unittest.TestCase):
    args = ['--config=%s/etc/lshell.conf' % TOPDIR, "--quiet=1"]
    userconf = CheckConfig(args).returnconf()
    shell = ShellCmd(userconf, args)

    def test_03_checksecure_doublepipe(self):
        """ U03 | double pipes should be allowed, even if pipe is forbidden """
        args = self.args + ["--forbidden=['|']"]
        userconf = CheckConfig(args).returnconf()
        INPUT = "ls || ls"
        return self.assertEqual(sec.check_secure(INPUT, userconf)[0], 0)

    def test_04_checksecure_forbiddenpipe(self):
        """ U04 | forbid pipe, should return 1 """
        args = self.args + ["--forbidden=['|']"]
        userconf = CheckConfig(args).returnconf()
        INPUT = "ls | ls"
        return self.assertEqual(sec.check_secure(INPUT, userconf)[0], 1)

    def test_05_checksecure_forbiddenchar(self):
        """ U05 | forbid character, should return 1 """
        args = self.args + ["--forbidden=['l']"]
        userconf = CheckConfig(args).returnconf()
        INPUT = "ls"
        return self.assertEqual(sec.check_secure(INPUT, userconf)[0], 1)

    def test_06_checksecure_sudo_command(self):
        """ U06 | quoted text should not be forbidden """
        INPUT = "sudo ls"
        return self.assertEqual(sec.check_secure(INPUT, self.userconf)[0], 1)

    def test_07_checksecure_notallowed_command(self):
        """ U07 | forbidden command, should return 1 """
        args = self.args + ["--allowed=['ls']"]
        userconf = CheckConfig(args).returnconf()
        INPUT = "ll"
        return self.assertEqual(sec.check_secure(INPUT, userconf)[0], 1)

    def test_08_checkpath_notallowed_path(self):
        """ U08 | forbidden command, should return 1 """
        args = self.args + ["--path=['/home', '/var']"]
        userconf = CheckConfig(args).returnconf()
        INPUT = "cd /tmp"
        return self.assertEqual(sec.check_path(INPUT, userconf)[0], 1)

    def test_09_checkpath_notallowed_path_completion(self):
        """ U09 | forbidden command, should return 1 """
        args = self.args + ["--path=['/home', '/var']"]
        userconf = CheckConfig(args).returnconf()
        INPUT = "cd /tmp/"
        return self.assertEqual(sec.check_path(INPUT,
                                               userconf,
                                               completion=1)[0], 1)

    def test_10_checkpath_dollarparenthesis(self):
        """ U10 | when $() is allowed, return 0 if path allowed """
        args = self.args + ["--forbidden=[';', '&', '|','`','>','<', '${']"]
        userconf = CheckConfig(args).returnconf()
        INPUT = "echo $(echo aze)"
        return self.assertEqual(sec.check_path(INPUT, userconf)[0], 0)

    def test_11_checkconfig_configoverwrite(self):
        """ U12 | forbid ';', then check_secure should return 1 """
        args = ['--config=%s/etc/lshell.conf' % TOPDIR, '--strict=123']
        userconf = CheckConfig(args).returnconf()
        return self.assertEqual(userconf['strict'], 123)

    def test_12_overssh(self):
        """ U12 | command over ssh """
        args = self.args + ["--overssh=['exit']", '-c exit']
        os.environ['SSH_CLIENT'] = '8.8.8.8 36000 22'
        if 'SSH_TTY' in os.environ:
            os.environ.pop('SSH_TTY')
        with self.assertRaises(SystemExit) as cm:
            CheckConfig(args).returnconf()
        return self.assertEqual(cm.exception.code, 0)

    def test_13_multiple_aliases_with_separator(self):
        """ U13 | multiple aliases using &&, || and ; separators """
        # enable &, | and ; characters
        aliases = {'foo': 'foo -l', 'bar': 'open'}
        INPUT = "foo; fooo  ;bar&&foo  &&   foo | bar||bar   ||     foo"
        return self.assertEqual(get_aliases(INPUT, aliases),
                                ' foo -l; fooo  ; open&& foo -l  '
                                '&& foo -l | open|| open   || foo -l')

    def test_14_sudo_all_commands_expansion(self):
        """ U14 | sudo_commands set to 'all' is equal to allowed variable """
        args = self.args + ["--sudo_commands=all"]
        userconf = CheckConfig(args).returnconf()
        # exclude internal and sudo(8) commands
        exclude = builtins_list + ['sudo']
        allowed = [x for x in userconf['allowed'] if x not in exclude]
        # sort lists to compare
        userconf['sudo_commands'].sort()
        allowed.sort()
        return self.assertEqual(allowed, userconf['sudo_commands'])

    def test_15_allowed_ld_preload_cmd(self):
        """ U15 | all allowed commands should be prepended with LD_PRELOAD """
        args = self.args + ["--allowed=['echo','export']"]
        userconf = CheckConfig(args).returnconf()
        # sort lists to compare
        return self.assertEqual(userconf['aliases']['echo'],
                                'LD_PRELOAD=%s echo' % userconf['path_noexec'])

    def test_16_allowed_ld_preload_builtin(self):
        """ U16 | builtin commands should NOT be prepended with LD_PRELOAD """
        args = self.args + ["--allowed=['echo','export']"]
        userconf = CheckConfig(args).returnconf()
        # verify that export is not automatically added to the aliases (i.e.
        # prepended with LD_PRELOAD)
        return self.assertNotIn('export', userconf['aliases'])

    def test_17_allowed_exec_cmd(self):
        """ U17 | allowed_shell_escape should NOT be prepended with LD_PRELOAD
            The command should not be added to the aliases variable
        """
        args = self.args + ["--allowed_shell_escape=['echo']"]
        userconf = CheckConfig(args).returnconf()
        # sort lists to compare
        return self.assertNotIn('echo', userconf['aliases'])

    def test_18_forbidden_environment(self):
        """ U18 | unsafe environment are forbidden
        """
        INPUT = 'export LD_PRELOAD=/lib64/ld-2.21.so'
        args = INPUT
        retcode = builtins.export(args)[0]
        return self.assertEqual(retcode, 1)

    def test_19_allowed_environment(self):
        """ U19 | other environment are accepted
        """
        INPUT = 'export MY_PROJECT_VERSION=43'
        args = INPUT
        retcode = builtins.export(args)[0]
        return self.assertEqual(retcode, 0)

    def test_20_winscp_allowed_commands(self):
        """ U20 | when winscp is enabled, new allowed commands are automatically
            added (see man).
        """
        args = self.args + ["--allowed=[]", "--winscp=1"]
        userconf = CheckConfig(args).returnconf()
        # sort lists to compare, except 'export'
        exclude = list(set(builtins_list) - set(['export']))
        expected = exclude + ['scp', 'env', 'pwd', 'groups',
                              'unset', 'unalias']
        expected.sort()
        allowed = userconf['allowed']
        allowed.sort()
        return self.assertEqual(allowed, expected)

    def test_21_winscp_allowed_semicolon(self):
        """ U21 | when winscp is enabled, use of semicolon is allowed """
        args = self.args + ["--forbidden=[';']", "--winscp=1"]
        userconf = CheckConfig(args).returnconf()
        # sort lists to compare
        return self.assertNotIn(';', userconf['forbidden'])

    def test_22_prompt_short_0(self):
        """ U22 | short_prompt = 0 should show dir compared to home dir """
        expected = '%s:~/foo$ ' % getuser()
        args = self.args + ['--prompt_short=0']
        userconf = CheckConfig(args).returnconf()
        currentpath = "%s/foo" % userconf['home_path']
        prompt = updateprompt(currentpath, userconf)
        # sort lists to compare
        return self.assertEqual(prompt, expected)

    def test_23_prompt_short_1(self):
        """ U23 | short_prompt = 1 should show only current dir """
        expected = '%s: foo$ ' % getuser()
        args = self.args + ['--prompt_short=1']
        userconf = CheckConfig(args).returnconf()
        currentpath = "%s/foo" % userconf['home_path']
        prompt = updateprompt(currentpath, userconf)
        # sort lists to compare
        return self.assertEqual(prompt, expected)

    def test_24_prompt_short_2(self):
        """ U24 | short_prompt = 2 should show full dir path """
        expected = '%s: %s$ ' % (getuser(), os.getcwd())
        args = self.args + ['--prompt_short=2']
        userconf = CheckConfig(args).returnconf()
        currentpath = "%s/foo" % userconf['home_path']
        prompt = updateprompt(currentpath, userconf)
        # sort lists to compare
        return self.assertEqual(prompt, expected)

    def test_25_disable_ld_preload(self):
        """ U25 | empty path_noexec should disable LD_PRELOAD """
        args = self.args + ["--allowed=['echo','export']", "--path_noexec=''"]
        userconf = CheckConfig(args).returnconf()
        # verify that no alias was created containing LD_PRELOAD
        return self.assertNotIn('echo', userconf['aliases'])

    def test_26_checksecure_quoted_command(self):
        """ U26 | quoted command should be parsed """
        INPUT = 'echo 1 && "bash"'
        return self.assertEqual(sec.check_secure(INPUT, self.userconf)[0], 1)

    def test_27_checksecure_quoted_command(self):
        """ U27 | quoted command should be parsed """
        INPUT = '"bash" && echo 1'
        return self.assertEqual(sec.check_secure(INPUT, self.userconf)[0], 1)

    def test_28_checksecure_quoted_command(self):
        """ U28 | quoted command should be parsed """
        INPUT = "echo'/1.sh'"
        return self.assertEqual(sec.check_secure(INPUT, self.userconf)[0], 1)

    def test_29_checkpath_no_shell_injection(self):
        """ U29 | check_path wildcard expansion must NOT execute a shell.
            A path token carrying a command substitution (no spaces, so it
            survives the operator split) previously reached a shell=True call
            and ran. Assert the marker command never runs.
        """
        import tempfile
        marker = os.path.join(tempfile.gettempdir(),
                              "lshell_pwned_%s" % os.getpid())
        if os.path.exists(marker):
            os.remove(marker)
        # $IFS supplies the space between "touch" and the path with no literal
        # space in the token, so check_path keeps it as a single item.
        INPUT = "ls x$(touch$IFS%s)y" % marker
        sec.check_path(INPUT, self.userconf)
        pwned = os.path.exists(marker)
        if pwned:
            os.remove(marker)
        return self.assertFalse(pwned)

    def test_30_checkpath_unset_var_still_blocks(self):
        """ U30 | an unset variable must expand to empty (shell parity) so a
            forbidden absolute path is still caught after the shell-free rewrite.
        """
        INPUT = 'cat "$undefined_var"/etc/passwd'
        return self.assertEqual(sec.check_path(INPUT, self.userconf)[0], 1)

    def test_31_scp_injection_blocked_over_ssh(self):
        """ U31 | scp over ssh carrying a shell-injection tail must be blocked
            before exec_cmd is ever reached. Both paths sit inside the user's
            home so check_path passes; only the new check_secure guard in the
            scp branch stops the ';id' tail. Fails on the pre-fix code (the raw
            string reaches exec_cmd).
        """
        from lshell import utils
        home = os.environ['HOME']
        inj = "scp -t %s ; id" % os.path.join(home, 'x')
        args = self.args + ["--overssh=['scp']", "--scp=1", "-c", inj]
        os.environ['SSH_CLIENT'] = '8.8.8.8 36000 22'
        os.environ.pop('SSH_TTY', None)
        exec_calls = []
        orig = utils.exec_cmd
        utils.exec_cmd = lambda cmd, conf=None: exec_calls.append(cmd) or 0
        try:
            with self.assertRaises(SystemExit):
                CheckConfig(args).returnconf()
        finally:
            utils.exec_cmd = orig
            os.environ.pop('SSH_CLIENT', None)
        # the injected string must never have reached the shell
        return self.assertEqual(exec_calls, [])

    def test_32_scp_legit_passes_over_ssh(self):
        """ U32 | a legitimate scp upload carries no shell metacharacters, so
            the new guard passes it through to exec_cmd unchanged.
        """
        from lshell import utils
        home = os.environ['HOME']
        legit = "scp -t %s" % os.path.join(home, 'x')
        args = self.args + ["--overssh=['scp']", "--scp=1", "-c", legit]
        os.environ['SSH_CLIENT'] = '8.8.8.8 36000 22'
        os.environ.pop('SSH_TTY', None)
        exec_calls = []
        orig = utils.exec_cmd
        utils.exec_cmd = lambda cmd, conf=None: exec_calls.append(cmd) or 0
        try:
            with self.assertRaises(SystemExit) as cm:
                CheckConfig(args).returnconf()
        finally:
            utils.exec_cmd = orig
            os.environ.pop('SSH_CLIENT', None)
        self.assertEqual(exec_calls, [legit])
        return self.assertEqual(cm.exception.code, 0)

    def test_33_noexec_strict_fail_closed(self):
        """ U33 | with path_noexec_strict set and no noexec library resolvable,
            lshell must refuse to start rather than confine unprotected.
        """
        from lshell import variables
        saved = variables.sudo_noexec_libs
        variables.sudo_noexec_libs = []  # simulate the library being absent
        args = self.args + ["--allowed=['echo']", "--path_noexec_strict=1"]
        try:
            with self.assertRaises(SystemExit) as cm:
                CheckConfig(args).returnconf()
        finally:
            variables.sudo_noexec_libs = saved
        return self.assertEqual(cm.exception.code, 2)

    def test_34_sanitize_strips_ld_preload(self):
        """ U34 | an inherited LD_PRELOAD is stripped from the environment at
            entry (so it cannot shadow the noexec backstop) while PATH is kept.
        """
        os.environ['LD_PRELOAD'] = '/tmp/evil.so'
        saved_path = os.environ.get('PATH', '')
        CheckConfig(self.args).returnconf()
        ld_gone = 'LD_PRELOAD' not in os.environ
        path_kept = saved_path in os.environ.get('PATH', '')
        return self.assertTrue(ld_gone and path_kept)

    def test_35_checkpath_wildcard_dotdot_traversal_blocked(self):
        """ U35 | dotdot obfuscated with shell wildcards must be blocked. The
            command runs through /bin/sh, which expands '.*.', '.?' and '.*'
            to '..'; check_path must resolve them the same way instead of
            treating the literal as an in-home path. Fails on the pre-fix code
            (check_path returned 0/allowed for the obfuscated forms).
        """
        import tempfile
        home = tempfile.mkdtemp()
        deep = os.path.join(home, 'a', 'b')
        os.makedirs(deep)
        args = self.args + ["--path=['%s']" % home]
        userconf = CheckConfig(args).returnconf()
        cwd = os.getcwd()
        os.chdir(deep)
        try:
            for token in ('.*./.*./.*./etc/passwd',
                          '.?/.?/.?/etc/passwd',
                          '.[.]/.[.]/.[.]/etc/passwd',
                          '../../../etc/passwd'):
                rc = sec.check_path('ls -l %s' % token, userconf)[0]
                self.assertEqual(rc, 1,
                                 "traversal not blocked: %s" % token)
        finally:
            os.chdir(cwd)
        return None

    def test_36_checkpath_legit_home_wildcard_allowed(self):
        """ U36 | a legitimate in-home wildcard path must still resolve and
            pass -- the dotdot-traversal guard must not over-block ordinary
            globs that stay inside the allowed tree.
        """
        import tempfile
        home = tempfile.mkdtemp()
        os.makedirs(os.path.join(home, 'docs'))
        open(os.path.join(home, 'docs', 'file.txt'), 'w').close()
        args = self.args + ["--path=['%s']" % home]
        userconf = CheckConfig(args).returnconf()
        cwd = os.getcwd()
        os.chdir(home)
        try:
            rc = sec.check_path('ls -l doc*/file.txt', userconf)[0]
        finally:
            os.chdir(cwd)
        return self.assertEqual(rc, 0)

    def test_37_max_processes_caps_child_rlimit(self):
        """ U37 | max_processes must cap the child's RLIMIT_NPROC soft limit.
            The child reads its own limit and exits 0 only when it matches the
            configured cap. No fork bomb is spawned -- the mechanism (setrlimit
            in the preexec_fn) is asserted directly. Fails on the pre-fix code
            (the limit was never applied, so it stayed at the inherited value).
            RLIMIT_NPROC counts every task the real UID already holds, so the
            cap is set above the current load (child can still fork) yet below
            the inherited ceiling (proving the limit is lowered and applied).
        """
        import resource
        from lshell import utils
        soft, _hard = resource.getrlimit(resource.RLIMIT_NPROC)
        # numeric /proc entries approximate the host's task count; a wide margin
        # covers threads that top-level /proc does not list
        approx_tasks = len([p for p in os.listdir("/proc") if p.isdigit()])
        cap = approx_tasks + 5000
        if soft != resource.RLIM_INFINITY and cap >= soft:
            self.skipTest("runner RLIMIT_NPROC ceiling too low for a lowering test")
        check = (
            "python3 -c \"import resource,sys;"
            "sys.exit(0 if resource.getrlimit(resource.RLIMIT_NPROC)[0]==%d"
            " else 1)\"" % cap
        )
        rc = utils.exec_cmd(check, {"max_processes": cap})
        return self.assertEqual(rc, 0)

    def test_38_max_processes_disabled_leaves_rlimit(self):
        """ U38 | max_processes = 0 (default) must NOT touch the child's
            RLIMIT_NPROC -- the child inherits the parent's soft limit unchanged.
        """
        import resource
        from lshell import utils
        parent_soft = resource.getrlimit(resource.RLIMIT_NPROC)[0]
        check = (
            "python3 -c \"import resource,sys;"
            "sys.exit(0 if resource.getrlimit(resource.RLIMIT_NPROC)[0]==%d"
            " else 1)\"" % parent_soft
        )
        rc = utils.exec_cmd(check, {"max_processes": 0})
        return self.assertEqual(rc, 0)

    def test_39_command_timeout_kills_long_command(self):
        """ U39 | command_timeout must kill a command that outruns it and return
            the conventional timeout exit code (124), well before the command's
            natural end. A finishing-early elapsed check proves the kill fired.
        """
        import time
        from lshell import utils
        start = time.time()
        rc = utils.exec_cmd("sleep 10", {"command_timeout": 1})
        elapsed = time.time() - start
        self.assertEqual(rc, 124)
        return self.assertLess(elapsed, 8)

    def test_40_command_timeout_disabled_no_change(self):
        """ U40 | with both controls disabled (0/0) behaviour is unchanged: a
            short command returns its real exit code, and a command that
            completes within an armed timeout is NOT killed (real code, not 124).
        """
        from lshell import utils
        # both disabled -- real return codes pass through
        self.assertEqual(utils.exec_cmd("true", {"command_timeout": 0,
                                                 "max_processes": 0}), 0)
        self.assertEqual(utils.exec_cmd("false"), 1)
        # completes within an armed timeout -> real code, not the 124 timeout
        return self.assertEqual(utils.exec_cmd("true", {"command_timeout": 5}), 0)

    def test_41_source_ip_captured_from_ssh_env(self):
        """ U41 | the SSH client address is captured once at session start from
            SSH_CONNECTION (first token) so security log lines can anchor on it.
        """
        os.environ.pop('SSH_CLIENT', None)
        os.environ['SSH_CONNECTION'] = '203.0.113.7 40000 10.0.0.1 22'
        try:
            conf = CheckConfig(self.args).returnconf()
            self.assertEqual(conf['source_ip'], '203.0.113.7')
        finally:
            os.environ.pop('SSH_CONNECTION', None)

    def test_42_source_ip_fallback_dash_without_ssh(self):
        """ U42 | with no SSH connection (local su/login) the captured address
            falls back to the literal '-' so the log token is always present.
        """
        os.environ.pop('SSH_CLIENT', None)
        os.environ.pop('SSH_CONNECTION', None)
        conf = CheckConfig(self.args).returnconf()
        return self.assertEqual(conf['source_ip'], '-')

    def test_43_forbidden_log_line_carries_ip_suffix(self):
        """ U43 | a forbidden command emits a log line ending in ' from <ip>' so
            the fail2ban contract is anchorable.
        """
        import logging
        args = self.args + ["--allowed=['ls']"]
        userconf = CheckConfig(args).returnconf()
        userconf['quiet'] = 0
        userconf['source_ip'] = '198.51.100.9'
        captured = []

        class _Cap(logging.Handler):
            def emit(self, record):
                captured.append(record.getMessage())

        userconf['logpath'].addHandler(_Cap())
        sec.check_secure("ll", userconf)
        return self.assertTrue(
            any(m.startswith("*** forbidden") and m.endswith(" from 198.51.100.9")
                for m in captured),
            "no forbidden line carried the ' from <ip>' suffix: %s" % captured,
        )

    def test_44_timeout_kill_writes_logfile_with_ip(self):
        """ U44 | a command killed by command_timeout writes a logfile line (not
            just terminal stderr) carrying the source-ip suffix.
        """
        from lshell import utils

        class _StubLog:
            def __init__(self):
                self.msgs = []

            def critical(self, message):
                self.msgs.append(message)

        log = _StubLog()
        rc = utils.exec_cmd(
            "sleep 10",
            {"command_timeout": 1, "source_ip": "192.0.2.5", "logpath": log},
        )
        self.assertEqual(rc, 124)
        return self.assertTrue(
            any("command_timeout" in m and m.endswith(" from 192.0.2.5")
                for m in log.msgs),
            "timeout kill did not log an ip-anchored line: %s" % log.msgs,
        )

    def test_45_process_limit_hit_logs_and_reraises(self):
        """ U45 | when the fork is denied (EAGAIN, the RLIMIT_NPROC ceiling) the
            event is logged with the ip suffix and returns 1; any other OSError
            is re-raised unchanged.
        """
        import errno
        from lshell import utils

        class _StubLog:
            def __init__(self):
                self.msgs = []

            def critical(self, message):
                self.msgs.append(message)

        orig_popen = utils.subprocess.Popen

        def _eagain(*a, **k):
            raise BlockingIOError(errno.EAGAIN, "Resource temporarily unavailable")

        def _enoent(*a, **k):
            raise OSError(errno.ENOENT, "No such file or directory")

        try:
            log = _StubLog()
            utils.subprocess.Popen = _eagain
            rc = utils.exec_cmd(
                "true",
                {"max_processes": 500, "source_ip": "192.0.2.9", "logpath": log},
            )
            self.assertEqual(rc, 1)
            self.assertTrue(
                any("process limit reached" in m and m.endswith(" from 192.0.2.9")
                    for m in log.msgs),
                "process-limit hit was not logged: %s" % log.msgs,
            )
            utils.subprocess.Popen = _enoent
            with self.assertRaises(OSError):
                utils.exec_cmd("true", {"max_processes": 500})
        finally:
            utils.subprocess.Popen = orig_popen

    def test_46_forbidden_sftp_log_line_carries_ip_suffix(self):
        """ U46 | a forbidden SFTP connection logs a line ending in ' from <ip>',
            the same anchor class as the scp/over-ssh forbidden lines.
        """
        import logging
        cc = CheckConfig(self.args)
        cc.conf["ssh"] = "/usr/lib/openssh/sftp-server"
        cc.conf["sftp"] = 0
        cc.conf["source_ip"] = "203.0.113.11"
        captured = []

        class _Cap(logging.Handler):
            def emit(self, record):
                captured.append(record.getMessage())

        cc.log.addHandler(_Cap())
        os.environ["SSH_CLIENT"] = "203.0.113.11 40000 22"
        os.environ.pop("SSH_TTY", None)
        os.environ.pop("SSH_CONNECTION", None)
        try:
            with self.assertRaises(SystemExit):
                cc.check_scp_sftp()
        finally:
            os.environ.pop("SSH_CLIENT", None)
        return self.assertTrue(
            any(m == "*** forbidden SFTP connection from 203.0.113.11"
                for m in captured),
            "forbidden SFTP line missing ip suffix: %s" % captured,
        )

    def test_47_default_configfile_linux_any_prefix(self):
        """ U47 | on Linux the default config file is /etc/lshell.conf
            whether the interpreter prefix is /usr or a compiled /usr/local.
        """
        from lshell.variables import default_configfile
        for prefix in ("/usr", "/usr/local", "/opt/python3.13"):
            self.assertEqual(
                default_configfile("linux", prefix), "/etc/lshell.conf",
                "wrong default config path for prefix %s" % prefix,
            )

    def test_48_default_configfile_bsd_follows_prefix(self):
        """ U48 | on *BSD the default config file follows the interpreter
            prefix, and a /usr prefix still resolves to /etc.
        """
        from lshell.variables import default_configfile
        self.assertEqual(
            default_configfile("freebsd14", "/usr/local"),
            "/usr/local/etc/lshell.conf",
        )
        self.assertEqual(
            default_configfile("openbsd7", "/usr/pkg"),
            "/usr/pkg/etc/lshell.conf",
        )
        self.assertEqual(
            default_configfile("freebsd14", "/usr"), "/etc/lshell.conf"
        )

    def test_49_default_configfile_module_constant(self):
        """ U49 | the module-level default is derived from the running
            interpreter through the same helper.
        """
        from lshell import variables
        self.assertEqual(variables.configfile, variables.default_configfile())


    def _user_conf(self, name, *extra):
        """Build a CheckConfig as the given account (log disabled)."""
        from unittest import mock
        args = self.args + ["--loglevel=0"] + list(extra)
        with mock.patch("lshell.checkconfig.getuser", return_value=name):
            return CheckConfig(args).returnconf()

    def test_50_path_expands_username(self):
        """ U50 | %u in path resolves to the account's own directory only """
        import tempfile
        base = os.path.realpath(tempfile.mkdtemp())
        for name in ("alice", "bob"):
            os.makedirs(os.path.join(base, name))
        userconf = self._user_conf("alice", "--path=['%s/%%u/']" % base)
        self.assertIn(os.path.join(base, "alice") + "/.*|", userconf["path"][0])
        self.assertNotIn("bob", userconf["path"][0])
        cwd = os.getcwd()
        try:
            self.assertEqual(
                sec.check_path("ls %s/alice/x" % base, userconf)[0], 0)
            self.assertEqual(
                sec.check_path("ls %s/bob/x" % base, userconf)[0], 1)
        finally:
            os.chdir(cwd)

    def test_51_path_plus_minus_expand_username(self):
        """ U51 | %u is expanded in the +/- path edits too """
        import tempfile
        base = os.path.realpath(tempfile.mkdtemp())
        os.makedirs(os.path.join(base, "alice", "secret"))
        userconf = self._user_conf(
            "alice", "--path=['%s'] - ['%s/%%u/secret']" % (base, base))
        self.assertIn(os.path.join(base, "alice", "secret") + "/.*|",
                      userconf["path"][1])
        userconf = self._user_conf(
            "alice", "--path=['%s'] + ['%s/%%u']" % (base, base))
        self.assertIn(os.path.join(base, "alice") + "/.*|", userconf["path"][0])

    def test_52_env_path_expands_username(self):
        """ U52 | %u in env_path becomes a PATH entry for that account """
        saved = os.environ["PATH"]
        try:
            userconf = self._user_conf("alice", "--env_path=':/opt/bin/%u'")
            self.assertEqual(userconf["env_path"], ":/opt/bin/alice")
            self.assertTrue(os.environ["PATH"].endswith(":/opt/bin/alice"))
        finally:
            os.environ["PATH"] = saved

    def test_53_allowed_cmd_path_expands_username(self):
        """ U53 | %u in allowed_cmd_path exposes that account's directory,
            and an account without one is skipped rather than crashing.
        """
        import tempfile
        base = os.path.realpath(tempfile.mkdtemp())
        mine = os.path.join(base, "alice")
        os.makedirs(mine)
        tool = os.path.join(mine, "mytool")
        with open(tool, "w") as fh:
            fh.write("#!/bin/sh\n")
        os.chmod(tool, 0o755)
        saved = os.environ["PATH"]
        try:
            userconf = self._user_conf(
                "alice", "--allowed_cmd_path=['%s/%%u']" % base)
            self.assertIn("mytool", userconf["allowed"])
            userconf = self._user_conf(
                "carol", "--allowed_cmd_path=['%s/%%u']" % base)
            self.assertNotIn("mytool", userconf["allowed"])
        finally:
            os.environ["PATH"] = saved

    def test_54_hostile_username_never_widens(self):
        """ U54 | an account name carrying a separator, glob, regex, list or
            dot-dot character is refused instead of reshaping a pattern.
        """
        import tempfile
        base = os.path.realpath(tempfile.mkdtemp())
        os.makedirs(os.path.join(base, "alice"))
        saved = os.environ["PATH"]
        hostile = ("*", "a*", "a?", "[a-z]", "a/b", "../etc", "..", "a..b",
                   "alice/..", "a:b", "-x", "a b", "a+b", "a|b", "")
        try:
            for name in hostile:
                for opt in ("--path=['%s/%%u/']" % base,
                            "--path=['%s'] - ['%s/%%u/']" % (base, base),
                            "--path=['%s'] + ['%s/%%u/']" % (base, base),
                            "--env_path=':/opt/bin/%u'",
                            "--allowed_cmd_path=['%s/%%u']" % base):
                    with self.assertRaises(SystemExit, msg=(name, opt)):
                        self._user_conf(name, opt)
        finally:
            os.environ["PATH"] = saved

    def test_55_unsafe_username_without_percent_u_unaffected(self):
        """ U55 | a configuration that never uses %u is untouched by the
            account-name check.
        """
        userconf = self._user_conf("a*b", "--path=['/tmp']")
        self.assertIn("/tmp", userconf["path"][0])


    def test_56_every_source_compiles_warning_free(self):
        """ U56 | every python source in the tree compiles with warnings
            promoted to errors, so an invalid escape sequence (a SyntaxWarning
            today, a SyntaxError in a future Python) cannot return.
        """
        import warnings
        files = []
        for sub in ("lshell", "bin", "test"):
            for dirpath, _dirs, names in os.walk(os.path.join(TOPDIR, sub)):
                if "__pycache__" in dirpath:
                    continue
                for name in names:
                    path = os.path.join(dirpath, name)
                    if name.endswith(".py"):
                        files.append(path)
                    elif sub == "bin":
                        with open(path, "rb") as fh:
                            if b"python" in fh.readline():
                                files.append(path)
        self.assertTrue(files)
        for path in files:
            with open(path, "rb") as fh:
                source = fh.read()
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                try:
                    compile(source, path, "exec")
                except (SyntaxWarning, DeprecationWarning,
                        SyntaxError) as exc:
                    self.fail("%s: %s" % (path, exc))


if __name__ == "__main__":
    unittest.main()
