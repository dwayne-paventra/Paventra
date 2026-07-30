import os

# ==========================
# Project Paths
# ==========================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ASSETS_DIR = os.path.join(BASE_DIR, "assets")
DATA_DIR = os.path.join(BASE_DIR, "data")

LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")
ROAD_DATA = os.path.join(DATA_DIR, "roads.csv")

# ==========================
# Paventra Theme
# ==========================

PRIMARY_COLOR = "#005EA2"
SECONDARY_COLOR = "#4CAF50"
WARNING_COLOR = "#F9A825"
DANGER_COLOR = "#D32F2F"

APP_TITLE = "Paventra"

APP_SUBTITLE = "AI-Powered Road Intelligence"