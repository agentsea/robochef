import json
import logging
import os
import time
import traceback
from typing import Final, List, Optional, Tuple, Type, Union

from agentdesk.device_v1 import Desktop
from devicebay import Device
from pydantic import BaseModel
from rich.console import Console
from rich.json import JSON
from skillpacks import EnvState
from skillpacks.server.models import V1ActionSelection
from surfkit.agent import TaskAgent
from taskara import Task, TaskStatus
from tenacity import before_sleep_log, retry, stop_after_attempt
from toolfuse.util import AgentUtils

from langchain.chains.base import Chain
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from .tool import RoboChefTool

logging.basicConfig(level=logging.INFO)
logger: Final = logging.getLogger(__name__)
logger.setLevel(int(os.getenv("LOG_LEVEL", str(logging.DEBUG))))

console = Console(force_terminal=True)


class RoboChefConfig(BaseModel):
    pass


class RoboChef(TaskAgent):
    """An AI agent that finds recipes and does other recipes-related tasks"""

    def solve_task(
        self,
        task: Task,
        device: Optional[Device] = None,
        max_steps: int = 30,
    ) -> Task:
        """Solve a task

        Args:
            task (Task): Task to solve.
            max_steps (int, optional): Max steps to try and solve. Defaults to 30.

        Returns:
            Task: The task
        """

        # Post a message to the task to let the user know the task is in progress
        task.post_message("assistant", f"Starting task '{task.description}'")

        # Create an instance of the RoboChef tool
        robochef = RoboChefTool(task=task)

        # Add standard agent utils to robochef
        robochef.merge(AgentUtils())

        # Get the json schema for the tool
        tools = robochef.json_schema()
        console.print("tools: ", style="purple")
        console.print(JSON.from_data(tools))

        # Start with a system prompt
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(
                    content=
                        "You are a helpful AI assistant which performs recipes related tasks."
                        f"Your available tools are {tools} "
                        "For each task I send you please return a raw JSON adhering to the following schema and with the correct action called. "
                        f"Schema: {V1ActionSelection.model_json_schema()} "
                        "Do not add any extra characters in your response. Just return the response in the correct json format. "
                        "Let me know when you are ready and I'll send you the first task."
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
        # Create the model and LangChain chain
        model = ChatOpenAI()
        chain = prompt | model

        # Initialize the thread messages exchanged with the LLM
        messages = []

        # The initial state is the task description itself.
        current_state = task.description

        # Loop to run actions
        for i in range(max_steps):
            console.print(f"-------step {i + 1}", style="green")

            try:
                current_state, done = self.take_action(robochef, task, messages, current_state, chain)
            except Exception as e:
                console.print(f"Error: {e}", style="red")
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.save()
                task.post_message("assistant", f"❗ Error taking action: {e}")
                return task

            if done:
                console.print("task is done", style="green")
                return task

            time.sleep(2)

        task.status = TaskStatus.FAILED
        task.save()
        task.post_message("assistant", "❗ Max steps reached without solving task")
        console.print("Reached max steps without solving task", style="red")

        return task

    @retry(
        stop=stop_after_attempt(5),
        before_sleep=before_sleep_log(logger, logging.INFO),
    )
    def take_action(
        self,
        robocheftool: RoboChefTool,
        task: Task,
        messages: List[Union[AIMessage, HumanMessage, SystemMessage]],
        current_state: dict,
        chain: Chain,
    ) -> Tuple[dict, bool]:
        """Take an action

        Args:
            robocheftool (RoboChefTool): Robo Chef tool
            task (str): Task to accomplish
            messages (LangChain messages): Complete history of conversation with the LLM
            current_state: The current state which is used to determine the next action
            chain: LangChain chain

        Returns:
            bool: Whether the task is complete
        """
        try:
            # Check to see if the task has been cancelled
            if task.remote:
                task.refresh()
            console.print("task status: ", task.status.value)
            if (
                task.status == TaskStatus.CANCELING
                or task.status == TaskStatus.CANCELED
            ):
                console.print(f"task is {task.status}", style="red")
                if task.status == TaskStatus.CANCELING:
                    task.status = TaskStatus.CANCELED
                    task.save()
                return current_state, True

            console.print("taking action...", style="white")

            # Craft the message asking the model for an action
            messages.append(HumanMessage(content=f"Your current task is {current_state}."))

            # Invoke the model to make the action selection
            response = chain.invoke(
                {
                    "messages": messages,
                }
            )

            # Add the model's response to the conversation thread
            messages.append(AIMessage(content=response.content))

            try:
                # Post to the user letting them know what the model selected
                selection = json.loads(response.content)
                if not selection:
                    raise ValueError("No action selection parsed")

                task.post_message("assistant", f"👁️ {selection['observation']}")
                task.post_message("assistant", f"💡 {selection['reason']}")
                console.print("action selection: ", style="white")
                console.print(selection)

                task.post_message(
                    "assistant",
                    f"▶️ Taking action '{selection['action']['name']}' with parameters: {selection['action']['parameters']}",
                )

            except Exception as e:
                console.print(f"Response failed to parse: {e}", style="red")
                raise

            # The agent will return 'result' if it believes it's finished
            if selection['action']['name'] == "result":
                console.print("final result: ", style="green")
                console.print(JSON.from_data(selection['action']['parameters']))
                task.post_message(
                    "assistant",
                    f"✅ I think the task is done, please review the result: {selection['action']['parameters']['value']}",
                )
                task.status = TaskStatus.FINISHED
                task.save()
                return current_state, True

            # Find the selected action in the tool
            action = robocheftool.find_action(selection['action']['name'])
            console.print(f"found action: {action}", style="blue")
            if not action:
                console.print(f"action returned not found: {selection['action']['name']}")
                raise SystemError("action not found")

            # Take the selected action
            try:
                action_response = robocheftool.use(action, **selection['action']['parameters'])
            except Exception as e:
                raise ValueError(f"Trouble using action: {e}")

            console.print(f"action output: {action_response}", style="blue")
            if action_response:
                task.post_message(
                    "assistant", f"👁️ Result from taking action: {action_response}"
                )

            # Record the action for feedback and tuning
            task.record_action(
                state=EnvState(),
                action=selection['action'],
                tool=robocheftool.ref(),
                result=action_response,
                agent_id=self.name(),
                model=response.response_metadata['model_name'],
            )

            new_state = action_response
            return new_state, False

        except Exception as e:
            console.print("Exception taking action: ", e)
            traceback.print_exc()
            task.post_message("assistant", f"⚠️ Error taking action: {e} -- retrying...")
            raise e

    @classmethod
    def supported_devices(cls) -> List[Type[Device]]:
        """Devices this agent supports

        Returns:
            List[Type[Device]]: A list of supported devices
        """
        return [Desktop]

    @classmethod
    def config_type(cls) -> Type[RoboChefConfig]:
        """Type of config

        Returns:
            Type[RoboChefConfig]: Config type
        """
        return RoboChefConfig

    @classmethod
    def from_config(cls, config: RoboChefConfig) -> "RoboChef":
        """Create an agent from a config

        Args:
            config (RoboChefConfig): Agent config

        Returns:
            RoboChef: The agent
        """
        return RoboChef()

    @classmethod
    def default(cls) -> "RoboChef":
        """Create a default agent

        Returns:
            RoboChef: The agent
        """
        return RoboChef()

    @classmethod
    def init(cls) -> None:
        """Initialize the agent class"""
        return


Agent = RoboChef
