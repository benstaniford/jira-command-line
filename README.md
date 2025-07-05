# jira-command-line
A command line Jira client

## How to install jira command line on windows
1. Install the latest 3.11 Python from:
* https://www.python.org/downloads/
* Remember to click the "Add python to path" checkbox during the install
* Note: Python 3.12 doesn't seem to work at the moment because one of the pip modules doesn't support it properly and crashes
2. Open a git4win bash terminal and check the version of python available is the native windows one you just installed:
```
$ python --version
Python 3.11.7
```
3. Install the python modules required:
`pip install jira gitpython PyGithub windows-curses ttkthemes sv-ttk`
4. Clone the jira command line repo:
```
cd ~
git clone https://github.com/benstaniford/jira-command-line.git
```
5. Add the jira command to your .bashrc file:
* `alias jira='python ~/jira-command-line/jira'`
* Note: If it doesn't already exist, just create `%USERPROFILE%\.bashrc` and add the alias to it.
6. Restart bash and run `jira` to generate the template configuration
```
$ jira
Configuration file not found, generating template...
Please edit the configuration file and generate required PAT tokens for jira and github
Configuration file saved to: C:\Users\bstaniford\.jira-config\config.json
```
7. Generate PAT tokens for [Jira](https://id.atlassian.com/manage-profile/security/api-tokens) and [Github](https://github.com/settings/tokens) (Select github classic token and give it repo scope). Customise the configuration with the PAT tokens and your settings.
8. Re-run `jira` and you should now be able to use the command line tool.  Initial commands to try are 's' to see the current sprint and 'l' to see the backlog.
