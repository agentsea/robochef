<!-- PROJECT LOGO -->
<br />
<p align="center">
  <!-- <a href="https://github.com/agentsea/skillpacks">
    <img src="https://project-logo.png" alt="Logo" width="80">
  </a> -->

  <h1 align="center">RoboChef</h1>
    <p align="center">
    <img src="https://storage.googleapis.com/guisurfer-assets/SurfPizza.webp" alt="SurfPizza Logo" width="200" style="border-radius: 20px;">
    </p>
  <p align="center">
    An AI agent that understands your requirements and does the following:
    <ul>
      <li>Searches recipes that meet your requirements</li>
      <li>Converts ingredient amounts from one unit to another</li>
      <li>Finds substitutes for your ingredients</li>
    </ul>
    <br />
    <a href="https://docs.hub.agentsea.ai/introduction"><strong>Explore AgentSea docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/agentsea/robochef/issues">Report Bug</a>
    ·
    <a href="https://github.com/agentsea/robochef/issues">Request Feature</a>
  </p>
  <br>
</p>

## Install

```sh
pip install surfkit
```

## Quick Start

### Configure API Keys

#### Spoonacular

RoboChef uses <a href="https://spoonacular.com/food-api">Spoonacular</a> to find recipes and other information for the user. So, you should set your Spoonacular API key.

```sh
export SPOONACULAR_API_KEY=<Provide your SPOONACULAR API KEY here>
```
If you have not created an account in Spoonacular, visit <a href="https://spoonacular.com/food-api">Spoonacular</a> to create an account and get your API key.

#### LLM

RoboChef uses LLMs like OpenAI GPT for AI capabilities. So, you should set your LLM API keys.

```sh
export OPENAI_API_KEY=<Provide your OPENAI API KEY here>
```

### Create a tracker

```sh
surfkit create tracker --name tracker01
```

### Create a device

```sh
surfkit create device --name device01
```

### Create the agent and solve a task

```sh
surfkit create agent --name agent01 -r process --local-keys
```

Solve a task

```sh
surfkit solve "Find me a gluten-free vegetarian salad recipe with tomato and carrots and without any eggs" \
  --device device01 \
  --tracker tracker01 \
  --agent agent01
```

You can also skip the agent creation step and directly run solve. You should specify the path of the `agent.yaml` file and the agent will be automatically created. This method makes it easier to solve multiple tasks, because you don't need explicitly create the agent each time.

```sh
surfkit solve "Find me a gluten-free vegetarian salad recipe with tomato and carrots and without any eggs" \
  --device device01 \
  --tracker tracker01 \
  -f agent.yaml
```

```sh
surfkit solve "Can you convert 2 cups flour into grams?" \
  --device device01 \
  --tracker tracker01 \
  -f agent.yaml
```

```sh
surfkit solve "What can I use instead of butter?" \
  --device device01 \
  --tracker tracker01 \
  -f agent.yaml
```

### Get the agent logs
```sh
surfkit logs --name ag101
```

### Delete the resources
```sh
surfkit delete device device01
surfkit delete tracker tracker01
surfkit delete agent agent01
```

## Documentation

See our [docs](https://docs.hub.agentsea.ai) for more information on how to use SurfPizza.

## Community

Come join us on [Discord](https://discord.gg/hhaq7XYPS6).

