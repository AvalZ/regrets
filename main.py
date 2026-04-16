import typer

from engines.z3 import app as z3_app

app = typer.Typer(help="Generate strings that match (or don't match) regex constraints.")
app.add_typer(z3_app, name="z3")


if __name__ == '__main__':
    app()
