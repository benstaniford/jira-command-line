from .base_command import BaseCommand
from ..MyPlotter import MyPlotter
import threading

class VisualizeCommand(BaseCommand):
    @property
    def shortcut(self):
        return "V"
    
    @property
    def description(self):
        return "visualise"
    
    def execute(self, ui, view, jira, **kwargs):
        try:
            visualisationOptions = { 'p': 'By person', 'i': 'By item' }
            selection = ui.prompt_with_choice_dictionary("Visualise sprint", visualisationOptions)
            time_period = ui.prompt_get_string("Enter time period in days (default 14 days)")
            if time_period == "":
                time_period = 14
            else:
                time_period = int(time_period)
            plotter = MyPlotter(data_file=None, time_period=time_period)
            if selection == 'By person':
                thread = threading.Thread(target=plotter.sprint_by_person)
                thread.start()
            elif selection == 'By item':
                thread = threading.Thread(target=plotter.sprint_by_item)
                thread.start()
        except Exception as e:
            ui.error("Visualise sprint", e)
        return False
