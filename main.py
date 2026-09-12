from pathlib import Path

import click
import uvicorn


@click.command()
@click.option("--reload", is_flag=True, default=False)
@click.option("--port", type=click.IntRange(1, 65535), default=8000)
def main(reload: bool, port: int) -> None:
    env_file = Path(__file__).resolve().parent / ".env"
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        reload=reload,
        port=port,
        env_file=env_file,
    )


if __name__ == "__main__":
    main()
