# Agent Lab

This is a repo for exploring the main techniques that make agents work like tool use, memory and swarms.

# Structure

## Notebooks

Jupyter notebooks contain experimentation with langchain and langgraph modules. Core concepts are in standalone modules as follow:

- agent_basics.ipynb --> basic building blocks of an agent using langchain's create_agent class
- tools.ipynb --> introduction to how to define and call tools in agents
- agent_memory.ipynb --> techniques for creating and managing agent memory starting with short term
- swarms.ipynb --> exploring the use of agent swarms (network of smaller, focused agents)
- multimodal.ipynb --> exploring multimodal (image and audio) inputs to a LLM

## src

- personal_chef.py --> first application of core concepts to create a personal chef agent