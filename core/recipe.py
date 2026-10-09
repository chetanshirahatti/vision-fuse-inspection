"""Recipe = trained master image + list of ROIs + parameters (stored as master.png + recipe.json)."""
from __future__ import annotations
import json, os, re, shutil, datetime
from dataclasses import dataclass, field, asdict
import cv2
from core.imageio import read_image, write_image


@dataclass
class Roi:
    name: str
    x1: int
    y1: int
    x2: int
    y2: int
    expected: str = ""          # what the part should show, e.g. "80A"
    threshold: float = 0.80     # minimum match score to be OK

    @property
    def rect(self):
        return self.x1, self.y1, self.x2, self.y2


@dataclass
class Recipe:
    name: str
    rois: list = field(default_factory=list)
    search_pad: int = 14
    min_matches: int = 20
    created: str = ""
    updated: str = ""
    img_w: int = 0
    img_h: int = 0

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        d = dict(d)
        d["rois"] = [Roi(**r) for r in d.get("rois", [])]
        return Recipe(**{k: v for k, v in d.items() if k in Recipe.__dataclass_fields__})


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", name.strip()) or "recipe"


class RecipeStore:
    def __init__(self, root):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _dir(self, name):
        return os.path.join(self.root, safe_name(name))

    def names(self):
        return sorted(d for d in os.listdir(self.root)
                      if os.path.isfile(os.path.join(self.root, d, "recipe.json")))

    def load(self, name):
        d = self._dir(name)
        with open(os.path.join(d, "recipe.json"), "r", encoding="utf-8") as f:
            recipe = Recipe.from_dict(json.load(f))
        master = read_image(os.path.join(d, "master.png"))
        if master is None:
            raise FileNotFoundError("master.png missing for recipe " + name)
        return recipe, master

    def save(self, recipe: Recipe, master):
        d = self._dir(recipe.name)
        os.makedirs(d, exist_ok=True)
        recipe.created = recipe.created or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        recipe.img_h, recipe.img_w = master.shape[:2]
        write_image(os.path.join(d, "master.png"), master)
        self.save_json(recipe)

    def save_json(self, recipe: Recipe):
        d = self._dir(recipe.name)
        recipe.updated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(os.path.join(d, "recipe.json"), "w", encoding="utf-8") as f:
            json.dump(recipe.to_dict(), f, indent=2)

    def delete(self, name):
        shutil.rmtree(self._dir(name), ignore_errors=True)
