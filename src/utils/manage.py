import sys
if sys.path[0].endswith("utils"):
    sys.path[0] = sys.path[0][:-5]
from flask_migrate import Migrate,MigrateCommand
from utils.model import *
from flask_script import Manager
from flask import Flask

migrate = Migrate(app,db)
manager = Manager(app)
manager.add_command('db',MigrateCommand)

if __name__ == '__main__':
    manager.run()
