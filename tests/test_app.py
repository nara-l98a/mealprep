import json
import tempfile
import unittest
from pathlib import Path
from mealprep.app import main

class MealprepTests(unittest.TestCase):
    def run_cli(self, root, *args):
        return main(["--data", str(root / "db.json"), *args])

    def test_recipe_plan_and_merged_shopping(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertEqual(self.run_cli(root, "add-recipe", "燕麦碗", "--servings", "2", "--ingredient", "燕麦:100:克"), 0)
            self.assertEqual(self.run_cli(root, "plan", "2025-01-06", "早餐", "燕麦碗", "--servings", "2"), 0)
            self.assertEqual(self.run_cli(root, "plan", "2025-01-07", "早餐", "燕麦碗", "--servings", "2"), 0)
            self.assertEqual(self.run_cli(root, "shopping-list", "2025-01-06", "2025-01-12"), 0)
            self.assertIn("燕麦: 200 克", __import__("subprocess").check_output(["python", "-m", "mealprep", "--data", str(root/"db.json"), "shopping-list", "2025-01-06", "2025-01-12"], text=True))

    def test_missing_recipe_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self.run_cli(Path(d), "plan", "2025-01-01", "午餐", "不存在"), 2)

    def test_invalid_date_and_quantity(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self.run_cli(Path(d), "plan", "bad", "午餐", "x"), 2)
            self.assertEqual(self.run_cli(Path(d), "add-ingredient", "盐", "0", "克"), 2)
            self.assertEqual(self.run_cli(Path(d), "add-ingredient", "盐", "nan", "克"), 2)
            self.assertEqual(self.run_cli(Path(d), "plan", "20250106", "午餐", "x"), 2)

    def test_duplicate_meal_and_blank_ingredient_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self.assertEqual(self.run_cli(root,"add-recipe","燕麦碗","--ingredient","燕麦:100:克"),0)
            self.assertEqual(self.run_cli(root,"plan","2025-01-06","早餐","燕麦碗"),0)
            self.assertEqual(self.run_cli(root,"plan","2025-01-06","早餐","燕麦碗"),2)
            self.assertEqual(len(json.loads((root/"db.json").read_text())["plans"]),1)
            self.assertEqual(self.run_cli(root,"add-ingredient"," ","2","个"),2)

    def test_validate_detects_broken_reference(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "db.json"
            path.write_text(json.dumps({"version": 1, "ingredients": [], "recipes": [], "plans": [{"date":"2025-01-01", "meal":"晚餐", "recipe":"缺失", "servings":1}]}), encoding="utf-8")
            self.assertEqual(self.run_cli(Path(d), "validate"), 1)

if __name__ == "__main__": unittest.main()
