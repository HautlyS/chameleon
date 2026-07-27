"""Entry point for: python3 -m scripts.tui_app"""
from scripts.tui.app import ChameleonTUI


def main():
    app = ChameleonTUI()
    app.run()


if __name__ == "__main__":
    main()
