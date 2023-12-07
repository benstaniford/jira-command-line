# jira-command-line
A command line Jira client

## How to install jira command line on windows
1. Install the latest 3.x Python from:
* https://www.python.org/downloads/
* Ensure the path to python.exe and its built in scripts folder is on your path in the windows environment variables settings.

2. Open a git4win bash terminal and check the version of python available is the native windows one you just installed:
```
$ python --version
Python 3.11.7
```

3. Install the python modules required:
`pip install jira gitpython PyGithub windows-curses`

4. Clone the jira command line repo:
```
cd ~
git clone https://github.com/benstaniford/jira-command-line.git
```

5. Add the jira command to your .bashrc file:
* `alias jira='python ~/jira-command-line/jira'`
* Note: If it doesn't already exist, just create %USERPROFILE%\.bashrc and add the alias to it.

6. Restart bash and run 'jira' to generate the template configuration
```
$ jira
Configuration file not found, generating template...
Please edit the configuration file and generate required PAT tokens for jira and github
Configuration file saved to: C:\Users\bstaniford\.jira-config\config.json
```

7. Generate PAT tokens for [Jira](https://id.atlassian.com/manage-profile/security/api-tokens) and [Github](https://github.com/settings/tokens) (Select github classic token). Customise the configuration with the PAT tokens and your settings.

