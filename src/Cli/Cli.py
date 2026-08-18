import typer

app = typer.Typer()

@app.command()
def cli(url: str):
    print(url)


if __name__ == "__main__":
    app()
