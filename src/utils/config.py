import json
import os
from pathlib import Path

class Config:
    def __init__(self):
        self.config_file = Path.home() / '.ytdownloader' / 'config.json'
        self.default_config = {
            'output_directory': str(Path.home() / 'Downloads'),
            'default_format': 'video',
        }
        self.load_config()

    def load_config(self):
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = self.default_config.copy()
            self.save_config()

    def save_config(self):
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)

    def get(self, key):
        return self.config.get(key, self.default_config.get(key))

    def set(self, key, value):
        self.config[key] = value
        self.save_config()