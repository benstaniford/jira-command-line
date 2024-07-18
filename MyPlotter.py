import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import os
from MyJiraLog import MyJiraLog

class MyPlotter:
    def __init__(self, data_file=None):
        self.log = MyJiraLog()
        self.data_file = self.log.get_log() if data_file is None else data_file
        self.created_data = data_file is None
        self.df = pd.read_csv(self.data_file)
        self.df['Time'] = pd.to_datetime(self.df['Time'], format='%d/%m/%Y %H:%M:%S')

    def __del__(self):
        if self.created_data:
            self.df = None
            os.unlink(self.data_file)

    def sprint_by_person(self):
        self.df = self.df.sort_values(by=['Assignee', 'Time'])
        fig, ax = plt.subplots(figsize=(15, 10))
        assignees = self.df['Assignee'].unique()
        issues = self.df[['Issue', 'Issue Summary']].drop_duplicates()
        colors = plt.cm.rainbow(np.linspace(0, 1, len(issues)))
        added_to_legend = set()
        
        # Plot each person's timetable showing the issue they are working on as colored dots
        for i, assignee in enumerate(assignees):
            assignee_data = self.df[self.df['Assignee'] == assignee]
            color_index = 0
            for _, issue in issues.iterrows():
                issue_data = assignee_data[assignee_data['Issue'] == issue['Issue']]
                issue_summary = issue['Issue Summary']
                if len(issue_summary) > 20:
                    issue_summary = issue_summary[:20] + '...'
                label = f"{issue['Issue']}: {issue_summary}"
                if not issue_data.empty:
                    if issue['Issue'] not in added_to_legend:
                        ax.scatter(issue_data['Time'], [i] * len(issue_data), color=colors[color_index], label=label)
                        added_to_legend.add(issue['Issue'])
                    else:
                        ax.scatter(issue_data['Time'], [i] * len(issue_data), color=colors[color_index])
                color_index += 1
        
        # Formatting the x-axis to show date and time
        ax.xaxis.set_major_locator(mdates.DayLocator())  # Set major ticks to daily intervals
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%A %d'))  # Format the ticks as 'Day Date'
        plt.xticks(rotation=45)

        # Formatting the y-axis to show assignee names
        ax.set_yticks(range(len(assignees)))
        ax.set_yticklabels(assignees)
        
        # Adding labels and title
        ax.set_xlabel('Date and Time')
        ax.set_ylabel('Assignee')
        ax.set_title('Sprint by Person')
        
        # Position the legend below the plot
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=3)
        
        plt.tight_layout()
        plt.show()

    def sprint_by_item(self):
        fig, ax = plt.subplots(figsize=(15, 10))
        issues = self.df['Issue'].unique()
        assignees = self.df[['Assignee']].drop_duplicates()
        colors = plt.cm.rainbow(np.linspace(0, 1, len(assignees)))
        added_to_legend = set()
        
        # Plot each issue showing the assignee as colored dots
        for i, issue in enumerate(issues):
            issue_data = self.df[self.df['Issue'] == issue]
            color_index = 0
            for _, assignee in assignees.iterrows():
                assignee_data = issue_data[issue_data['Assignee'] == assignee['Assignee']]
                assignee_name = assignee['Assignee']
                if not assignee_data.empty:
                    if assignee_name not in added_to_legend:
                        ax.scatter(assignee_data['Time'], [i] * len(assignee_data), color=colors[color_index], label=assignee_name)
                        added_to_legend.add(assignee_name)
                    else:
                        ax.scatter(assignee_data['Time'], [i] * len(assignee_data), color=colors[color_index])
                color_index += 1
        
        # Formatting the x-axis to show date and time
        ax.xaxis.set_major_locator(mdates.DayLocator())  # Set major ticks to daily intervals
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%A %d'))  # Format the ticks as 'Day Date'
        plt.xticks(rotation=45)

        # Formatting the y-axis to show issue names
        ax.set_yticks(range(len(issues)))
        ax.set_yticklabels(issues)
        
        # Adding labels and title
        ax.set_xlabel('Date and Time')
        ax.set_ylabel('Issue')
        ax.set_title('Sprint by Item')
        
        # Position the legend below the plot
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=3)
        
        plt.tight_layout()
        plt.show()
