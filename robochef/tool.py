import logging
import os
import json
from typing import List, Dict, Union

import requests
from mllm import RoleThread, Router
from PIL import Image
from rich.console import Console
from taskara import Task
from toolfuse import Tool, action

from .prompts import recipe_req_analyzer_prompt, \
                        conversion_analyzer_prompt, \
                        substitution_analyzer_prompt

router = Router.from_env()
console = Console()

logger = logging.getLogger(__name__)
logger.setLevel(int(os.getenv("LOG_LEVEL", logging.DEBUG)))

SPOONACULAR_API_KEY = os.environ['SPOONACULAR_API_KEY']
if not SPOONACULAR_API_KEY:
    print ("Please set your SPOONACULAR_API_KEY first.")
    raise

class RoboChefTool(Tool):
    """A semantic desktop replaces click actions with semantic description rather than coordinates"""

    def __init__(
        self, task: Task, data_path: str = "./.data"
    ) -> None:
        """
        Initialize the tool.

        Args:
            task: Agent task. Defaults to None.
            data_path (str, optional): Path to data. Defaults to "./.data".
        """
        super().__init__()

        self.data_path = data_path
        self.img_path = os.path.join(self.data_path, "images", task.id)
        os.makedirs(self.img_path, exist_ok=True)

        self.task = task

    @action
    def get_recipe_requirements(self, requirements: str) -> Dict[str, Union[str, List[str]]]:
        """
        This is the first step in finding a recipe. It takes a text describing what type of recipe the user wants and returns a structured breakdown of user requirements. The structured breakdown clarifies the food, diet, intolerances, include_ingredients and exclude_ingredients that the user wants in the recipe. This breakdown can then be used to search for suitable recipes.
        """
        thread = RoleThread()
        router = Router(preference=["gpt-4-turbo"])

        analyzer_msg = f"{recipe_req_analyzer_prompt} Here is the user requirement in plain English: {requirements}"
        thread.post(role="user", msg=analyzer_msg)

        response = router.chat(thread)
        requirements_breakdown = json.loads(response.msg.text)

        return {
            "food": requirements_breakdown["food"],
            "diet": requirements_breakdown["diet"],
            "intolerances": requirements_breakdown["intolerances"],
            "include_ingredients": requirements_breakdown["include_ingredients"],
            "exclude_ingredients": requirements_breakdown["exclude_ingredients"],
        }

    @action
    def search_recipe(self, requirements_breakdown: Dict[str, str]) -> str:
        """
        Searches for a recipe that meet the user's requirements. The user's requirements are provided as a structured dictionary with the following keys: food, diet, intolerances, include_ingredients, exclude_ingredients. Using this dictionary, this method queries the spoonacular recipe search api and returns the ID of a recipe that meets the requirements.
        """
        params = {'apiKey': SPOONACULAR_API_KEY, 'number': 1}
        if requirements_breakdown['food']: params['query'] = requirements_breakdown['food']
        if requirements_breakdown['diet']: params['diet'] = requirements_breakdown['diet']
        if requirements_breakdown['intolerances']:
            if type(requirements_breakdown['intolerances']) == list:
                params['intolerances'] = ','.join(requirements_breakdown['intolerances'])
            else:
                params['intolerances'] = requirements_breakdown['intolerances']
        if requirements_breakdown['include_ingredients']:
            if type(requirements_breakdown['include_ingredients']) == list:
                params['includeIngredients'] = ','.join(requirements_breakdown['include_ingredients'])
            else:
                params['includeIngredients'] =requirements_breakdown['include_ingredients']
        if requirements_breakdown['exclude_ingredients']:
            if type(requirements_breakdown['exclude_ingredients']) == list:
                params['excludeIngredients'] = ','.join(requirements_breakdown['exclude_ingredients'])
            else:
                params['excludeIngredients'] =requirements_breakdown['exclude_ingredients']

        search_recipe_api_url = "https://api.spoonacular.com/recipes/complexSearch"
        response = requests.get(search_recipe_api_url, params=params)
        if response.status_code != 200:
            raise Exception("Error searching recipes on Spoonacular")
        recipe = json.loads(response.text)
        recipe_id = recipe['results'][0]['id']
        return recipe_id

    @action
    def get_recipe_details(self, recipe_id: str) -> str:
        """
        Fetches the details of a recipe identified by the given recipe ID. The fetched details are contained in an image hosted in a recipe_card_url. Later, the recipe_card_url can be shown to the user.
        """
        params = {'apiKey': SPOONACULAR_API_KEY}
        get_recipe_card_api_url = f"https://api.spoonacular.com/recipes/{recipe_id}/card"
        recipe_card_response = requests.get(get_recipe_card_api_url, params=params)
        if recipe_card_response.status_code != 200:
            raise Exception("Error getting recipe card from Spoonacular")
        recipe_card = json.loads(recipe_card_response.text)
        recipe_card_url = recipe_card['url']
        return recipe_card_url

    @action
    def display_recipe_details(self, recipe_card_url: str) -> None:
        """Displays the details of a recipe using a recipe card available in the specified recipe_card_url."""
        img_content = requests.get(recipe_card_url, stream=True)
        if img_content.status_code != 200:
            raise Exception("Error loading recipe card image")
        img = Image.open(img_content.raw)
        img.show()
        return "Task Complete"

    @action
    def get_conversion_requirements(self, requirements: str) -> Dict[str, Union[str, List[str]]]:
        """
        Transforms the user request to covert ingredients from one unit to another from a plain English format to a structured format. It takes a text describing what the uer is trying to convert and returns a structured breakdown that clarifies the ingredient name, source amount, source unit and target unit for conversion. These details can then be used to perform the conversion.
        """
        thread = RoleThread()
        router = Router(preference=["gpt-4-turbo"])

        analyzer_msg = f"{conversion_analyzer_prompt} Here is the conversion requirement in plain English: {requirements}"
        thread.post(role="user", msg=analyzer_msg)

        response = router.chat(thread)
        requirements_breakdown = json.loads(response.msg.text)

        return {
            "ingredient_name": requirements_breakdown["ingredient_name"],
            "source_amount": requirements_breakdown["source_amount"],
            "source_unit": requirements_breakdown["source_unit"],
            "target_unit": requirements_breakdown["target_unit"],
        }

    @action
    def convert_ingredient_amounts(self, requirements_breakdown: Dict[str, str]) -> None:
        """Converts ingredient amount from one unit to another. It needs the conversion request to be in a structured format. Then, it can perform the conversion."""
        params = {'apiKey': SPOONACULAR_API_KEY}
        params['ingredientName'] = requirements_breakdown['ingredient_name']
        params['sourceAmount'] = requirements_breakdown['source_amount']
        params['sourceUnit'] = requirements_breakdown['source_unit']
        params['targetUnit'] = requirements_breakdown['target_unit']

        convert_amount_api_url = "https://api.spoonacular.com/recipes/convert"
        response = requests.get(convert_amount_api_url, params=params)
        if response.status_code != 200:
            raise Exception("Error converting amounts on Spoonacular")
        conversion = json.loads(response.text)
        conversion_answer = conversion['answer']
        return conversion_answer

    @action
    def get_substitute_requirements(self, requirements: str) -> Dict[str, Union[str, List[str]]]:
        """
        Transforms the user request to find ingredient substitutes from a plain English format to a structured format. It takes a text describing what the uer is trying to substitute and returns a structured breakdown that clarifies the ingredient name, which can then be used to search for substitutes.
        """
        thread = RoleThread()
        router = Router(preference=["gpt-4-turbo"])

        analyzer_msg = f"{substitution_analyzer_prompt} Here is the substitution requirement in plain English: {requirements}"
        thread.post(role="user", msg=analyzer_msg)

        response = router.chat(thread)
        requirements_breakdown = json.loads(response.msg.text)

        return {
            "ingredient_name": requirements_breakdown["ingredient_name"],
        }

    @action
    def get_ingredient_substitutes(self, requirements_breakdown: Dict[str, str]) -> None:
        """Find substitutes for a given ingredient. It needs the substitution request to be in a structured format. Then, it can find the substitutes."""
        params = {'apiKey': SPOONACULAR_API_KEY}
        params['ingredientName'] = requirements_breakdown['ingredient_name']

        substitute_api_url = "https://api.spoonacular.com/food/ingredients/substitutes"
        response = requests.get(substitute_api_url, params=params)
        if response.status_code != 200:
            raise Exception("Error finding substitutes from Spoonacular")
        conversion = json.loads(response.text)
        if conversion['status'] == 'success':
            conversion_answer = f"Substitutes for {params['ingredientName']}: "
            conversion_answer += ", ".join(conversion['substitutes'])
        else:
            conversion_answer = f"Spoonacular did not return any substitutes for {params['ingredientName']}"
        return conversion_answer

    @action
    def result(self, value: str) -> str:
        """Return a result to the user

        Args:
            value (str): Value to return

        Returns:
            str: Value returned
        """
        return value