"""spark.cli.__main__ — Abilita ``python -m spark.cli``.

Equivalente a eseguire ``python spark_launcher.py`` dalla root.
"""
from spark.cli.main import main

if __name__ == "__main__":
    main()
