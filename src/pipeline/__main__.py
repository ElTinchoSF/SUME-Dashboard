"""
Main entry point for the pipeline package.

Allows running: python -m src.pipeline run --phase init-db
"""

from src.pipeline.run import main

if __name__ == "__main__":
    main()