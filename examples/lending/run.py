"""Run lending example: registers all host functions and starts web UI."""

from monty_workspace import Monty
from examples.lending.host_functions import register_all

monty = Monty(workspace_dir="examples/lending/codes")
register_all(monty)
monty.serve()
