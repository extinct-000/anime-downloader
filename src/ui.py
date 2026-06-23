from rich.columns import Columns
from rich.console import Group, Console
from rich.panel import Panel
from rich.progress import Progress
from rich.text import Text
from rich.live import Live
import time

console: Console = Console()

content: Group = Group(
    Text("Hellsjflkasjdfslkdfja"),
    Text("o"),
    Text("worlds"),
)

layout = Columns(
    [Panel(content), Panel(content), Panel(content)], equal=True, expand=True
)

console.print(layout)
