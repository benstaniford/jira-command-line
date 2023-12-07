# jira-command-line
A command line Jira client

## How to install jira command line on windows
1. Install the latest 3.x Python from:
https://www.python.org/downloads/

2. Open a git4win bash terminal and check the version of python available is the native windows one you just installed:
$ python --version
Python 3.11.7

3. Install the python modules required:
pip install jira gitpython PyGithub windows-curses

4. Clone the jira command line repo:
git clone https://github.com/benstaniford/jira-command-line.git

5. Add the jira command to your .bashrc file:
`alias jira='python ~/dot-files/scripts/jira'`

6. Restart bash and run 'jira' to generate the template configuration

$ jira
```
Configuration file not found, generating template...
Please edit the configuration file and generate required PAT tokens for jira and github
Configuration file saved to: C:\Users\bstaniford\.jira-config\config.json
```

7. Generate PAT tokens and edit the configuration


