
lshell - limited shell  [![Build Status](https://travis-ci.org/ghantoos/lshell.svg?branch=master)](https://travis-ci.org/ghantoos/lshell)
======================

lshell is a shell coded in Python, that lets you restrict a user's environment to limited sets of commands, choose to enable/disable any command over SSH (e.g. SCP, SFTP, rsync, etc.), log user's commands, implement timing restriction, and more. 

Note: all the following information (and more) can be found in the manpage - ```man -l man/lshell.1``` or ```man lshell```)

Installation
----------------

> [!IMPORTANT]   
> This project has been forked from [ghantoos/lshell](https://github.com/ghantoos/lshell) as it has been abandoned by the original author. This fork is intended to keep the project alive and to add new features and bug fixes. The use of setup.py has been removed in favor of flit and the project has been updated to support Python 3.9+. `setup.py` has been removed as it utilized `distutils`, which is being deprecated from python and will be removed in Python 3.12. See [PEP 632](https://www.python.org/dev/peps/pep-0632/) for more information. As a result, the installation instructions have been updated to reflect the new installation process using flit and pip.


### 1. Install from source
  - <strong>on Linux:</strong>
    - Install dependencies, in this case python3 and python3-pip. You will also need the flit package (`pip3 install flit`). 
    - Then run the following commands:
	  ```bash
      git clone https://lab.quickbox.io/jmsolo/lshell.git /path/to/lshell
	  cd /path/to/lshell
	  flit build
	  python3 -m pip install dist/lshell-*.tar.gz
      ```


Configuration
------------------------

lshell.conf presents a template configuration file. See etc/lshell.conf or man file for more information.

A [default] profile is available for all users using lshell. Nevertheless,  you can create a [username] section or a [grp:groupname] section to customize users' preferences.

Order of priority when loading preferences is the following:

1. User configuration
2. Group configuration
3. Default configuration


The primary goal of lshell, is to be able to create shell accounts with ssh access and restrict their environment to a couple a needed commands and path.
 
For example User 'foo' and user 'bar' both belong to the 'users' UNIX group:

- User 'foo': 
       - must be able to access /usr and /var but not /usr/local
       - user all command in their PATH but 'su'
       - has a warning counter set to 5
       - has their home path set to '/home/users'

- User 'bar':
       - must be able to access /etc and /usr but not /usr/local
       - is allowed default commands plus 'ping' minus 'ls'
       - strictness is set to 1 (meaning he is not allowed to type an unknown command)

In this case, my configuration file will look something like this:

    # CONFIGURATION START
    [global]
    logpath         : /var/log/lshell/
    loglevel        : 2

    [default]
    allowed         : ['ls','pwd']
    forbidden       : [';', '&', '|'] 
    warning_counter : 2
    timer           : 0
    path            : ['/etc', '/usr']
    env_path        : ':/sbin:/usr/foo'
    scp             : 1 # or 0
    sftp            : 1 # or 0
    overssh         : ['rsync','ls']
    aliases         : {'ls':'ls --color=auto','ll':'ls -l'}

    [grp:users]
    warning_counter : 5
    overssh         : - ['ls']

    [foo]
    allowed         : 'all' - ['su']
    path            : ['/var', '/usr'] - ['/usr/local']
    home_path       : '/home/users'

    [bar]
    allowed         : + ['ping'] - ['ls'] 
    path            : - ['/usr/local']
    strict          : 1
    scpforce        : '/home/bar/uploads/'
    # CONFIGURATION END


Usage
--------------

To launch lshell, just execute lshell specifying the location of your configuration file:

    lshell --config /path/to/configuration/file

In order to log a user, you will have to add them to the lshell group:

    usermod -aG lshell username

In order to configure a user account to use lshell by default, you must: 

    chsh -s /usr/bin/lshell user_name
(You might need to insure that lshell is listed in /etc/shells)

After this, whichever method is used by the user to log into their account, they will end up using the limited shell you configured for them!


Contact
----------------
If you want to contribute to this project, please do not hesitate. Open an issue and, if possible, send a pull request.

Please use the original github for all requests: https://github.com/ghantoos/lshell/issues as I am only maintaining this fork to keep the project alive. I will occasionally check the issues/PR there and work on them **here** as time permits. I am not taking any credit for this project, nor am I offering any support for it. I am simply keeping it alive and making any necessary adjustments for those who wish to use it.

Cheers
