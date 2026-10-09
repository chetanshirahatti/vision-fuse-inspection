"""Shared application state: settings, recipes, inspector, history, PLC."""
from __future__ import annotations
import os, shutil
import cv2
from PySide6.QtCore import QObject, Signal
from core.recipe import Recipe, Roi, RecipeStore
from core.inspector import Inspector
from core.settings import Settings
from core.history import History
from core.imageio import read_image
from core.plc import PlcWorker

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RECIPE = "Fuse_80A_400A"


class AppContext(QObject):
    recipeChanged = Signal()
    resultReady = Signal(object, str)       # InspectionResult, source name
    historyChanged = Signal()

    def __init__(self, data_dir=None):
        super().__init__()
        self.data_dir = data_dir or os.path.join(APP_DIR, "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.settings_path = os.path.join(self.data_dir, "settings.json")
        self.settings = Settings.load(self.settings_path)
        self.store = RecipeStore(os.path.join(self.data_dir, "recipes"))
        self.history = History(os.path.join(self.data_dir, "history"))
        self.samples_dir = os.path.join(APP_DIR, "samples")
        self.recipe = self.master = self.inspector = None
        self.stats = dict(total=0, ok=0, nok=0)
        self._heal_recipes()
        self._seed_default()
        names = self.store.names()
        pick = self.settings.last_recipe if self.settings.last_recipe in names else (names[0] if names else None)
        if pick:
            self.load_recipe(pick)
        self.plc = PlcWorker(self.settings.modbus)
        self.plc.start()

    def _heal_recipes(self):
        """Remove recipes whose files are broken (e.g. missing master.png) so the app can start."""
        for n in self.store.names():
            try:
                self.store.load(n)
            except Exception:
                self.store.delete(n)

    def _seed_default(self):
        if self.store.names():
            return
        master = read_image(os.path.join(APP_DIR, "assets", "master.png"))
        if master is None:
            return
        r = Recipe(DEFAULT_RECIPE, [Roi("FUSE_80A", 255, 530, 352, 582, "80A"),
                                    Roi("FUSE_400A", 268, 1095, 392, 1146, "400A")])
        self.store.save(r, master)

    # ---- recipes ----
    def load_recipe(self, name):
        self.recipe, self.master = self.store.load(name)
        self.inspector = Inspector(self.recipe, self.master)
        self.inspector.max_side = self.settings.max_side
        self.settings.last_recipe = name
        self.save_settings()
        self.recipeChanged.emit()

    def save_recipe(self, recipe, master):
        self.store.save(recipe, master)
        self.load_recipe(recipe.name)

    def delete_recipe(self, name):
        self.store.delete(name)
        names = self.store.names()
        if self.recipe and self.recipe.name == name:
            self.recipe = self.master = self.inspector = None
            if names:
                self.load_recipe(names[0])
                return
        self.recipeChanged.emit()

    def save_thresholds(self):
        if self.recipe:
            self.store.save_json(self.recipe)

    def save_settings(self):
        self.settings.save(self.settings_path)
        if self.inspector:
            self.inspector.max_side = self.settings.max_side

    # ---- inspection ----
    def run_inspection(self, img, source="manual", log=True):
        res = self.inspector.inspect(img)
        ann = Inspector.annotate(res)
        self.stats["total"] += 1
        self.stats["ok" if res.status == "PASS" else "nok"] += 1
        if log:
            self.history.log(self.recipe.name, source, res, ann, self.settings.save_nok_images)
            self.historyChanged.emit()
        self.plc.publish(res.status, res.fail_mask)
        self.resultReady.emit(res, source)
        return res, ann

    def reset_stats(self):
        self.stats = dict(total=0, ok=0, nok=0)

    def shutdown(self):
        self.plc.stop()
